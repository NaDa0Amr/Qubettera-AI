# Qubettera backend

From the project root, install `python -m pip install -e ".[web,analytics]"`
and run `python -m uvicorn backend.app.main:app --port 8000`.

This API uses the shared `qubettera` package, root `.env`, and `outputs/`.
It does not load the legacy `agent-apps` repositories. See the root README for
frontend startup, Docker, endpoint documentation, and runtime limitations.
