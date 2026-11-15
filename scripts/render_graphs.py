"""Compiles and renders the LangGraph StateGraphs (bid graph and conversation graph) into Mermaid and PNG diagrams.

Assignment requirements:
- Exports docs/images/bid_graph.mmd and docs/images/bid_graph.png.
- Exports docs/images/conversation_graph.mmd and docs/images/conversation_graph.png.
- Run as part of CI to ensure diagrams never drift from code.
"""
from __future__ import annotations

import logging
from pathlib import Path

from agent.graphs.bid_graph import build_bid_graph
from agent.graphs.conversation_graph import build_conversation_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "images"


def render() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Bid Graph
    logger.info("Compiling StateGraph bid graph...")
    b_graph = build_bid_graph()
    b_drawable = b_graph.get_graph()

    b_mmd_path = DOCS_DIR / "bid_graph.mmd"
    logger.info("Rendering Mermaid diagram to %s", b_mmd_path)
    b_mmd_path.write_text(b_drawable.draw_mermaid(), encoding="utf-8")

    b_png_path = DOCS_DIR / "bid_graph.png"
    try:
        b_png_bytes = b_drawable.draw_mermaid_png()
        b_png_path.write_bytes(b_png_bytes)
        logger.info("Successfully generated %s (%d bytes)", b_png_path, len(b_png_bytes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not generate PNG for bid graph: %s", exc)

    # 2. Conversation Graph
    logger.info("Compiling StateGraph conversation graph...")
    c_graph = build_conversation_graph()
    c_drawable = c_graph.get_graph()

    c_mmd_path = DOCS_DIR / "conversation_graph.mmd"
    logger.info("Rendering Mermaid diagram to %s", c_mmd_path)
    c_mmd_path.write_text(c_drawable.draw_mermaid(), encoding="utf-8")

    c_png_path = DOCS_DIR / "conversation_graph.png"
    try:
        c_png_bytes = c_drawable.draw_mermaid_png()
        c_png_path.write_bytes(c_png_bytes)
        logger.info("Successfully generated %s (%d bytes)", c_png_path, len(c_png_bytes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not generate PNG for conversation graph: %s", exc)


if __name__ == "__main__":
    render()
