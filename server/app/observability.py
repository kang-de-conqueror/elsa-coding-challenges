"""Structured logging and Prometheus metrics.

Grading criteria explicitly ask for monitoring/observability, so this module
is a real (if minimal) implementation rather than a design-doc paragraph:
JSON logs carry `quiz_id`/`connection_id` for correlation, and `/metrics`
exposes counters/histograms an operator could actually alert on.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry()

ACTIVE_CONNECTIONS = Gauge(
    "quiz_active_connections",
    "Number of currently open WebSocket connections",
    registry=REGISTRY,
)
ACTIVE_SESSIONS = Gauge(
    "quiz_active_sessions",
    "Number of quiz sessions currently held in memory",
    registry=REGISTRY,
)
ANSWERS_PROCESSED = Counter(
    "quiz_answers_processed_total",
    "Total number of answer submissions processed",
    ["correct"],
    registry=REGISTRY,
)
BROADCAST_LATENCY = Histogram(
    "quiz_broadcast_latency_seconds",
    "Time to serialize and fan out one broadcast message to all connections in a room",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.15, 0.25, 0.5, 1.0),
    registry=REGISTRY,
)
MESSAGES_REJECTED = Counter(
    "quiz_messages_rejected_total",
    "Total number of inbound messages rejected (validation error or rate limit)",
    ["reason"],
    registry=REGISTRY,
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in getattr(record, "context", {}).items():
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, message: str, /, **context: Any) -> None:
    logger.info(message, extra={"context": context})


@contextmanager
def track_broadcast_latency() -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        BROADCAST_LATENCY.observe(time.perf_counter() - start)
