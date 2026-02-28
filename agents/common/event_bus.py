"""
ZeroMQ Event Bus for TradeBot
=============================

Provides real-time push notifications between agents using ZeroMQ
PUB/SUB sockets routed through a central XSUB/XPUB proxy.

This is a **notification layer only** — the SQLite database remains
the source of truth for all queryable state.  If the proxy is not
running, agents gracefully fall back to their existing polling loops.

Usage — Publisher (e.g. Crypto Liquidation Agent)::

    from agents.common.event_bus import EventPublisher, TOPIC_LIQUIDATION_CASCADE

    pub = EventPublisher()
    pub.publish(TOPIC_LIQUIDATION_CASCADE, {"symbol": "BTCUSDT", "usd": 5_200_000})
    pub.close()

Usage — Subscriber (e.g. Manager Orchestrator)::

    from agents.common.event_bus import EventSubscriber, TOPIC_LIQUIDATION_CASCADE

    sub = EventSubscriber(topics=[TOPIC_LIQUIDATION_CASCADE])
    msg = sub.listen_sync(timeout_ms=5000)  # blocks up to 5 s
    if msg:
        topic, payload = msg
        print(f"Received {topic}: {payload}")
    sub.close()

Architecture::

    Publishers ──► [XSUB :5555] ── PROXY ── [XPUB :5556] ──► Subscribers
"""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator, Optional

logger = logging.getLogger("tradebot.event_bus")

# ---------------------------------------------------------------------------
# Default proxy endpoints (localhost-only for single-machine deployment)
# ---------------------------------------------------------------------------
DEFAULT_PUB_ADDRESS = "tcp://127.0.0.1:5555"   # publishers connect here (XSUB)
DEFAULT_SUB_ADDRESS = "tcp://127.0.0.1:5556"   # subscribers connect here (XPUB)

# ---------------------------------------------------------------------------
# Topic Constants
#
# Convention:  CATEGORY.SUBCATEGORY
# Subscribers can use a prefix to catch an entire category, e.g.
#   subscribe("NEWS")  will receive both NEWS.CRITICAL and NEWS.HIGH.
# ---------------------------------------------------------------------------
TOPIC_CIRCUIT_BREAKER       = "CIRCUIT_BREAKER"
TOPIC_POLICY_SWITCH         = "POLICY.SWITCH"
TOPIC_NEWS_CRITICAL         = "NEWS.CRITICAL"
TOPIC_NEWS_HIGH             = "NEWS.HIGH"
TOPIC_LIQUIDATION_CASCADE   = "LIQUIDATION.CASCADE"
TOPIC_WHALE_CLUSTER         = "WHALE.CLUSTER"
TOPIC_STRATEGY_UPDATE       = "STRATEGY.UPDATE"
TOPIC_TRADE_EXECUTED        = "TRADE.EXECUTED"
TOPIC_TRADE_FAILED          = "TRADE.FAILED"
TOPIC_PORTFOLIO_ALERT       = "PORTFOLIO.ALERT"
TOPIC_BACKTEST_FAILED       = "BACKTEST.FAILED"
TOPIC_NEWS_SENTIMENT_SHIFT  = "NEWS.SENTIMENT_SHIFT"

# Collect all topics for programmatic listing
ALL_TOPICS = [
    TOPIC_CIRCUIT_BREAKER,
    TOPIC_POLICY_SWITCH,
    TOPIC_NEWS_CRITICAL,
    TOPIC_NEWS_HIGH,
    TOPIC_NEWS_SENTIMENT_SHIFT,
    TOPIC_LIQUIDATION_CASCADE,
    TOPIC_WHALE_CLUSTER,
    TOPIC_STRATEGY_UPDATE,
    TOPIC_TRADE_EXECUTED,
    TOPIC_TRADE_FAILED,
    TOPIC_PORTFOLIO_ALERT,
    TOPIC_BACKTEST_FAILED,
]


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------

