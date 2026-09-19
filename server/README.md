# Server — ELSA Real-Time Quiz

FastAPI + WebSocket backend for the real-time quiz. See [`../design/SYSTEM_DESIGN.md`](../design/SYSTEM_DESIGN.md) for the full architecture and [`../design/adr/`](../design/adr/) for the key design decisions.

## Requirements

- Python 3.11+

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

## Run

```bash
uvicorn app.main:app --reload
```

The server listens on `http://localhost:8000`. Health check: `GET /healthz`. Metrics (Prometheus format): `GET /metrics`. WebSocket endpoint: `ws://localhost:8000/ws/{quiz_id}`.

## Test

```bash
pytest -q
```

Runs unit tests (scoring, session state machine, concurrency/idempotency) and an integration test that drives the real FastAPI app through a full join -> start -> answer -> quiz_end flow with multiple simulated WebSocket clients.

## Lint & type-check

```bash
ruff check app scripts tests
mypy app
```

## Load test (manual, not run in CI)

With the server running in one terminal:

```bash
python scripts/load_test.py --clients 300
```

Simulates N concurrent WebSocket clients joining one quiz room and answering, and reports answer-ack latency percentiles and leaderboard broadcast fan-out spread. Add `--stagger-ms 300` to spread answers over a window instead of a fully-synchronized burst (the synchronized case is a deliberate worst-case stress test, not the expected real-world pattern). See "Capacity" in `../design/SYSTEM_DESIGN.md` for measured results and how to read them.

## Docker

```bash
docker build -t elsa-quiz-server .
docker run -p 8000:8000 elsa-quiz-server
```

Or use `docker compose up` from the repo root to run both the server and client together.

## Project layout

```
app/
  main.py               FastAPI app, WebSocket endpoint, /healthz, /metrics
  schemas.py             Versioned WebSocket message protocol (Pydantic)
  quiz.py                QuizSession state machine, scoring integration
  scoring.py              Scoring formula, leaderboard ranking (pure functions)
  session_store.py        SessionStore interface + InMemorySessionStore
  connection_manager.py   WebSocket registry, broadcast, rate limiting, idle reaping
  observability.py        Structured logging + Prometheus metrics
scripts/
  load_test.py            Manual load test (see above)
tests/
  test_scoring.py          Unit tests: scoring, tie-break
  test_session.py          Unit tests: state machine, concurrency, idempotency
  test_integration_ws.py   Integration test: full flow, real WebSocket clients
```
