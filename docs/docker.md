# Docker deployment and Docker Hub

The stack includes the Next.js UI, FastAPI API, shared retrieval/discussion/analytics
code, and PostgreSQL with pgvector. Optional Ollama containers provide local
generation and download the selected model before the API starts.

The two application images are:

- `<namespace>/qubettera-frontend:<tag>`
- `<namespace>/qubettera-backend:<tag>`

PostgreSQL and Ollama use their upstream images. Model weights, database contents,
research data, discussion history, and credentials are not included in the
application images. Live operation needs a populated knowledge base and either
configured external model access or the optional Ollama stack.

## Build and run locally

Use Docker Desktop with Linux containers, or Docker Engine with Compose 2.24.4+.
Allow sufficient memory/disk for PyTorch, Chromium, embeddings, and model downloads;
local generation adds substantial model memory requirements. The default backend
uses CPU PyTorch; this is not a CUDA image.

From the project root:

```powershell
# Only copy when you do not already have a configured .env.
Copy-Item .env.example .env
# Edit .env: PGPASSWORD, model endpoint/key, Docker Hub namespace and image tag.
docker compose build
docker compose up -d --wait --wait-timeout 180
docker compose ps
```

Open http://localhost:3000; API docs are at http://localhost:8000/docs.
`docker compose up -d postgres` starts only the database for local CLI development.
The previous `--profile web` flag is no longer needed: the default starts all three
services. The model cache and database use named volumes; local `data/` and
`outputs/` directories are shared with the CLI. On Linux, these directories must
be writable by container UID 10001. The Hub deployment below uses automatically
initialized named volumes instead.

For host-based Ollama, use `http://host.docker.internal:11434` in the relevant
backend URL variables. Container `localhost` refers to that container.

To host generation in Docker too:

```powershell
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build --wait --wait-timeout 1800
```

This sets `LLM_PROVIDER=ollama`, uses `OLLAMA_MODEL` (default `qwen3:4b`), and waits
for its first download. It overrides query expansion and paper-review model URLs
to use the same service. CPU generation can be slow. GPU passthrough is not
configured by these files.

Initialize the research collection before live retrieval:

```powershell
docker compose exec backend qubettera rag pipeline
docker compose exec backend qubettera rag retrieve "mixture of experts routing" --top-k 5
```

If `data/` already contains the required collected corpus, use
`qubettera rag pipeline --skip-collection`. Fake discussion mode is available
immediately for an interface/orchestration check; analytics requires live opinions.

## Validate before publishing

```powershell
python scripts/docker-smoke.py --namespace nada123456aa --tag 0.1.0
```

Use the namespace/tag built above (`qubettera-local:latest` defaults when those
settings are absent). The test starts a unique Compose project with empty data
volumes and random localhost ports. It checks health, the frontend proxy, a full
fake discussion, transcript persistence after restart, pgvector, CLI availability,
non-root write permissions, CPU PyTorch, and Chromium. It removes only its own
test containers and volumes. It does not read your model credentials or mount
your data directories. Live inference and model downloads are separate checks.

## Publish to Docker Hub

Create the two repositories under your Docker Hub account or organization, with
your chosen visibility. Authenticate locally; do not put registry credentials in
`.env`, Dockerfiles, or Git:

```powershell
docker login
.\scripts\publish-docker.ps1 -Namespace nada123456aa -Tag 0.1.0 -Push
```

The script builds both images, runs the isolated smoke checks, then pushes only
the two application images. Without `-Push`, it builds and tests only. Python 3.11+
is needed for the smoke runner, but no host Python packages are required.
The script uses `.venv/Scripts/python.exe` when present.

Equivalent manual commands (after successful checks):

```powershell
$env:DOCKERHUB_NAMESPACE = "nada123456aa"
$env:IMAGE_TAG = "0.1.0"
docker compose build backend frontend
python scripts/docker-smoke.py --namespace nada123456aa --tag 0.1.0
docker compose push backend frontend
```

Use a new version tag for each release. Builds use the Docker host's architecture;
the tested default target is Linux amd64. These commands do not claim multi-platform
support. The npm dependency lock is used, while Python dependency ranges resolve
at build time; preserve published release tags for repeatable deployments.

## Run published images on another computer

Copy only `docker-compose.yml`, `docker-compose.hub.yml`, and `.env.example` to
the deployment directory. Create/edit `.env` with the namespace, published tag,
database password, and model settings. No source checkout or build is needed:

```powershell
docker compose -f docker-compose.yml -f docker-compose.hub.yml pull
docker compose -f docker-compose.yml -f docker-compose.hub.yml up -d --no-build --wait --wait-timeout 180
```

For containerized generation, also copy `docker-compose.ollama.yml` and append
`-f docker-compose.ollama.yml` to both commands; allow a longer first-start timeout.

The Hub override removes builds and host database/API ports, and stores research
data and outputs in named volumes. The UI binds to localhost by default. There is
no application authentication: remote access needs an authenticated HTTPS reverse
proxy with SSE buffering disabled and long request timeouts. Set
`WEB_BIND_ADDRESS` deliberately for your hosting network.

The new host starts with an empty database. Run the corpus pipeline through
`docker compose -f docker-compose.yml -f docker-compose.hub.yml exec backend ...`,
or restore your existing database and data backups. Pulling an image never copies
your local corpus or history. Health checks verify service/code readiness, not
whether external inference is reachable or the corpus is populated.

## Operations

```powershell
docker compose logs -f --tail 100 backend frontend
docker compose stop
docker compose up -d --wait
```

Use the same `-f` arguments for all commands on a Hub/Ollama deployment. Keep one
backend worker; analytics job coordination is process-local. Running jobs do not
survive a backend restart, but saved transcripts/reports persist. Back up the
database, data, and outputs before upgrades. `docker compose down` retains named
volumes; adding `--volumes` deletes them and should not be used for normal upgrades.

References: [Docker Hub publishing](https://docs.docker.com/docker-hub/repos/manage/hub-images/push/),
[Compose override rules](https://docs.docker.com/reference/compose-file/merge/),
and [Playwright container dependencies](https://playwright.dev/python/docs/docker).
