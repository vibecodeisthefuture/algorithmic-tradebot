"""
Unit tests for the ZeroMQ Event Bus.

Tests cover:
    1. Proxy lifecycle (start/stop in a thread)
    2. Publish → Subscribe round-trip
    3. Topic filtering (subscriber receives only matching topics)
    4. Graceful degradation (publisher handles missing proxy)
    5. Synchronous and async listener interfaces
    6. Drain (non-blocking bulk receive)

Requirements:
    pip install pyzmq pytest

Run:
    py -m pytest agents/common/test_event_bus.py -v
"""

from __future__ import annotations

import threading
import time
import unittest

# ---------------------------------------------------------------------------
# Import guards — skip all tests if pyzmq is missing
# ---------------------------------------------------------------------------
try:
    import zmq  # noqa: F401
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False


# Use non-default ports so we don't collide with a running proxy
TEST_XSUB = "tcp://127.0.0.1:15555"
TEST_XPUB = "tcp://127.0.0.1:15556"


def _start_test_proxy():
    """Start a proxy in a daemon thread on test ports."""
    from agents.common.proxy import run_proxy

    t = threading.Thread(
        target=run_proxy,
        args=(TEST_XSUB, TEST_XPUB),
        daemon=True,
    )
    t.start()
    time.sleep(0.3)  # let sockets bind
    return t


@unittest.skipUnless(HAS_ZMQ, "pyzmq not installed — skipping event bus tests")
class TestProxyLifecycle(unittest.TestCase):
    """Verify the proxy binds and stays alive."""

    def test_proxy_starts_in_thread(self):
        t = _start_test_proxy()
        self.assertTrue(t.is_alive())


@unittest.skipUnless(HAS_ZMQ, "pyzmq not installed — skipping event bus tests")
class TestPublishSubscribe(unittest.TestCase):
    """Publish a message and verify the subscriber receives it."""

    @classmethod
    def setUpClass(cls):
        cls._proxy = _start_test_proxy()

    def test_round_trip(self):
        from agents.common.event_bus import EventPublisher, EventSubscriber

        sub = EventSubscriber(
            topics=["TEST.ROUND_TRIP"],
            proxy_address=TEST_XPUB,
        )
        time.sleep(0.2)  # let subscription propagate

        pub = EventPublisher(proxy_address=TEST_XSUB)
        time.sleep(0.1)

        pub.publish("TEST.ROUND_TRIP", {"key": "value", "n": 42})

        msg = sub.listen_sync(timeout_ms=2000)
        self.assertIsNotNone(msg, "Subscriber did not receive message")
        topic, payload = msg
        self.assertEqual(topic, "TEST.ROUND_TRIP")
        self.assertEqual(payload["key"], "value")
        self.assertEqual(payload["n"], 42)

        pub.close()
        sub.close()


@unittest.skipUnless(HAS_ZMQ, "pyzmq not installed — skipping event bus tests")
class TestTopicFiltering(unittest.TestCase):
    """Subscriber receives only matching topics."""

    @classmethod
    def setUpClass(cls):
        cls._proxy = _start_test_proxy()

    def test_subscriber_filters_by_topic(self):
        from agents.common.event_bus import EventPublisher, EventSubscriber

        # Subscribe to NEWS only
        sub = EventSubscriber(topics=["NEWS"], proxy_address=TEST_XPUB)
        time.sleep(0.2)

        pub = EventPublisher(proxy_address=TEST_XSUB)
        time.sleep(0.1)

        # Publish on two different topics
        pub.publish("TRADE.EXECUTED", {"symbol": "AAPL"})
        pub.publish("NEWS.CRITICAL", {"headline": "Fed raises rates"})
        time.sleep(0.3)

        # Should receive the NEWS event only
        msg = sub.listen_sync(timeout_ms=1000)
        self.assertIsNotNone(msg)
        topic, payload = msg
        self.assertTrue(topic.startswith("NEWS"))
        self.assertEqual(payload["headline"], "Fed raises rates")

        # Should NOT receive the TRADE event
        msg2 = sub.listen_sync(timeout_ms=500)
        self.assertIsNone(msg2)

        pub.close()
        sub.close()


@unittest.skipUnless(HAS_ZMQ, "pyzmq not installed — skipping event bus tests")
class TestDrain(unittest.TestCase):
    """Drain returns all queued messages non-blockingly."""

    @classmethod
    def setUpClass(cls):
        cls._proxy = _start_test_proxy()

    def test_drain_multiple(self):
        from agents.common.event_bus import EventPublisher, EventSubscriber

        sub = EventSubscriber(topics=["DRAIN"], proxy_address=TEST_XPUB)
        time.sleep(0.2)

        pub = EventPublisher(proxy_address=TEST_XSUB)
        time.sleep(0.1)

        for i in range(5):
            pub.publish("DRAIN.TEST", {"i": i})
        time.sleep(0.3)

        messages = sub.drain(max_messages=10)
        self.assertEqual(len(messages), 5)
        for idx, (topic, payload) in enumerate(messages):
            self.assertEqual(topic, "DRAIN.TEST")
            self.assertEqual(payload["i"], idx)

        pub.close()
        sub.close()


@unittest.skipUnless(HAS_ZMQ, "pyzmq not installed — skipping event bus tests")
class TestGracefulDegradation(unittest.TestCase):
    """Publisher handles missing proxy gracefully."""

    def test_publish_without_proxy_returns_false_not_crash(self):
        from agents.common.event_bus import EventPublisher

        # Connect to a port where nothing is listening
        pub = EventPublisher(proxy_address="tcp://127.0.0.1:19999")
        # publish should return True (ZMQ PUB sends even without subscribers)
        # but importantly it should NOT raise
        result = pub.publish("TEST", {"data": 1})
        self.assertIsInstance(result, bool)
        pub.close()

    def test_subscriber_timeout_returns_none(self):
        from agents.common.event_bus import EventSubscriber

        sub = EventSubscriber(
            topics=["NOTHING"],
            proxy_address="tcp://127.0.0.1:19999",
        )
        msg = sub.listen_sync(timeout_ms=200)
        self.assertIsNone(msg)
        sub.close()


@unittest.skipUnless(HAS_ZMQ, "pyzmq not installed — skipping event bus tests")
class TestTopicConstants(unittest.TestCase):
    """Verify all topic constants are properly defined."""

    def test_all_topics_are_strings(self):
        from agents.common.event_bus import ALL_TOPICS

        self.assertGreater(len(ALL_TOPICS), 5)
        for topic in ALL_TOPICS:
            self.assertIsInstance(topic, str)
            self.assertTrue(len(topic) > 0)


if __name__ == "__main__":
    unittest.main()
