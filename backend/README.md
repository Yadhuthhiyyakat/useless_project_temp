# Digital Cemetery — Backend

Local privacy-focused filesystem monitoring application. It watches
user-selected directories and records permanent digital "death records" for
deleted files.

> **Status:** Phase 1 (project foundation). Most features are scaffolded and
> implemented in later phases.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (or plain `pip`)

## Quick start

```bash
uv venv .venv
uv pip install -r requirements.txt
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the interactive API documentation.

## Tests

```bash
pytest
```

The full README (architecture, API reference, operational details) is written
in a later phase.