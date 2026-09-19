# ELSA Real-Time Quiz — Coding Challenge Submission

A real-time vocabulary quiz: users join a quiz session with a shared quiz ID, answer multiple-choice questions, and see scores and a leaderboard update live for everyone in the room.

This submission implements a **full-stack slice**: a real WebSocket server (FastAPI/Python) and a real client (Vue 3/TypeScript), with the question bank mocked (static in-memory data, no real content service) per the challenge's "implement one core component, mock the rest" scope.

## Where to look

| What | Where |
|---|---|
| System design (architecture, data flow, tech justification, capacity) | [`design/SYSTEM_DESIGN.md`](design/SYSTEM_DESIGN.md) |
| Key design decisions, with alternatives considered | [`design/adr/`](design/adr/) |
| AI collaboration (design + implementation) | [`AI_COLLABORATION.md`](AI_COLLABORATION.md) |
| Server (FastAPI + WebSocket) | [`server/`](server/), run instructions in [`server/README.md`](server/README.md) |
| Client (Vue 3 + Pinia) | [`client/`](client/), run instructions in [`client/README.md`](client/README.md) |

## Quickstart

**Option A — Docker (one command):**

```bash
docker compose up --build
```

Server on `http://localhost:8000`, client on `http://localhost:5173`.

**Option B — local dev, two terminals:**

```bash
# Terminal 1
cd server
python -m venv .venv && .venv\Scripts\activate   # or: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Terminal 2
cd client
npm install
npm run dev
```

Open `http://localhost:5173`, join a quiz ID (e.g. `demo-quiz`) with a username, open the same URL in a second tab with a different username, and click "Start quiz" from either tab.

## Verifying this submission

```bash
# Server: lint, types, tests
cd server && ruff check app scripts tests && mypy app && pytest -q

# Client: lint, types, build
cd client && npm run lint && npm run type-check && npm run build
```

Both are also run on every push via GitHub Actions (`.github/workflows/ci.yml`). For a real-load sanity check (not part of CI — see `server/README.md`):

```bash
cd server && python scripts/load_test.py --clients 300
```

## Submission checklist (per the challenge brief)

- [x] System Design Document — `design/SYSTEM_DESIGN.md` (architecture diagram, component descriptions, data flow, tech justification, AI collaboration in design)
- [x] Working code for one real-time component (implemented as a full-stack slice) — `server/`, `client/`
- [x] Scalability/performance/reliability/maintainability/observability addressed — see `design/SYSTEM_DESIGN.md` sections 6-8, and measured (not just claimed) load test results
- [x] AI collaboration documented for both design and implementation, with verification steps — `AI_COLLABORATION.md`
- [x] Instructions to run the code/tests — this file, `server/README.md`, `client/README.md`
- [ ] Video submission (5-10 minutes) — outside the scope of this repository; record separately per the challenge instructions

## Out of scope

Redis-backed multi-instance scaling, real authentication, durability past a server restart, and a full frontend e2e test suite were intentionally not implemented — each is documented with a reason in `design/SYSTEM_DESIGN.md` ("Out of scope") and, where relevant, an ADR describing the path to add it.
