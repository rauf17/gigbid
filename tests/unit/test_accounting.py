"""Unit tests for LLM accounting and cost/token aggregation (AI-4016 Requirement R8/E5)."""
from __future__ import annotations

import json
from pathlib import Path

from agent.accounting import (
    aggregate_by_node,
    aggregate_by_trace,
    compute_overall_metrics,
    generate_accounting_report,
    load_call_logs,
)


def test_accounting_hand_built_log(tmp_path: Path) -> None:
    """Verifies that nested, repair retries, fallbacks, and multi-call traces are fully summed."""
    log_file = tmp_path / "mock_llm_calls.jsonl"

    # Hand-built log entries
    # Trace 1: Multi-step pipeline with initial call, repair retry, and fallback
    mock_records = [
        # Call 1 in trace_alpha: Analyst node
        {
            "ts": "2026-11-15T12:00:00Z",
            "trace_id": "trace_alpha",
            "node": "analyst",
            "model": "openai/gpt-oss-20b",
            "prompt_tokens": 500,
            "completion_tokens": 150,
            "total_tokens": 650,
            "latency_ms": 1200.0,
            "cache_hit": False,
            "retries": 0,
            "fallback_used": False,
            "status": "success",
            "estimated_cost_usd": 0.00065,
        },
        # Call 2 in trace_alpha: Writer initial call (failed schema validation, triggered repair)
        {
            "ts": "2026-11-15T12:00:02Z",
            "trace_id": "trace_alpha",
            "node": "writer",
            "model": "openai/gpt-oss-120b",
            "prompt_tokens": 900,
            "completion_tokens": 1600,
            "total_tokens": 2500,
            "latency_ms": 2500.0,
            "cache_hit": False,
            "retries": 1,
            "fallback_used": False,
            "status": "repaired",
            "estimated_cost_usd": 0.0050,
        },
        # Call 3 in trace_alpha: Verifier with fallback model used
        {
            "ts": "2026-11-15T12:00:05Z",
            "trace_id": "trace_alpha",
            "node": "verifier",
            "model": "openai/gpt-oss-20b",
            "prompt_tokens": 800,
            "completion_tokens": 200,
            "total_tokens": 1000,
            "latency_ms": 1800.0,
            "cache_hit": False,
            "retries": 1,
            "fallback_used": True,
            "status": "success",
            "estimated_cost_usd": 0.0010,
        },
        # Trace 2: Cached call + error call
        {
            "ts": "2026-11-15T12:01:00Z",
            "trace_id": "trace_beta",
            "node": "analyst",
            "model": "openai/gpt-oss-20b",
            "prompt_tokens": 500,
            "completion_tokens": 150,
            "total_tokens": 650,
            "latency_ms": 0.0,
            "cache_hit": True,
            "retries": 0,
            "fallback_used": False,
            "status": "success",
            "estimated_cost_usd": 0.0,
        },
        {
            "ts": "2026-11-15T12:01:01Z",
            "trace_id": "trace_beta",
            "node": "risk_assessor",
            "model": "openai/gpt-oss-20b",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "latency_ms": 500.0,
            "cache_hit": False,
            "retries": 3,
            "fallback_used": False,
            "status": "error",
            "estimated_cost_usd": 0.0,
        },
    ]

    with open(log_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in mock_records)

    loaded = load_call_logs(log_file)
    assert len(loaded) == 5

    # Test aggregate_by_trace
    traces = aggregate_by_trace(loaded)
    assert "trace_alpha" in traces
    alpha = traces["trace_alpha"]
    assert alpha["calls"] == 3
    assert alpha["nodes_called"] == ["analyst", "verifier", "writer"]
    # Total tokens must sum all calls: 650 + 2500 + 1000 = 4150
    assert alpha["total_tokens"] == 4150
    assert alpha["total_prompt_tokens"] == 2200
    assert alpha["total_completion_tokens"] == 1950
    assert alpha["retries"] == 2
    assert alpha["fallbacks_used"] == 1
    assert round(alpha["total_cost_usd"], 4) == 0.0066
    assert round(alpha["total_latency_ms"], 1) == 5500.0

    assert "trace_beta" in traces
    beta = traces["trace_beta"]
    assert beta["calls"] == 2
    assert beta["total_tokens"] == 650
    assert beta["retries"] == 3

    # Test aggregate_by_node
    nodes = aggregate_by_node(loaded)
    assert "analyst" in nodes
    analyst_stat = nodes["analyst"]
    assert analyst_stat["calls"] == 2
    assert analyst_stat["cache_hits"] == 1
    assert analyst_stat["total_tokens"] == 1300
    # Mean tokens per call: 1300 / 2 = 650.0
    assert analyst_stat["mean_tokens_per_call"] == 650.0
    # Non-cached latency p50 for analyst: [1200.0] -> 1200.0
    assert analyst_stat["p50_latency_ms"] == 1200.0

    writer_stat = nodes["writer"]
    assert writer_stat["calls"] == 1
    assert writer_stat["total_tokens"] == 2500
    assert writer_stat["p50_latency_ms"] == 2500.0

    # Test overall metrics
    overall = compute_overall_metrics(loaded)
    assert overall["total_calls"] == 5
    assert overall["cache_hits"] == 1
    assert overall["total_tokens"] == 4800

    # Test complete report generation
    out_dir = tmp_path / "results"
    report = generate_accounting_report(log_path=log_file, output_dir=out_dir)
    assert (out_dir / "llm_accounting_latest.json").is_file()
    assert report["overall"]["total_tokens"] == 4800
