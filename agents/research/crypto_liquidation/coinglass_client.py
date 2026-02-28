"""
CoinGlass API Client — Liquidation Data (Framework)

Provides async access to CoinGlass liquidation-specific REST endpoints.
Requires a paid API key (Hobbyist plan: $29/month).

When no API key is configured, all methods raise ``CoinGlassNotConfigured``
so the agent can operate gracefully without this data source.

Endpoints (v3 API):
    - /futures/liquidation/v2/history   → historical liquidation data
    - /futures/liquidation/heatmap      → liquidation price heatmap
    - /futures/liquidation/order        → recent liquidation orders (7 days)

Documentation: https://coinglass.com/pricing
API Docs:      https://open-api-v3.coinglass.com/api
"""

import logging
import os
from typing import Optional

import aiohttp

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COINGLASS_BASE_URL = "https://open-api-v3.coinglass.com/api"

logger = logging.getLogger("crypto_liquidation.coinglass_client")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CoinGlassNotConfigured(Exception):
    """Raised when CoinGlass API key is not set."""

    def __init__(self):
        super().__init__(
            "CoinGlass API key not configured. "
            "Set COINGLASS_API_KEY environment variable. "
            "Plans start at $29/month: https://coinglass.com/pricing"
        )


# ---------------------------------------------------------------------------
# REST Client
# ---------------------------------------------------------------------------


class CoinGlassREST:
    """
    Async REST client for CoinGlass liquidation data.

    All requests require a valid API key passed via the ``coinglassSecret``
    header.  If no key is configured, methods raise ``CoinGlassNotConfigured``.

    Usage::

        client = CoinGlassREST()
        if client.is_configured:
            history = await client.get_liquidation_history("BTC")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = COINGLASS_BASE_URL,
    ):
        self.api_key = api_key or os.environ.get("COINGLASS_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def is_configured(self) -> bool:
        """True if an API key is available."""
        return bool(self.api_key)

    async def _ensure_session(self):
        if not self.is_configured:
            raise CoinGlassNotConfigured()
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"coinglassSecret": self.api_key}
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict) -> dict:
        """Execute a GET request and return the parsed JSON body."""
        await self._ensure_session()
        url = f"{self.base_url}{path}"
        async with self._session.get(url, params=params) as resp:
            body = await resp.json()
            if body.get("success") is False:
                logger.error("CoinGlass error: %s", body.get("msg", body))
            return body

    # ------------------------------------------------------------------
    # Liquidation History
    # ------------------------------------------------------------------

    async def get_liquidation_history(
        self,
        symbol: str = "BTC",
        time_type: str = "all",
    ) -> list[dict]:
        """
        GET /futures/liquidation/v2/history

        Returns historical liquidation data for a symbol.

        Parameters
        ----------
        symbol : str
            Coin symbol (e.g. "BTC", "ETH").
        time_type : str
            Time window: "all", "4h", "12h", "24h".

        Returns
        -------
        list[dict]
            Liquidation records with fields like: exchange, symbol,
            longVolUsd, shortVolUsd, timestamp, etc.
        """
        body = await self._get(
            "/futures/liquidation/v2/history",
            {"symbol": symbol.upper(), "time_type": time_type},
        )
        return body.get("data", [])

    # ------------------------------------------------------------------
    # Liquidation Heatmap
    # ------------------------------------------------------------------

    async def get_liquidation_heatmap(
        self,
        symbol: str = "BTC",
        time_type: str = "24h",
    ) -> list[dict]:
        """
        GET /futures/liquidation/heatmap

        Returns liquidation heatmap data showing accumulated liquidation
        levels at different price points.

        Parameters
        ----------
        symbol : str
            Coin symbol (e.g. "BTC", "ETH").
        time_type : str
            Time window: "12h", "24h", "3d", "7d", "30d".

        Returns
        -------
        list[dict]
            Heatmap price-level records with liquidation volume.
        """
        body = await self._get(
            "/futures/liquidation/heatmap",
            {"symbol": symbol.upper(), "time_type": time_type},
        )
        return body.get("data", [])

    # ------------------------------------------------------------------
    # Liquidation Orders (Recent, 7-day window)
    # ------------------------------------------------------------------

    async def get_liquidation_orders(
        self,
        symbol: str = "BTC",
    ) -> list[dict]:
        """
        GET /futures/liquidation/order

        Returns recent liquidation orders from the past 7 days.

        Parameters
        ----------
        symbol : str
            Coin symbol (e.g. "BTC", "ETH").

        Returns
        -------
        list[dict]
            Liquidation order records with exchange, pair, side, price,
            quantity, and timestamp.
        """
        body = await self._get(
            "/futures/liquidation/order",
            {"symbol": symbol.upper()},
        )
        return body.get("data", [])
