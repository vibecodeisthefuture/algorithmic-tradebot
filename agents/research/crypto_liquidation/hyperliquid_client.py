"""
Hyperliquid API Client — WebSocket & REST

Provides async connections to the Hyperliquid public data streams and REST
endpoints used by the Crypto Liquidation Agent.

WebSocket topics:
    - trades.{coin}   → real-time public trades (whale + liquidation detection)

REST endpoint (all via POST to /info):
    - metaAndAssetCtxs  → open interest, funding rate, mark price per coin
    - fundingHistory    → historical funding rate records
    - recentTrades      → recent public trades snapshot

Documentation: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
"""

import asyncio
import json
import logging
import time
from typing import Callable, Optional

import aiohttp

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HYPERLIQUID_WS_URL = "wss://api.hyperliquid.xyz/ws"
HYPERLIQUID_REST_URL = "https://api.hyperliquid.xyz"

logger = logging.getLogger("crypto_liquidation.hyperliquid_client")

# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------


class HyperliquidWS:
    """
    Async WebSocket client for Hyperliquid public streams.

    Subscribes to ``trades`` for each coin and dispatches received
    messages to the registered callback.

    Hyperliquid trade format::

        {
            "coin": "BTC",
            "side": "B",          # "B" = buy, "A" = sell (ask)
            "px":   "66924.0",    # price
            "sz":   "0.00016",    # size (quantity)
            "time": 1770976001290,  # epoch ms
            "hash": "0x...",
            "tid":  692701904451338,
            "users": ["0x...", "0x..."]
        }
    """

    def __init__(
        self,
        coins: list[str],
        on_public_trade: Callable,
        url: str = HYPERLIQUID_WS_URL,
    ):
        self.coins = [c.upper() for c in coins]
        self.url = url
        self._on_public_trade = on_public_trade

        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

        # Exponential backoff state
        self._backoff_base = 1  # seconds
        self._backoff_max = 60
        self._backoff_current = self._backoff_base

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self):
        """Open WS connection, subscribe, and enter receive loop."""
        self._running = True
        while self._running:
            try:
                await self._connect_and_listen()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "WS disconnected (%s). Reconnecting in %ss …",
                    exc,
                    self._backoff_current,
                )
                await asyncio.sleep(self._backoff_current)
                self._backoff_current = min(
                    self._backoff_current * 2, self._backoff_max
                )

    async def stop(self):
        """Gracefully tear down the WebSocket connection."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("Hyperliquid WS client stopped.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _connect_and_listen(self):
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.url, heartbeat=20)
        logger.info("Connected to Hyperliquid WS: %s", self.url)

        # Reset backoff on successful connect
        self._backoff_current = self._backoff_base

        await self._subscribe()
        await self._receive_loop()

    async def _subscribe(self):
        """Subscribe to ``trades`` topic for every coin."""
        for coin in self.coins:
            payload = {
                "method": "subscribe",
                "subscription": {
                    "type": "trades",
                    "coin": coin,
                },
            }
            await self._ws.send_json(payload)
        logger.info("Subscribed to trades for: %s", self.coins)

    async def _receive_loop(self):
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                self._dispatch(data)
            elif msg.type in (
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                logger.warning("WS message type %s — breaking.", msg.type)
                break

    def _dispatch(self, data: dict):
        """Route an incoming message to the correct callback."""
        channel = data.get("channel", "")
        if channel == "trades":
            for item in data.get("data", []):
                self._on_public_trade(item)
        elif channel == "subscriptionResponse":
            logger.debug("WS subscription ack: %s", data)

    async def _send_ping(self):
        """Send heartbeat ping to keep connection alive."""
        if self._ws and not self._ws.closed:
            await self._ws.send_json({"method": "ping"})


# ---------------------------------------------------------------------------
# REST Client
# ---------------------------------------------------------------------------


class HyperliquidREST:
    """
    Async REST client for Hyperliquid info endpoint.

    All requests are POST to ``/info`` with a JSON body specifying the
    ``type`` of query.
    """

    def __init__(self, base_url: str = HYPERLIQUID_REST_URL):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # Meta + Asset Contexts (Open Interest, Funding, Prices)
    # ------------------------------------------------------------------

    async def get_meta_and_contexts(self) -> tuple[dict, list[dict]]:
        """
        POST /info  { "type": "metaAndAssetCtxs" }

        Returns (meta, asset_contexts):
            - meta["universe"]: list of {name, szDecimals, maxLeverage, ...}
            - asset_contexts[i]: {funding, openInterest, oraclePx, markPx, midPx, ...}

        Each asset_contexts entry corresponds to meta["universe"][i].
        """
        await self._ensure_session()
        url = f"{self.base_url}/info"
        async with self._session.post(url, json={"type": "metaAndAssetCtxs"}) as resp:
            body = await resp.json()
            if isinstance(body, list) and len(body) == 2:
                return body[0], body[1]
            logger.error("Unexpected metaAndAssetCtxs response: %s", str(body)[:200])
            return {}, []

    async def get_ticker(self, coin: str) -> dict:
        """
        Get ticker data for a specific coin from metaAndAssetCtxs.

        Returns a dict with keys: funding, openInterest, oraclePx, markPx,
        midPx, coin (added for convenience).
        """
        meta, ctxs = await self.get_meta_and_contexts()
        universe = meta.get("universe", [])
        for i, asset in enumerate(universe):
            if asset.get("name", "").upper() == coin.upper():
                if i < len(ctxs):
                    result = ctxs[i].copy()
                    result["coin"] = coin.upper()
                    return result
        return {}

    # ------------------------------------------------------------------
    # Open Interest (from metaAndAssetCtxs)
    # ------------------------------------------------------------------

    async def get_open_interest(self, coin: str) -> str:
        """
        Get current open interest for a coin.

        Returns the OI value as a string, or "" if not found.
        """
        ticker = await self.get_ticker(coin)
        return ticker.get("openInterest", "")

    # ------------------------------------------------------------------
    # Funding Rate History
    # ------------------------------------------------------------------

    async def get_funding_history(
        self,
        coin: str,
        start_time: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        """
        POST /info  { "type": "fundingHistory", "coin": coin, "startTime": start_time }

        Returns list of {coin, fundingRate, premium, time}.
        Most recent entries are last in the list.
        """
        await self._ensure_session()
        url = f"{self.base_url}/info"
        payload = {
            "type": "fundingHistory",
            "coin": coin.upper(),
            "startTime": start_time,
        }
        async with self._session.post(url, json=payload) as resp:
            body = await resp.json()
            if isinstance(body, list):
                return body[-limit:]  # Return most recent entries
            logger.error("Unexpected fundingHistory response: %s", str(body)[:200])
            return []

    # ------------------------------------------------------------------
    # Recent Trades (REST snapshot)
    # ------------------------------------------------------------------

    async def get_recent_trades(self, coin: str) -> list[dict]:
        """
        POST /info  { "type": "recentTrades", "coin": coin }

        Returns list of trade dicts: {coin, side, px, sz, time, hash, tid, users}.
        """
        await self._ensure_session()
        url = f"{self.base_url}/info"
        payload = {
            "type": "recentTrades",
            "coin": coin.upper(),
        }
        async with self._session.post(url, json=payload) as resp:
            body = await resp.json()
            if isinstance(body, list):
                return body
            logger.error("Unexpected recentTrades response: %s", str(body)[:200])
            return []
