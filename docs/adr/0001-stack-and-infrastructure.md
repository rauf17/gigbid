# ADR 0001: Stack and infrastructure
**Status:** proposed

- Postgres with pgvector for checkpointer, memory store AND vectors (one fewer service to deploy).
- Redis + Arq for background work.
- LangSmith for tracing (simplest hosted option with public share links).
- Open-model profile: hosted open-model provider in deployment, Ollama locally.
- Next.js + TypeScript frontend, FastAPI backend, OpenAPI-generated TS client.
