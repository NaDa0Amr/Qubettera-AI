"""Validate built images against an isolated database; remove only test resources."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="qubettera-local")
    parser.add_argument("--tag", default="latest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    project = "qubettera-smoke-" + uuid.uuid4().hex[:10]
    env = {**os.environ, "DOCKERHUB_NAMESPACE": args.namespace, "IMAGE_TAG": args.tag}
    command = ["docker", "compose", "--env-file", ".env.example", "-p", project,
               "-f", "docker-compose.yml", "-f", "docker-compose.hub.yml",
               "-f", "docker-compose.smoke.yml"]

    def compose(*arguments, capture=False):
        return subprocess.run(command + list(arguments), cwd=root, env=env,
                              check=True, text=True, capture_output=capture).stdout

    def request(base, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(base + path, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.read().decode(), response.headers

    try:
        compose("config", "--quiet")
        compose("pull", "--policy", "missing", "postgres")
        compose("up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "180")
        api = "http://" + compose("port", "backend", "8000", capture=True).strip()
        web = "http://" + compose("port", "frontend", "3000", capture=True).strip()
        health = json.loads(request(web, "/api/health")[0])
        assert health["backend"] == "ok" and health["backend_ready"], health
        personas = json.loads(request(web, "/api/personas")[0])["personas"]
        assert len(personas) >= 2
        stream, headers = request(web, "/api/week3/discuss", {
            "topic": "Docker integration smoke test", "mode": "fake", "num_rounds": 3,
            "participant_ids": [persona["id"] for persona in personas[:2]],
        })
        assert "event: discussion_completed" in stream, stream
        assert "event: discussion_failed" not in stream, stream
        discussion_id = headers["x-discussion-id"]
        detail = json.loads(request(web, f"/api/discussions/{discussion_id}")[0])
        assert detail["status"] == "completed", detail
        history = json.loads(request(web, "/api/discussions")[0])["discussions"]
        assert any(item["discussion_id"] == discussion_id for item in history)
        assert "Skip to content" in request(web, "/")[0]
        compose("exec", "-T", "postgres", "psql", "-U", "smoke", "-d", "smoke",
                "-v", "ON_ERROR_STOP=1", "-c", "CREATE EXTENSION IF NOT EXISTS vector;")
        compose("exec", "-T", "backend", "qubettera", "--help")
        compose("exec", "-T", "backend", "python", "-c",
                "from sentence_transformers import SentenceTransformer; "
                "from transformers import pipeline; "
                "import qubettera.analytics.engine; import qubettera.rag.embed; "
                "print('Retrieval and analytics dependencies imported successfully')")
        compose("exec", "-T", "backend", "python", "-c",
                "import os, pathlib, torch; assert os.getuid() != 0; "
                "assert torch.version.cuda is None; "
                "assert pathlib.Path('/app/resources/personas/personas.json').is_file(); "
                "pathlib.Path('/app/data/smoke-write').write_text('ok'); "
                "pathlib.Path('/app/.cache/huggingface/smoke-write').write_text('ok')")
        compose("exec", "-T", "backend", "python", "-c",
                "from playwright.sync_api import sync_playwright; "
                "p=sync_playwright().start(); b=p.chromium.launch(headless=True, args=['--no-sandbox']); "
                "page=b.new_page(); page.set_content('<title>smoke</title>'); "
                "assert page.title() == 'smoke'; b.close(); p.stop()")
        # A container restart must preserve the transcript on its named volume.
        compose("restart", "backend")
        compose("up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "120")
        api = "http://" + compose("port", "backend", "8000", capture=True).strip()
        assert json.loads(request(api, f"/discussions/{discussion_id}")[0])["status"] == "completed"
        print("PASS: health, UI proxy, fake discussion, history persistence, pgvector, CLI, CPU runtime, Chromium.")
    except Exception:
        compose("logs", "--no-color", "--tail", "80")
        raise
    finally:
        # The unique project owns all these volumes; real project data is never mounted.
        compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
