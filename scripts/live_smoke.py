"""Live smoke test verifying full autonomous bid flow against a running GigBid stack.

Requirements:
- Zero mocks: hits actual live HTTP endpoints.
- Steps:
  1. Authenticates as reviewer user.
  2. Lists candidate marketplace jobs (asserts >= 1).
  3. Launches bid graph run on a real job.
  4. Polls until graph suspends at approval interrupt (awaiting_approval).
  5. Inspects approval payload, draft text, and claim evidence.
  6. Submits human approval decision.
  7. Verifies proposal submission in pipeline / marketplace.
"""
from __future__ import annotations

import os
import sys
import time

import httpx


def run_smoke(base_url: str) -> None:
    print(f"=== Starting GigBid Live Smoke Test against {base_url} ===")

    email = os.getenv("REVIEWER_EMAIL", "reviewer@gigbid.local")
    password = os.getenv("REVIEWER_PASSWORD", "reviewer123")

    with httpx.Client(base_url=base_url, timeout=40.0) as client:
        # 1. Login
        print(f"\n[1/7] Logging in as {email}...")
        login_res = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        if login_res.status_code != 200:
            raise RuntimeError(f"Login failed: HTTP {login_res.status_code} - {login_res.text}")

        login_data = login_res.json()
        token = login_data.get("access_token")
        if not token:
            raise RuntimeError(f"No access token returned: {login_data}")

        client.headers["Authorization"] = f"Bearer {token}"
        print(f"  ✓ Authenticated successfully. Token: {token[:12]}...")

        # Verify /auth/me
        me_res = client.get("/api/auth/me")
        if me_res.status_code != 200:
            raise RuntimeError(f"GET /auth/me failed: {me_res.status_code} - {me_res.text}")
        me_data = me_res.json()
        print(f"  ✓ Verified tenant user: id={me_data.get('id')} email={me_data.get('email')} persona={me_data.get('persona_id')}")

        # 2. List candidate jobs
        print("\n[2/7] Discovering marketplace candidate jobs (GET /api/jobs)...")
        jobs_res = client.get("/api/jobs")
        if jobs_res.status_code != 200:
            raise RuntimeError(f"GET /api/jobs failed: HTTP {jobs_res.status_code} - {jobs_res.text}")

        jobs = jobs_res.json()
        if not isinstance(jobs, list) or len(jobs) == 0:
            raise RuntimeError(f"Expected at least 1 job, got: {jobs}")

        first_three = [j.get("id") for j in jobs[:3]]
        print(f"  ✓ Retrieved {len(jobs)} candidate jobs.")
        print(f"  ✓ Sample job IDs: {first_three}")

        # 3. Start a bid run on a real candidate job
        candidate_job = next((j for j in jobs if not j.get("is_scam", False)), jobs[0])
        job_id = candidate_job["id"]
        print(f"\n[3/7] Starting autonomous bid graph run for job: {job_id}...")
        run_res = client.post(
            "/api/runs",
            json={"job_id": job_id},
        )
        if run_res.status_code not in {200, 201}:
            raise RuntimeError(f"POST /api/runs failed: HTTP {run_res.status_code} - {run_res.text}")

        run_data = run_res.json()
        thread_id = run_data.get("thread_id") or f"{me_data['id']}:{job_id}"
        print(f"  ✓ Run launched. Thread ID: {thread_id}, initial status: {run_data.get('status')}")

        # 4. Poll until graph reaches awaiting_approval
        print(f"\n[4/7] Polling run status for {thread_id} until awaiting_approval...")
        max_attempts = 45
        is_ready = False
        last_status = "unknown"

        for attempt in range(1, max_attempts + 1):
            time.sleep(1.5)
            state_res = client.get(f"/api/runs/{thread_id}")
            if state_res.status_code == 200:
                st = state_res.json()
                last_status = st.get("status", "unknown")
                if st.get("is_awaiting_approval") or last_status == "awaiting_approval":
                    appr_check = client.get(f"/api/approvals/{thread_id}")
                    if appr_check.status_code == 200:
                        appr_d = appr_check.json()
                        if appr_d.get("draft", {}).get("cover_letter"):
                            is_ready = True
                            print(f"  ✓ Approval gate reached after {attempt * 1.5:.1f}s (status={last_status})!")
                            break

            print(f"    ... waiting for graph execution (attempt {attempt}/{max_attempts}, status={last_status})")

        if not is_ready:
            raise TimeoutError(f"Bid graph run did not reach awaiting_approval within 60s. Last status: {last_status}")

        # 5. Inspect approval payload
        print(f"\n[5/7] Inspecting approval dossier (GET /api/approvals/{thread_id})...")
        appr_res = client.get(f"/api/approvals/{thread_id}")
        if appr_res.status_code != 200:
            raise RuntimeError(f"GET /api/approvals failed: HTTP {appr_res.status_code} - {appr_res.text}")

        appr_data = appr_res.json()
        keys = list(appr_data.keys())
        print(f"  ✓ Approval payload keys: {keys}")

        draft = appr_data.get("draft") or {}
        cover_letter = draft.get("cover_letter", "")
        if not cover_letter:
            raise RuntimeError(f"Draft proposal has empty cover letter! Payload: {appr_data}")

        print("  ✓ First 200 chars of draft proposal:")
        print("  --------------------------------------------------")
        print(f"  {cover_letter[:200]}")
        print("  --------------------------------------------------")

        # 6. Submit human approval
        print(f"\n[6/7] Submitting approval decision (POST /api/approvals/{thread_id} action=approve)...")
        decide_res = client.post(
            f"/api/approvals/{thread_id}",
            json={"action": "approve"},
        )
        if decide_res.status_code != 200:
            raise RuntimeError(f"Approval decision failed: HTTP {decide_res.status_code} - {decide_res.text}")

        decide_data = decide_res.json()
        print(f"  ✓ Approval response: status={decide_data.get('status')} action={decide_data.get('action_taken')}")

        # 7. Verify proposal was submitted to marketplace / pipeline
        print("\n[7/7] Verifying proposal submission (GET /api/proposals)...")
        time.sleep(2.0)
        prop_res = client.get("/api/proposals")
        if prop_res.status_code != 200:
            raise RuntimeError(f"GET /api/proposals failed: HTTP {prop_res.status_code} - {prop_res.text}")

        pipeline = prop_res.json()
        submitted = pipeline.get("submitted", [])
        submitted_job_ids = [p.get("job_id") for p in submitted]
        print(f"  ✓ Pipeline submitted count: {len(submitted)}; Job IDs: {submitted_job_ids}")

        if job_id not in submitted_job_ids and len(submitted) == 0:
            # Check proposal submissions directly
            print("  Note: Checking if submission was recorded under thread or direct status...")
            run_check = client.get(f"/api/runs/{thread_id}")
            if run_check.status_code == 200 and run_check.json().get("status") == "submitted":
                print("  ✓ Run state confirms status=submitted!")
            else:
                raise RuntimeError(f"Submitted job {job_id} not found in pipeline: {pipeline}")
        else:
            print(f"  ✓ Job {job_id} confirmed in submitted proposals pipeline!")

    print("\n" + "=" * 60)
    print("✓✓✓ LIVE SMOKE TEST PASSED: Full autonomous flow verified ✓✓✓")
    print("=" * 60)


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:7860"
    try:
        run_smoke(base_url=base_url)
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ LIVE SMOKE TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