class EventPublisher:
    """Publishes JSON-serializable events to the ZeroMQ proxy.

    Connects a PUB socket to the XSUB side of the proxy.
    All operations are wrapped in try/except so a missing proxy
    never crashes the calling agent.
    """

    def __init__(self, proxy_address: str = DEFAULT_PUB_ADDRESS) -> None:
        self._address = proxy_address
        self._socket = None
        self._context = None
        try:
            import zmq
            self._context = zmq.Context.instance()
            self._socket = self._context.socket(zmq.PUB)
            self._socket.setsockopt(zmq.LINGER, 0)
            self._socket.connect(self._address)
            # Short sleep to allow the connection to settle (slow-joiner
            # mitigation — the proxy handles the rest).
            time.sleep(0.1)
            logger.info("EventPublisher connected to %s", self._address)
        except ImportError:
            logger.warning(
                "pyzmq not installed — EventPublisher disabled.  "
                "Install with: pip install pyzmq"
            )
        except Exception as exc:
            logger.warning("EventPublisher failed to connect to %s: %s", self._address, exc)

    # ------------------------------------------------------------------
    def publish(self, topic: str, payload: dict) -> bool:
        """Send *payload* on *topic*.  Returns True on success."""
        if self._socket is None:
            return False
        try:
            message = json.dumps(payload, default=str)
            self._socket.send_string(f"{topic} {message}")
            logger.debug("Published [%s]: %s", topic, message[:120])
            return True
        except Exception as exc:
            logger.warning("EventPublisher.publish failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    def close(self) -> None:
        """Release the socket."""
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
            logger.debug("EventPublisher closed")


# ---------------------------------------------------------------------------
# Subscriber
# ---------------------------------------------------------------------------

class EventSubscriber:
    """Subscribes to one or more ZeroMQ topics from the proxy.

    Connects a SUB socket to the XPUB side of the proxy.

    Provides both **synchronous** (``listen_sync``) and **asynchronous**
    (``listen``) interfaces.
    """

    def __init__(
        self,
        topics: list[str] | None = None,
        proxy_address: str = DEFAULT_SUB_ADDRESS,
    ) -> None:
        self._address = proxy_address
        self._topics = topics or [""]  # empty string = subscribe to everything
        self._socket = None
        self._context = None
        self._async_socket = None
        try:
            import zmq
            self._zmq = zmq
            self._context = zmq.Context.instance()
            self._socket = self._context.socket(zmq.SUB)
            self._socket.setsockopt(zmq.LINGER, 0)
            self._socket.connect(self._address)
            for t in self._topics:
                self._socket.setsockopt_string(zmq.SUBSCRIBE, t)
            logger.info(
                "EventSubscriber connected to %s, topics=%s",
                self._address,
                self._topics,
            )
        except ImportError:
            logger.warning(
                "pyzmq not installed — EventSubscriber disabled.  "
                "Install with: pip install pyzmq"
            )
            self._zmq = None
        except Exception as exc:
            logger.warning("EventSubscriber failed to connect to %s: %s", self._address, exc)
            self._zmq = None

    # ------------------------------------------------------------------
    @staticmethod
    def _parse(raw: str) -> tuple[str, dict]:
        """Split a ``"TOPIC {json}"`` frame into (topic, payload)."""
        idx = raw.find(" ")
        if idx == -1:
            return raw, {}
        topic = raw[:idx]
        try:
            payload = json.loads(raw[idx + 1:])
        except json.JSONDecodeError:
            payload = {"_raw": raw[idx + 1:]}
        return topic, payload

    # ------------------------------------------------------------------
    def listen_sync(self, timeout_ms: int = 1000) -> Optional[tuple[str, dict]]:
        """Block for up to *timeout_ms* waiting for a message.

        Returns ``(topic, payload)`` or ``None`` on timeout / error.
        """
        if self._socket is None:
            return None
        try:
            if self._socket.poll(timeout_ms):
                raw = self._socket.recv_string()
                return self._parse(raw)
        except Exception as exc:
            logger.warning("EventSubscriber.listen_sync error: %s", exc)
        return None

    # ------------------------------------------------------------------
    def drain(self, max_messages: int = 100) -> list[tuple[str, dict]]:
        """Non-blocking drain of all pending messages (up to *max_messages*).

        Useful for the orchestrator sweep: grab everything queued, then
        process the DB.
        """
        messages: list[tuple[str, dict]] = []
        if self._socket is None:
            return messages
        try:
            for _ in range(max_messages):
                if self._socket.poll(0):
                    raw = self._socket.recv_string()
                    messages.append(self._parse(raw))
                else:
                    break
        except Exception as exc:
            logger.warning("EventSubscriber.drain error: %s", exc)
        return messages

    # ------------------------------------------------------------------
    async def listen(self) -> AsyncGenerator[tuple[str, dict], None]:
        """Async generator that yields ``(topic, payload)`` as they arrive.

        Requires ``zmq.asyncio`` — designed for agents that already run
        an asyncio event loop (e.g. CryptoLiquidationAgent).
        """
        if self._zmq is None:
            return
        try:
            import zmq.asyncio as azmq

            ctx = azmq.Context.instance()
            sock = ctx.socket(self._zmq.SUB)
            sock.setsockopt(self._zmq.LINGER, 0)
            sock.connect(self._address)
            for t in self._topics:
                sock.setsockopt_string(self._zmq.SUBSCRIBE, t)

            try:
                while True:
                    raw = await sock.recv_string()
                    yield self._parse(raw)
            finally:
                sock.close()
        except Exception as exc:
            logger.warning("EventSubscriber.listen (async) error: %s", exc)

    # ------------------------------------------------------------------
    def close(self) -> None:
        """Release the socket."""
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
            logger.debug("EventSubscriber closed")
