import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const fixtures = JSON.parse(await readFile(new URL("../lib/mocks/personas.json", import.meta.url), "utf8"));
let unavailable = false;
let discussions = [];
const backend = createServer((request, response) => {
  response.setHeader("Content-Type", "application/json");
  if (unavailable) {
    response.writeHead(503).end(JSON.stringify({ error: "unavailable" }));
  } else if (request.url === "/personas") {
    response.end(JSON.stringify(fixtures.personas));
  } else if (request.url === "/discussions") {
    response.end(JSON.stringify(discussions));
  } else {
    response.writeHead(404).end("{}");
  }
});
backend.listen(0, "127.0.0.1");
await once(backend, "listening");

// Allocate an ephemeral port for the production frontend.
const reservation = createServer();
reservation.listen(0, "127.0.0.1");
await once(reservation, "listening");
const port = reservation.address().port;
await new Promise((resolve) => reservation.close(resolve));
const base = `http://127.0.0.1:${port}`;
const child = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", String(port)], {
  cwd: root,
  windowsHide: true,
  env: {
    ...process.env,
    FASTAPI_INTERNAL_URL: `http://127.0.0.1:${backend.address().port}`,
    MOCK_BACKEND: "false",
  },
  stdio: ["ignore", "pipe", "pipe"],
});
let output = "";
let startupError;
child.on("error", (error) => { startupError = error; });
child.stdout.on("data", (chunk) => { output += chunk; });
child.stderr.on("data", (chunk) => { output += chunk; });
const request = (path) => fetch(`${base}${path}`, { redirect: "manual", signal: AbortSignal.timeout(15_000) });

try {
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    if (startupError) throw startupError;
    if (child.exitCode !== null) throw new Error(`Frontend exited: ${output}`);
    try {
      if ((await request("/api/personas")).ok) { ready = true; break; }
    } catch { /* Wait for the server to bind its port. */ }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  assert.ok(ready, `Frontend did not become ready: ${output}`);
  assert.deepEqual(await (await request("/api/personas")).json(), fixtures);
  assert.deepEqual(await (await request("/api/discussions")).json(), { discussions: [] });
  assert.match(await (await request("/analytics")).text(), /No saved analytics yet/);
  const home = await (await request("/")).text();
  assert.match(home, /Skip to content/);
  assert.match(home, new RegExp(fixtures.personas[0].name));

  discussions = [
    { discussion_id: "older", status: "completed", has_analytics: true, created_at: "2026-01-01T00:00:00Z" },
    { discussion_id: "latest", status: "completed", has_analytics: true, created_at: "2026-02-01T00:00:00Z" },
    { discussion_id: "running", status: "running", has_analytics: false, created_at: "2026-03-01T00:00:00Z" },
  ];
  const analytics = await request("/analytics");
  assert.equal(analytics.status, 307);
  assert.equal(analytics.headers.get("location"), "/analytics/latest");

  unavailable = true;
  for (const path of ["/api/personas", "/api/discussions"]) {
    const response = await request(path);
    assert.equal(response.status, 502);
    assert.ok((await response.json()).error);
  }
  assert.match(await (await request("/analytics")).text(), /temporarily unavailable/);
  assert.match(await (await request("/")).text(), /Personas are temporarily unavailable/);
  console.log("Frontend smoke checks passed: collections, empty state, analytics redirect, and backend failures.");
} finally {
  if (child.exitCode === null && !startupError) {
    const exited = once(child, "exit");
    child.kill();
    await exited;
  }
  backend.closeAllConnections();
  await new Promise((resolve) => backend.close(resolve));
}
