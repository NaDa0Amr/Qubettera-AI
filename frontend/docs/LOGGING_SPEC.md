# Backend Logging Specification

**For:** Task 2 owner (Youssef — FastAPI backend)  
**From:** Task 1 owner (Frontend — Next.js)  
**Purpose:** Ensure backend logs are machine-parseable and correlate with frontend request IDs.

---

## Format

All log entries must be emitted to **stdout** as **newline-delimited JSON (NDJSON)**.  
Do not use Python's default `%(levelname)s %(message)s` plaintext format in production.  
Use `structlog` or a custom `logging.Formatter` that serializes to JSON.

---

## Required Fields

Every log line must contain these fields:

| Field | Type | Example | Description |
|---|---|---|---|
| `timestamp` | ISO 8601 string | `"2026-09-21T20:30:12.123Z"` | UTC timestamp |
| `level` | string | `"INFO"` | `INFO`, `WARN`, `ERROR`, `DEBUG` |
| `service` | string | `"fastapi"` | Constant identifier for the backend service |
| `event` | string | `"request_started"` | Machine-readable event slug (snake_case) |
| `message` | string | `"POST /week3/discuss accepted"` | Human-readable description |

---

## Optional Contextual Fields

Include these when available:

| Field | Type | Description |
|---|---|---|
| `request_id` | string (UUID) | Injected by middleware on every request |
| `discussion_id` | string (UUID) | Present for all discussion-related events |
| `agent_id` | string | Persona ID (e.g. `"dr_aris"`) |
| `round` | integer | Discussion round number |
| `duration_ms` | integer | Wall-clock duration of the operation |
| `error` | string | Full error message or traceback summary |
| `status_code` | integer | HTTP response status |
| `path` | string | Request path |
| `method` | string | HTTP method |

---

## Required Events

Implement logging at these boundaries:

### Application Lifecycle

```json
{"timestamp":"...","level":"INFO","service":"fastapi","event":"app_started","message":"FastAPI application started","version":"0.1.0"}
```

### Request Middleware

Inject `request_id` (UUID v4) into every request via middleware. Log at entry and exit:

```json
{"timestamp":"...","level":"INFO","service":"fastapi","event":"request_started","message":"POST /week3/discuss","method":"POST","path":"/week3/discuss","request_id":"a3f9..."}
{"timestamp":"...","level":"INFO","service":"fastapi","event":"request_completed","message":"POST /week3/discuss 200","status_code":200,"duration_ms":123,"request_id":"a3f9..."}
{"timestamp":"...","level":"ERROR","service":"fastapi","event":"request_failed","message":"POST /week3/discuss 500","status_code":500,"duration_ms":45,"error":"...","request_id":"a3f9..."}
```

### Discussion Events

```json
{"timestamp":"...","level":"INFO","service":"fastapi","event":"discussion_started","message":"Discussion a3f9... started","discussion_id":"a3f9...","participant_ids":["dr_aris","prof_elena"],"num_rounds":3}
{"timestamp":"...","level":"INFO","service":"fastapi","event":"discussion_turn_completed","message":"Turn completed","discussion_id":"a3f9...","agent_id":"dr_aris","round":1,"sequence_number":5}
{"timestamp":"...","level":"INFO","service":"fastapi","event":"discussion_completed","message":"Discussion completed","discussion_id":"a3f9...","message_count":16,"duration_ms":312000}
{"timestamp":"...","level":"ERROR","service":"fastapi","event":"discussion_failed","message":"Discussion failed","discussion_id":"a3f9...","error":"LLM call timed out"}
```

### Analytics Events

```json
{"timestamp":"...","level":"INFO","service":"fastapi","event":"analytics_started","message":"Analytics started","discussion_id":"a3f9..."}
{"timestamp":"...","level":"INFO","service":"fastapi","event":"analytics_metric_completed","message":"opinion_change computed","discussion_id":"a3f9...","metric":"opinion_change","duration_ms":45210}
{"timestamp":"...","level":"INFO","service":"fastapi","event":"analytics_completed","message":"All metrics complete","discussion_id":"a3f9...","total_duration_ms":61234}
```

### LLM / Retrieval Failures

```json
{"timestamp":"...","level":"ERROR","service":"fastapi","event":"llm_call_failed","message":"LLM call failed after 3 retries","discussion_id":"a3f9...","agent_id":"dr_aris","round":2,"error":"rate_limit_exceeded"}
{"timestamp":"...","level":"WARN","service":"fastapi","event":"retrieval_failed","message":"Knowledge base retrieval failed, continuing without evidence","discussion_id":"a3f9...","agent_id":"prof_elena"}
```

---

## Python Implementation Reference

```python
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "fastapi",
            "event": getattr(record, "event", record.getMessage().split()[0].lower()),
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in {"name","msg","args","levelname","levelno","pathname",
                           "filename","module","exc_info","exc_text","stack_info",
                           "lineno","funcName","created","msecs","relativeCreated",
                           "thread","threadName","processName","process","message","taskName"}:
                log[key] = value
        return json.dumps(log)

# Apply in setup_logging():
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.root.addHandler(handler)
logging.root.setLevel(logging.INFO)
```

---

## Docker Commands for Log Inspection

```bash
# Stream Next.js logs (raw JSON)
docker compose logs -f nextjs

# Stream FastAPI logs, extract timestamp and event
docker compose logs -f fastapi | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        obj = json.loads(line)
        print(obj.get('timestamp',''), obj.get('level',''), obj.get('event',''), obj.get('message',''))
    except:
        print(line.rstrip())
"

# Aggregate health check
curl -s http://localhost:3000/api/health | python3 -m json.tool

# Filter discussion events
docker compose logs fastapi | grep '"discussion_id"'

# Watch analytics completion
docker compose logs -f fastapi | grep '"event":"analytics_metric_completed"'
```

---

## Notes

- The `request_id` header should be echoed back to the client as `X-Request-Id` so the frontend can correlate its own logs.
- Do not log LLM response content at INFO level — it may contain PII or sensitive prompts. Log only metadata (token counts, latency, model).
- Discussion transcript content is written to disk at `WEEK3_OUTPUT_DIR/{discussion_id}.jsonl` — this is the source of truth for `/week4/analytics`, not logs.
