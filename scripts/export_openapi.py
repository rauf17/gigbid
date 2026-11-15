"""CLI script to export FastAPI OpenAPI specification to JSON."""
from __future__ import annotations

import json
from pathlib import Path

from apps.api.main import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "apps" / "api" / "openapi.json"


def export_openapi() -> None:
    openapi_schema = app.openapi()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(openapi_schema, indent=2), encoding="utf-8")
    print(f"[export_openapi] Exported {len(openapi_schema.get('paths', {}))} API paths to {OUTPUT_PATH}")


if __name__ == "__main__":
    export_openapi()
