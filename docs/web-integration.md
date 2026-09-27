# Deployment integration

The deployment handoff is consolidated into a single project:

| Handoff component | Maintained location |
| --- | --- |
| `frontend/simu-discuss/` | `frontend/` |
| FastAPI application | `backend/app/` |
| Legacy agent, retrieval, and analytics engines | `src/qubettera/` |
| Container orchestration | Root `docker-compose.yml` |

All frontend handoff files were compared before cleanup. The existing project
already included the complete frontend, plus fixes to discussion streaming,
analytics caching, and package scripts. Those fixes were retained. The legacy
`week3_adapter.py` is superseded by the backend's shared-package integration.
No nested engine checkout is needed at runtime.

The original handoff, including its Git history and deployment reference files,
was moved to a local temporary backup outside the workspace during cleanup.
Only the maintained application belongs in this repository.

Persona and history collection requests share one server-side implementation.
Mock fixtures require `MOCK_BACKEND=true`; upstream errors are visible in normal
mode. The analytics index opens the latest completed discussion with saved
analytics. Branding, keyboard tab navigation, skip navigation, and reduced-motion
support are shared across the UI.

Exact duplicate historical documents were replaced with links to their canonical
copies. Generated build directories and runtime data are not source duplicates
and remain excluded from version control.

See the [project README](../README.md) for setup, runtime limitations, and checks.
