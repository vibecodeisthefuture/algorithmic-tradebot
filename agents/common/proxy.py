"""
ZeroMQ XSUB/XPUB Proxy for TradeBot
====================================

Central message forwarder that decouples publishers from subscribers.

    Publishers ──► [XSUB :5555] ── PROXY ── [XPUB :5556] ──► Subscribers

Run standalone::

    py agents/common/proxy.py

Or start programmatically::

    from agents.common.proxy import start_proxy_thread
    thread = start_proxy_thread()   # returns immediately
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger("tradebot.proxy")

# Default bind addresses
XSUB_BIND = "tcp://127.0.0.1:5555"   # publishers connect here
XPUB_BIND = "tcp://127.0.0.1:5556"   # subscribers connect here


def run_proxy(
    xsub_bind: str = XSUB_BIND,
    xpub_bind: str = XPUB_BIND,
) -> None:
    """Run a blocking XSUB/XPUB proxy (never returns under normal use).

    Call this in a dedicated thread or process.
    """
    import zmq

    ctx = zmq.Context.instance()
    xsub = ctx.socket(zmq.XSUB)
    xpub = ctx.socket(zmq.XPUB)

    xsub.bind(xsub_bind)
    xpub.bind(xpub_bind)

    logger.info(
        "ZeroMQ proxy started — XSUB=%s  XPUB=%s", xsub_bind, xpub_bind
    )
    print(f"✅ ZeroMQ proxy running  XSUB={xsub_bind}  XPUB={xpub_bind}")
    print("   Press Ctrl+C to stop.")

    try:
        zmq.proxy(xsub, xpub)
    except zmq.ContextTerminated:
        logger.info("ZeroMQ proxy terminated (context closed)")
    finally:
        xsub.close()
        xpub.close()


def start_proxy_thread(
    xsub_bind: str = XSUB_BIND,
    xpub_bind: str = XPUB_BIND,
) -> Optional[threading.Thread]:
    """Start the proxy in a daemon thread and return it immediately.

    Returns ``None`` if pyzmq is not installed.
    """
    try:
        import zmq  # noqa: F401  — verify importable
    except ImportError:
        logger.warning("pyzmq not installed — proxy not started")
        return None

    t = threading.Thread(
        target=run_proxy,
        args=(xsub_bind, xpub_bind),
        name="zmq-proxy",
        daemon=True,
    )
    t.start()
    return t


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    )
    try:
        run_proxy()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
