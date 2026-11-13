# ADR 0001: Stack and infrastructure
**Status:** accepted

- **Vector Storage**: Qdrant in local (path) mode replaces pgvector for vector search. Embedded local file persistence under `data/processed/index/qdrant/` enables fast CPU vector querying, zero external daemon overhead, and granular payload filtering for persona, artifact types, and skills.
- **Relational & Memory Storage**: PostgreSQL remains for LangGraph checkpointer persistence and agent memory store.
- **Task Queue**: Redis + Arq for background worker execution and asynchronous task queueing.
- **Observability**: LangSmith for tracing (simplest hosted option with public share links).
- **Model Profile**: Open-model profile: hosted open-model provider in deployment, Ollama locally.
- **Frontend & Backend**: Next.js + TypeScript frontend, FastAPI backend, OpenAPI-generated TS client.
