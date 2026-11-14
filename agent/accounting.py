"""LLM Call Logging and Cost/Latency Accounting (AI-4016 Requirement R8).

Aggregates data/processed/llm_calls.jsonl into p50/p95 latency and tokens/USD per node
and per trace_id, producing deterministic JSON benchmarks in evals/results/.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "llm_calls.jsonl"
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "results"


def load_call_logs(log_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Reads all JSONL audit records from the LLM call log."""
    path = Path(log_path or DEFAULT_LOG_PATH)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def aggregate_by_node(logs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregates latency (p50/p95), tokens, and USD cost by graph node."""
    by_node: dict[str, list[dict[str, Any]]] = {}
    for entry in logs:
        node = entry.get("node", "unknown")
        by_node.setdefault(node, []).append(entry)

    summary: dict[str, dict[str, Any]] = {}
    for node, entries in sorted(by_node.items()):
        latencies = [float(e.get("latency_ms", 0.0)) for e in entries if not e.get("cache_hit", False)]
        prompt_tokens = sum(int(e.get("prompt_tokens", 0)) for e in entries)
        completion_tokens = sum(int(e.get("completion_tokens", 0)) for e in entries)
        total_tokens = prompt_tokens + completion_tokens
        total_cost = sum(float(e.get("estimated_cost_usd", 0.0)) for e in entries)
        cache_hits = sum(1 for e in entries if e.get("cache_hit", False))
        fallbacks = sum(1 for e in entries if e.get("fallback_used", False))
        errors = sum(1 for e in entries if e.get("status") == "error")

        p50 = float(np.percentile(latencies, 50)) if latencies else 0.0
        p95 = float(np.percentile(latencies, 95)) if latencies else 0.0
        mean_lat = float(np.mean(latencies)) if latencies else 0.0

        summary[node] = {
            "calls": len(entries),
            "cache_hits": cache_hits,
            "fallbacks_used": fallbacks,
            "errors": errors,
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "mean_latency_ms": round(mean_lat, 2),
            "total_prompt_tokens": prompt_tokens,
            "total_completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "mean_tokens_per_call": round(total_tokens / len(entries), 1) if entries else 0.0,
            "total_cost_usd": round(total_cost, 6),
        }

    return summary


def aggregate_by_trace(logs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregates calls, tokens, latency, and cost per execution trace_id."""
    by_trace: dict[str, list[dict[str, Any]]] = {}
    for entry in logs:
        t_id = entry.get("trace_id", "unknown")
        by_trace.setdefault(t_id, []).append(entry)

    summary: dict[str, dict[str, Any]] = {}
    for trace_id, entries in by_trace.items():
        total_tokens = sum(int(e.get("prompt_tokens", 0)) + int(e.get("completion_tokens", 0)) for e in entries)
        total_cost = sum(float(e.get("estimated_cost_usd", 0.0)) for e in entries)
        total_latency = sum(float(e.get("latency_ms", 0.0)) for e in entries)
        nodes = sorted({e.get("node", "unknown") for e in entries})

        summary[trace_id] = {
            "calls": len(entries),
            "nodes_called": nodes,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "total_latency_ms": round(total_latency, 2),
        }

    return summary


def compute_overall_metrics(logs: list[dict[str, Any]]) -> dict[str, Any]:
    """Computes overall aggregate metrics across all recorded calls."""
    if not logs:
        return {
            "total_calls": 0,
            "cache_hits": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
        }

    latencies = [float(e.get("latency_ms", 0.0)) for e in logs if not e.get("cache_hit", False)]
    total_tokens = sum(int(e.get("prompt_tokens", 0)) + int(e.get("completion_tokens", 0)) for e in logs)
    total_cost = sum(float(e.get("estimated_cost_usd", 0.0)) for e in logs)
    cache_hits = sum(1 for e in logs if e.get("cache_hit", False))

    p50 = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95 = float(np.percentile(latencies, 95)) if latencies else 0.0

    return {
        "total_calls": len(logs),
        "cache_hits": cache_hits,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
    }


def generate_accounting_report(
    log_path: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Generates complete LLM accounting report and writes results JSON files."""
    logs = load_call_logs(log_path)
    overall = compute_overall_metrics(logs)
    by_node = aggregate_by_node(logs)
    by_trace = aggregate_by_trace(logs)

    timestamp = datetime.now(UTC).isoformat()
    timestamp_slug = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    report = {
        "timestamp": timestamp,
        "overall": overall,
        "by_node": by_node,
        "by_trace": by_trace,
    }

    out_dir = Path(output_dir or DEFAULT_RESULTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts_file = out_dir / f"llm_accounting_{timestamp_slug}.json"
    latest_file = out_dir / "llm_accounting_latest.json"

    ts_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report
