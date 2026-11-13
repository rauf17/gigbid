"""Factory function for selecting and initializing marketplace adapters."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from mcp_servers.marketplace.adapters.base import MarketplaceAdapter
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.adapters.upwork_live import UpworkLiveAdapter

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "agent" / "config.yaml"


def get_adapter(
    mode: str | None = None,
    config_path: Path | str | None = None,
    **adapter_kwargs: Any,
) -> MarketplaceAdapter:
    """Selects and instantiates the configured marketplace adapter.

    Precedence:
    1. Explicit `mode` parameter
    2. Environment variable `MARKETPLACE_MODE`
    3. `agent/config.yaml` field `marketplace.mode`
    4. Default: `"gigsim"`
    """
    selected_mode = mode or os.getenv("MARKETPLACE_MODE")

    if not selected_mode:
        cfg_file = Path(config_path or DEFAULT_CONFIG_PATH)
        if cfg_file.is_file():
            try:
                data = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
                selected_mode = data.get("marketplace", {}).get("mode")
            except (yaml.YAMLError, OSError):
                selected_mode = None

    selected_mode = (selected_mode or "gigsim").lower().strip()

    if selected_mode == "gigsim":
        return GigSimAdapter(**adapter_kwargs)
    elif selected_mode in {"upwork", "upwork_live"}:
        return UpworkLiveAdapter()
    else:
        raise ValueError(
            f"Unsupported marketplace mode: '{selected_mode}'. Expected 'gigsim' or 'upwork'."
        )
