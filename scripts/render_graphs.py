"""Compiles and renders the LangGraph StateGraph bid graph into Mermaid and PNG diagrams.

Assignment requirements:
- Part 5 of Prompt 9.
- Exports docs/images/bid_graph.mmd (Mermaid markup).
- Exports docs/images/bid_graph.png (rendered graphic).
- Run as part of CI to ensure diagrams never drift from code.
"""
from __future__ import annotations

import logging
from pathlib import Path

from agent.graphs.bid_graph import build_bid_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "images"


def render() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Compiling StateGraph bid graph...")
    graph = build_bid_graph()
    drawable = graph.get_graph()

    mmd_path = DOCS_DIR / "bid_graph.mmd"
    logger.info("Rendering Mermaid diagram to %s", mmd_path)
    mmd_content = drawable.draw_mermaid()
    mmd_path.write_text(mmd_content, encoding="utf-8")

    png_path = DOCS_DIR / "bid_graph.png"
    logger.info("Rendering PNG diagram to %s", png_path)
    try:
        png_bytes = drawable.draw_mermaid_png()
        png_path.write_bytes(png_bytes)
        logger.info("Successfully generated %s (%d bytes)", png_path, len(png_bytes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not generate PNG directly (network/mermaid CLI unavailable): %s", exc)


if __name__ == "__main__":
    render()
