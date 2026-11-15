"""Local verification script for Hugging Face Space single-container deployment."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_KEY = os.getenv("GROQ_API_KEY", "")
REVIEWER_EMAIL = "reviewer@gigbid.local"
REVIEWER_PASSWORD = "reviewer_password_123"
CONTAINER_NAME = "test-gigbid-space"
BASE_URL = "http://127.0.0.1:7860"


def run_cmd(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def main() -> None:
    print(f"--- 1. Cleaning up existing {CONTAINER_NAME} if any ---")
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], check=False, capture_output=True)

    print("--- 2. Checking image size ---")
    img_size = run_cmd(["docker", "images", "gigbid-space:latest", "--format", "{{.Size}}"])
    print(f"Image Size: {img_size}")

    print("--- 3. Launching container & measuring cold-start seconds ---")
    t0 = time.perf_counter()
    run_cmd([
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", "7860:7860",
        "-e", f"GROQ_API_KEY={GROQ_KEY}",
        "-e", f"REVIEWER_EMAIL={REVIEWER_EMAIL}",
        "-e", f"REVIEWER_PASSWORD={REVIEWER_PASSWORD}",
        "gigbid-space:latest",
    ])

    health_url = f"{BASE_URL}/api/health"
    healthy = False
    cold_start_seconds = 0.0

    for _ in range(60):
        try:
            req = urllib.request.Request(health_url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    t1 = time.perf_counter()
                    cold_start_seconds = t1 - t0
                    print(f"Healthy in {cold_start_seconds:.2f} seconds! Response: {data}")
                    healthy = True
                    break
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(1)

    if not healthy:
        print("ERROR: Container failed to become healthy within 60s.")
        print("=== Container Logs ===")
        print(run_cmd(["docker", "logs", CONTAINER_NAME]))
        sys.exit(1)

    print("\n--- 4. Test Reviewer Login via curl ---")
    login_url = f"{BASE_URL}/api/auth/login"
    login_payload = json.dumps({"email": REVIEWER_EMAIL, "password": REVIEWER_PASSWORD}).encode()
    login_req = urllib.request.Request(
        login_url,
        data=login_payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(login_req) as resp:
        login_resp = json.loads(resp.read().decode())

    token = login_resp.get("access_token")
    user_info = login_resp.get("user", {})
    print(f"Login success! User: {user_info.get('email')} (Persona: {user_info.get('persona_id')})")
    print(f"Token (preview): {token[:25]}...")

    print("\n--- 5. Get available jobs from inbox ---")
    jobs_req = urllib.request.Request(
        f"{BASE_URL}/api/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(jobs_req) as resp:
        jobs = json.loads(resp.read().decode())
    print(f"Retrieved {len(jobs)} jobs from marketplace/sim.")
    target_job = jobs[0]["id"] if jobs else "job_stream_00022"
    print(f"Selected target job for run: {target_job}")

    print(f"\n--- 6. Trigger run for job {target_job} to approval screen ---")
    run_req = urllib.request.Request(
        f"{BASE_URL}/api/runs",
        data=json.dumps({"job_id": target_job}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(run_req) as resp:
        run_res = json.loads(resp.read().decode())
    thread_id = run_res["thread_id"]
    print(f"Run initiated! Thread ID: {thread_id}")

    print("Polling run until pending approval or completion...")
    approval_dossier = None
    for poll_idx in range(45):
        time.sleep(2)
        try:
            app_req = urllib.request.Request(
                f"{BASE_URL}/api/approvals/{thread_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(app_req) as resp:
                if resp.status == 200:
                    approval_dossier = json.loads(resp.read().decode())
                    print(f"Reached approval screen! Node status: {approval_dossier.get('status')}")
                    break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                try:
                    st_req = urllib.request.Request(
                        f"{BASE_URL}/api/runs/{thread_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    with urllib.request.urlopen(st_req) as rresp:
                        st = json.loads(rresp.read().decode())
                        print(f"  [poll {poll_idx}] state status={st.get('status')}")
                        if st.get("status") in ("completed", "interrupted", "needs_attention"):
                            print(f"Run ended in state: {st.get('status')}")
                            approval_dossier = st
                            break
                except (urllib.error.URLError, TimeoutError, OSError) as poll_err:
                    logger.debug("Transient poll error: %s", poll_err)
            else:
                print(f"HTTPError: {e}")

    print("\n--- 7. Verification Summary ---")
    print(f"Image Size: {img_size}")
    print(f"Cold Start: {cold_start_seconds:.2f}s")
    if approval_dossier:
        print("Approval / Run State preview:")
        print(json.dumps(approval_dossier, indent=2)[:300] + "...")

    print("\n--- 8. Cleaning up container ---")
    run_cmd(["docker", "rm", "-f", CONTAINER_NAME])
    print("Test container removed.")


if __name__ == "__main__":
    main()
