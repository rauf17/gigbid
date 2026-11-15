"""LangSmith Tracing and Telemetry Integration (Requirement E3).

Provides centralized trace ID propagation, LangSmith runtime configuration,
PII anonymization hooks, and runnable metadata helpers for graph execution.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig

from agent.pii import mask_pii_obj

logger = logging.getLogger(__name__)

_CLIENT_INSTANCE: Any | None = None


def is_tracing_enabled() -> bool:
    """Returns True if a valid LangSmith API key is configured."""
    key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    return bool(key and key.strip() and not key.startswith("placeholder") and not key.startswith("your_"))


def init_tracing() -> bool:
    """Initializes LangSmith tracing environment and returns True if active."""
    if not is_tracing_enabled():
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return False

    key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    project = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or "gigbid"
    endpoint = os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT") or "https://api.smith.langchain.com"

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = key
    os.environ["LANGCHAIN_PROJECT"] = project
    os.environ["LANGCHAIN_ENDPOINT"] = endpoint

    logger.info("[tracing] LangSmith tracing enabled for project '%s'", project)
    return True


def get_langsmith_client() -> Any | None:
    """Returns singleton LangSmith Client with PII anonymizer hook, or None if disabled."""
    global _CLIENT_INSTANCE
    if _CLIENT_INSTANCE is not None:
        return _CLIENT_INSTANCE

    if not is_tracing_enabled():
        return None

    try:
        from langsmith import Client

        _CLIENT_INSTANCE = Client(
            anonymizer=mask_pii_obj,
            hide_inputs=mask_pii_obj,
            hide_outputs=mask_pii_obj,
        )
        return _CLIENT_INSTANCE
    except Exception as exc:  # noqa: BLE001
        logger.debug("[tracing] Failed initializing LangSmith client: %s", exc)
        return None


def ensure_valid_uuid(val: str | None) -> uuid.UUID:
    """Converts arbitrary trace string or generates a valid RFC-4122 UUID."""
    if not val:
        return uuid.uuid4()
    try:
        return uuid.UUID(val)
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


def build_trace_config(
    trace_id: str | None = None,
    thread_id: str | None = None,
    job_id: str | None = None,
    persona: str | None = None,
    user_id: str | None = None,
    node_models: dict[str, str] | None = None,
    deps: Any | None = None,
) -> RunnableConfig:
    """Builds a LangGraph RunnableConfig propagating the trace id, run_id, and metadata."""
    run_uuid = ensure_valid_uuid(trace_id)
    str_trace_id = str(run_uuid)

    hashed_uid = hashlib.sha256(str(user_id or "default").encode("utf-8")).hexdigest()[:16]

    metadata: dict[str, Any] = {
        "trace_id": str_trace_id,
        "thread_id": thread_id or str_trace_id,
        "job_id": job_id or "unknown",
        "persona": persona or "unknown",
        "hashed_user_id": hashed_uid,
        "node_models": node_models or {},
    }

    tags = [str_trace_id]
    if persona:
        tags.append(persona)
    if job_id:
        tags.append(job_id)

    config: RunnableConfig = {
        "run_id": run_uuid,
        "configurable": {
            "thread_id": thread_id or str_trace_id,
        },
        "metadata": metadata,
        "tags": tags,
    }

    if deps is not None:
        config["configurable"]["deps"] = deps

    return config


def get_run_url(trace_id: str) -> str:
    """Returns human-browsable LangSmith run URL for a given trace_id."""
    run_uuid = ensure_valid_uuid(trace_id)
    client = get_langsmith_client()
    project = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or "gigbid"

    if client:
        try:
            run = client.read_run(str(run_uuid))
            url = client.get_run_url(run=run, project_name=project)
            if url:
                return url
        except Exception as exc:  # noqa: BLE001
            logger.debug("[tracing] Could not retrieve run URL: %s", exc)

    return f"https://smith.langchain.com/o/default/projects/p/{project}/r/{run_uuid}"
