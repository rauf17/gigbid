# Portfolio MCP Server (`portfolio`)

A read-only Model Context Protocol (MCP) server providing structured, verifiable access to freelancer persona evidence, case studies, skill inventories, and historical bid outcomes. Built with the official MCP Python SDK (`FastMCP`) supporting both Streamable HTTP and stdio transports.

---

## 1. Quick Start

### Running with `uvx` or `uv run`

#### Streamable HTTP Transport (Default, Port 8001)
```bash
uv run gigbid-portfolio-mcp --port 8001
```
Or directly via the Python module:
```bash
uv run python -m mcp_servers.portfolio.server --port 8001
```

#### Stdio Mode (For Desktop MCP Clients)
```bash
uv run gigbid-portfolio-mcp --stdio --persona ai_ml
```

---

## 2. Claude Desktop Integration

To connect the Portfolio MCP server to Claude Desktop, add the following snippet to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "portfolio": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/gigbid",
        "gigbid-portfolio-mcp",
        "--stdio",
        "--persona",
        "ai_ml"
      ],
      "env": {
        "PORTFOLIO_PERSONA": "ai_ml",
        "USE_HASH_EMBEDDER": "1"
      }
    }
  }
}
```

---

## 3. Configuration & Authentication

| Environment Variable | Description | Default |
| :--- | :--- | :--- |
| `PORTFOLIO_PERSONA` | Active persona identifier (`ai_ml`, `fullstack`, `data_analyst`) | `ai_ml` |
| `PORTFOLIO_MCP_TOKEN` | Optional Bearer token for HTTP transport. If unset, access is unauthenticated. | *(empty)* |
| `USE_HASH_EMBEDDER` | Use deterministic offline 384-dim embedder (no downloads/network) | `0` |

### HTTP Headers
- `X-Persona`: Dynamically switches persona per HTTP request (e.g. `X-Persona: fullstack`).
- `Authorization`: `Bearer <PORTFOLIO_MCP_TOKEN>` (required if `PORTFOLIO_MCP_TOKEN` is configured).

---

## 4. Tools Catalog

All tools carry strict safety annotations:
`readOnlyHint=true`, `idempotentHint=true`, `destructiveHint=false`, `openWorldHint=false`.

### 4.1 `search_evidence`
- **Description**: Search verified portfolio evidence chunks matching a client job requirement or technical topic.
- **Inputs**:
  - `requirement` (str, 3..500 characters): Target requirement, query, or technical domain.
  - `k` (int, 1..20, default 5): Maximum evidence items to return.
  - `filters` (optional dict): Filter by `type` (`cv`, `case_study`, `repo_readme`, `repo_code`, `review`, `proposal`), `skills` (`list[str]`), and `outcome` (`won`, `replied`, `ignored`).
- **Output**: `SearchEvidenceOutput` containing matching evidence items with scores and metadata.

### 4.2 `get_case_study`
- **Description**: Retrieve full Markdown text and verified metadata for a specific case study by ID.
- **Inputs**: `id` (str): Unique case study identifier (e.g. `cs_01`).
- **Output**: `CaseStudyOutput` with full project narrative, skills, client industry, and outcomes. Fails gracefully with a structured error if not found.

### 4.3 `list_skills`
- **Description**: List all technical and domain skills claimed across the persona's verified artifacts, with counts of how many evidence items back each skill.
- **Inputs**: None.
- **Output**: `ListSkillsOutput` with deduplicated skill list sorted by backing evidence count.

---

## 5. Resource Templates

Clients that browse URIs rather than executing tool calls can inspect resources directly:

- `portfolio://case/{id}`: Full Markdown text and front-matter of a specific case study.
- `portfolio://proposal/{id}`: Historical proposal cover letter text and outcome status.

---

## 6. Prompt Templates

Pre-engineered prompt workflows available to MCP clients:

1. **`Answer a screening question from my portfolio`**:
   - Argument: `question` (str)
   - Renders instructions guiding the model to query `search_evidence`, cite verifiable evidence item IDs, and never extrapolate or hallucinate unverified experience.

2. **`Summarise my most relevant experience for this job`**:
   - Argument: `job_text` (str)
   - Renders instructions to query top 3 evidence items matching a target job description and draft tailored proposal proof points.
