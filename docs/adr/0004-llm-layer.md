# ADR 0004: LLM Layer Implementation via langchain-groq and Centralized Configuration

**Status:** accepted

## Context
Assignment requirements specify "Models: Open and Local First" (R8). The platform must:
1. Use open-weight models served via Groq's high-speed API (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`).
2. Strictly decouple model configuration from application code: every node's model must be defined in `agent/config.yaml`, never hardcoded in `.py` files.
3. Support model profile switching (e.g. `open` vs. `open_alt` for model ablation studies) via the `MODEL_PROFILE` environment variable.
4. Provide structured output generation with Pydantic schema validation and automatic single-attempt repair retries.
5. Implement client-side token-bucket rate limiting, exponential backoff honoring `Retry-After`, deterministic on-disk response caching, and full audit logging with PII masking.

Two technical approaches were evaluated for the Groq client integration:
- **Option A: `langchain-groq` (`ChatGroq`)**
- **Option B: `langchain-openai` (`ChatOpenAI` with `base_url="https://api.groq.com/openai/v1"`)**

## Decision
We select **Option A: `langchain-groq` (`ChatGroq`)**.

### Justification
1. **Native Support for Groq Reasoning Parameters**: Groq's API exposes model-specific parameters such as `reasoning_effort` (`low`, `medium`, `high`) and `reasoning_format` (`parsed`, `raw`, `hidden`) for open-weight reasoning models like `openai/gpt-oss-120b`. `ChatGroq` natively exposes these as Pydantic fields, whereas `ChatOpenAI` requires manual injection into untyped `model_kwargs`.
2. **First-Class Structured Output**: `ChatGroq.with_structured_output` natively supports both `json_mode` and tool calling on open-weight models hosted on Groq, ensuring predictable Pydantic validation.
3. **Official Maintenance & Upstream Support**: `langchain-groq` is officially maintained by Groq and LangChain, guaranteeing compatibility with new open-weight model releases on Groq without adapter workarounds.
4. **Rate Limit & Error Handling**: `ChatGroq` surfaces Groq's specific 429 rate limit exceptions and `Retry-After` headers cleanly to our exponential backoff and token-bucket limiter.

## Consequences
- `langchain-groq>=1.1.3` is added to `pyproject.toml` dependencies.
- Model names are centralized in `agent/config.yaml`; no model names appear in `.py` application code (enforced by `scripts/check_repo_rules.py`).
- All LLM interactions flow through `agent/llm.py` via `get_llm(node)` and `llm_call(node, ...)`.
- CI runs hermetically using offline test doubles (`FakeChatModel`) without requiring `GROQ_API_KEY` or network connectivity.
