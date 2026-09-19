#!/usr/bin/env python
"""Manual load test: simulate N concurrent WebSocket clients in one quiz room.

Not run in CI -- it is a sanity check against the latency NFR stated in
design/SYSTEM_DESIGN.md (p95 broadcast fan-out < 150ms on localhost), meant
to be run by hand against a live server:

    uvicorn app.main:app &
    python scripts/load_test.py --clients 300

It reports two numbers that avoid comparing clocks across machines/processes
(server vs. client clocks are never assumed to be in sync):

- answer round-trip time: per client, time from sending its own answer to
  receiving its own score_update ack (self-referential, no clock sync needed).
- leaderboard fan-out spread: for one leaderboard broadcast, the spread
  between the first and last client to receive it (all client-side
  timestamps, so only relative skew between clients matters, not absolute
  time).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time

import websockets


async def _run_client(
    uri: str,
    quiz_id: str,
    username: str,
    is_starter: bool,
    joined_barrier: asyncio.Barrier,
    rtts_ms: list[float],
    leaderboard_recv_times: list[float],
    stagger_ms: float,
) -> None:
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "join", "quiz_id": quiz_id, "username": username}))
        user_id = ""
        while not user_id:
            msg = json.loads(await ws.recv())
            if msg["type"] == "joined":
                user_id = msg["user_id"]

        # Every client must have joined before anyone starts the quiz, or
        # late joiners get rejected with QUIZ_ALREADY_STARTED.
        await joined_barrier.wait()
        if is_starter:
            await ws.send(json.dumps({"type": "start", "quiz_id": quiz_id}))

        question_id = ""
        while not question_id:
            msg = json.loads(await ws.recv())
            if msg["type"] == "question":
                question_id = msg["question_id"]

        if stagger_ms > 0:
            # Real users don't answer in perfect lockstep; spread submissions
            # over a random window to approximate human reaction-time jitter
            # instead of the pathological fully-synchronized worst case.
            await asyncio.sleep(random.uniform(0, stagger_ms) / 1000)

        send_ts = time.perf_counter()
        await ws.send(
            json.dumps(
                {
                    "type": "answer",
                    "request_id": f"{user_id}-{question_id}",
                    "question_id": question_id,
                    "choice_index": 0,
                }
            )
        )

        got_ack = False
        got_leaderboard = False
        while not (got_ack and got_leaderboard):
            msg = json.loads(await ws.recv())
            if msg["type"] == "score_update" and not got_ack:
                rtts_ms.append((time.perf_counter() - send_ts) * 1000)
                got_ack = True
            elif msg["type"] == "leaderboard" and not got_leaderboard:
                leaderboard_recv_times.append(time.perf_counter())
                got_leaderboard = True


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--clients", type=int, default=300)
    parser.add_argument("--quiz-id", default="load-test")
    parser.add_argument(
        "--stagger-ms",
        type=float,
        default=0.0,
        help="Randomize each client's answer over this many ms (0 = fully synchronized worst case).",
    )
    args = parser.parse_args()

    uri = f"ws://{args.host}:{args.port}/ws/{args.quiz_id}"
    rtts_ms: list[float] = []
    leaderboard_recv_times: list[float] = []

    joined_barrier = asyncio.Barrier(args.clients)
    tasks = [
        _run_client(
            uri,
            args.quiz_id,
            f"loadtest-{i}",
            is_starter=(i == 0),
            joined_barrier=joined_barrier,
            rtts_ms=rtts_ms,
            leaderboard_recv_times=leaderboard_recv_times,
            stagger_ms=args.stagger_ms,
        )
        for i in range(args.clients)
    ]
    started_at = time.perf_counter()
    await asyncio.gather(*tasks)
    wall_clock_seconds = time.perf_counter() - started_at

    spread_ms = float("nan")
    if leaderboard_recv_times:
        spread_ms = (max(leaderboard_recv_times) - min(leaderboard_recv_times)) * 1000

    print(f"clients={args.clients} total_wall_clock_seconds={wall_clock_seconds:.2f}")
    print(
        "answer_ack_rtt_ms: "
        f"p50={_percentile(rtts_ms, 50):.1f} p95={_percentile(rtts_ms, 95):.1f} "
        f"p99={_percentile(rtts_ms, 99):.1f} max={max(rtts_ms):.1f}"
    )
    print(f"leaderboard_fanout_spread_ms={spread_ms:.1f} (max-min receipt time across all clients)")
    print(f"mean_rtt_ms={statistics.fmean(rtts_ms):.1f}")


if __name__ == "__main__":
    asyncio.run(main())
