# ADR 0001: WebSocket as the real-time transport

## Status

Accepted

## Context

The quiz needs three real-time behaviors: participants joining a room, live score updates as answers are submitted, and a live leaderboard. All three are bidirectional (client submits answers; server pushes questions, scores, and leaderboard updates without the client polling) and latency-sensitive (the leaderboard should feel instant).

Candidate transports:

- **WebSocket** — full-duplex, single persistent TCP connection per client, native browser API, first-class support in FastAPI/Starlette.
- **Server-Sent Events (SSE)** — simple, HTTP-native, auto-reconnecting, but one-directional (server -> client only); answer submission would still need a separate HTTP POST per answer.
- **Socket.IO** — adds automatic reconnection, room abstraction, and long-polling fallback on top of WebSocket, at the cost of a non-standard protocol and a required client library; most valuable when IE11-class fallback or very old proxies are a concern.
- **Polling** — simplest to implement, but a fixed poll interval directly trades off against perceived latency and wastes requests when nothing changed; the whole point of the challenge is real-time updates.

## Decision

Use plain WebSocket, one connection per client, one endpoint (`/ws/{quiz_id}`) per quiz room. FastAPI's native WebSocket support removes the need for a second transport (SSE) just to receive answers, and the browser's built-in `WebSocket` API means the client needs no extra runtime dependency. Reconnection and heartbeat (ping/pong) are implemented at the application-message level instead of relying on a framework like Socket.IO (see `connection_manager.py` and `client/src/composables/useQuizSocket.ts`), since the fallback-transport features Socket.IO adds are not a requirement for this challenge's target clients (modern browsers).

## Consequences

- Simpler stack: no separate Socket.IO server/client dependency, one protocol to reason about and test.
- We own reconnection/backoff and idle-connection detection ourselves (implemented, not outsourced to a library) — more code, but fully under test and easy to explain in the design document.
- No automatic fallback to long-polling for clients/networks that cannot hold a WebSocket open (e.g. some restrictive corporate proxies). Acceptable for this challenge's scope; would be revisited if that user segment mattered in production.
- The message protocol (see `server/app/schemas.py`) is a JSON envelope with a `type` discriminator and a `v` version field from day one, so the protocol can evolve without breaking older clients mid-rollout.
