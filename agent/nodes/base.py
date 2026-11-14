"""Base dependencies container and helper utilities for agent nodes.

Assignment requirements:
- Nodes are plain async functions with signature: `async def run(state_slice: dict[str, Any], deps: NodeDeps) -> Handoff`.
- Dependencies carry port, retriever/portfolio client, and llm overrides.
- No node reads or writes global state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.llm import load_config
from agent.policy import PolicyPack, load_policy_pack

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@dataclass
class NodeDeps:
    """Explicit dependency injection container for agent node execution."""

    port: Any | None = None
    retriever: Any | None = None
    portfolio_client: Any | None = None
    llm: Any | None = None
    config: dict[str, Any] = field(default_factory=dict)
    policy: PolicyPack | None = None

    def get_config(self) -> dict[str, Any]:
        """Returns active configuration, loading from agent/config.yaml if not set."""
        if not self.config:
            self.config = load_config(DEFAULT_CONFIG_PATH)
        return self.config

    def get_policy(self) -> PolicyPack:
        """Returns machine policy pack, loading from data/policy_pack/policy.yaml if not set."""
        if self.policy is None:
            self.policy = load_policy_pack()
        return self.policy
