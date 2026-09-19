# Client — ELSA Real-Time Quiz

Vue 3 + TypeScript + Pinia frontend for the real-time quiz. See [`../design/SYSTEM_DESIGN.md`](../design/SYSTEM_DESIGN.md) for the full architecture.

## Requirements

- Node.js 22+

## Setup

```bash
npm install
```

> If `npm install` fails with `Cannot read properties of null (reading 'edgesOut')`, that is a known npm-version/arborist peer-dependency resolution issue unrelated to this project; `npm install --legacy-peer-deps` works around it.

## Configure

Copy `.env.example` to `.env.local` and point it at the running server:

```
VITE_WS_BASE_URL=ws://localhost:8000
```

If unset, it defaults to `ws://<current-hostname>:8000`.

## Run

```bash
npm run dev
```

Opens on `http://localhost:5173`. The server must be running separately (see `../server/README.md`) — this app does not run without it, by design (no mocked backend on the client side; the mock is the question bank on the server, per the challenge scope).

## Test / lint / type-check / build

```bash
npm run lint
npm run type-check
npm run build
```

`npm run test:unit -- --run` runs the Vitest store tests. `npm run test:e2e` drives a real browser through the full flow (needs the server on :8000, `npm run dev` on :5173, and Chrome or Edge installed; set `E2E_CHANNEL=msedge` to use Edge). It takes about 90 seconds because it plays a whole quiz.

## Project layout

```
src/
  types/protocol.ts            WebSocket message protocol types (mirrors server/app/schemas.py)
  composables/useQuizSocket.ts  Connection lifecycle: connect, reconnect+backoff, heartbeat, rejoin
  stores/quiz.ts                 Pinia store: single source of truth for quiz UI state
  components/
    QuestionCard.vue              Question, lettered answer cards, countdown ring, answer feedback
    LeaderboardPanel.vue           Live-ranked standings with medals, score bars and move animation
    ScoreBadge.vue                 Current user's avatar, score and rank
    UserAvatar.vue                 Deterministic coloured initial avatar
    PodiumBoard.vue                Top-3 podium on the results screen
    ConnectionStatus.vue           Connected / reconnecting / disconnected indicator
  views/
    JoinView.vue                   Quiz ID + name entry
    QuizRoomView.vue               Lobby / in-progress / finished, composed from the components above
  App.vue                         Switches between JoinView and QuizRoomView based on store.phase
```

## Design

The visual language follows ELSA's own site: deep indigo `#2b1b93`, navy `#171f48` text, soft blue `#5f94cf` accent, white surfaces, rounded cards and a motivational tone. Tokens live in `src/assets/main.css` (light and dark via `prefers-color-scheme`); animations honour `prefers-reduced-motion`; layouts collapse to one column under 860px.
