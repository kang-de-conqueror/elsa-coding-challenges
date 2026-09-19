from __future__ import annotations

from app.connection_manager import ConnectionManager, RateLimiter
from app.schemas import PongMessage
from app.session_store import InMemorySessionStore


class FakeSocket:
    def __init__(self) -> None:
        self.closed = False
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def close(self, code: int = 1000) -> None:
        self.closed = True


def _register(manager: ConnectionManager, quiz_id: str, user_id: str, socket: FakeSocket) -> None:
    manager.register(quiz_id, user_id, socket)  # type: ignore[arg-type]


def test_rate_limiter_blocks_after_burst_is_exhausted() -> None:
    limiter = RateLimiter(max_tokens=2, refill_seconds=1000.0)
    assert limiter.allow("u") is True
    assert limiter.allow("u") is True
    assert limiter.allow("u") is False


def test_rate_limiter_tracks_keys_independently() -> None:
    limiter = RateLimiter(max_tokens=1, refill_seconds=1000.0)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False


def test_unregister_with_stale_socket_keeps_the_newer_socket() -> None:
    manager = ConnectionManager()
    old, new = FakeSocket(), FakeSocket()
    _register(manager, "room", "user", old)
    _register(manager, "room", "user", new)  # rejoin replaces the old socket

    assert manager.unregister("room", "user", old) is False  # type: ignore[arg-type]
    assert manager.unregister("room", "user", new) is True  # type: ignore[arg-type]


def test_unregister_unknown_connection_returns_false() -> None:
    assert ConnectionManager().unregister("room", "nobody") is False


async def test_reap_idle_connections_closes_and_unregisters_silent_sockets() -> None:
    manager = ConnectionManager(idle_timeout_seconds=-1.0)  # everything counts as idle
    socket = FakeSocket()
    _register(manager, "room", "user", socket)

    await manager.reap_idle_connections()

    assert socket.closed is True
    assert manager.unregister("room", "user") is False


async def test_touch_keeps_a_connection_from_being_reaped() -> None:
    manager = ConnectionManager(idle_timeout_seconds=60.0)
    socket = FakeSocket()
    _register(manager, "room", "user", socket)
    manager.touch("room", "user")

    await manager.reap_idle_connections()

    assert socket.closed is False


async def test_broadcast_survives_a_dead_socket() -> None:
    class DeadSocket(FakeSocket):
        async def send_text(self, text: str) -> None:
            raise RuntimeError("socket is gone")

    manager = ConnectionManager()
    healthy = FakeSocket()
    _register(manager, "room", "dead", DeadSocket())
    _register(manager, "room", "alive", healthy)

    await manager.broadcast("room", PongMessage())

    assert len(healthy.sent) == 1


async def test_session_store_remove_frees_the_session() -> None:
    store = InMemorySessionStore()
    await store.get_or_create("room", lambda: [])
    assert store.active_session_count() == 1

    await store.remove("room")
    await store.remove("room")  # removing twice is harmless

    assert await store.get("room") is None
    assert store.active_session_count() == 0

