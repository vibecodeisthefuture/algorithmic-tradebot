"""
DataLoader — OHLCV Data Source for the Predictions Agent

Loads clean OHLCV DataFrames for any supported asset. Tries tradebot.db first
(ohlcv table, if it exists), then falls back to the pre-collected CSV files
at data/datasets/data_tables/. Always returns a consistent DataFrame shape.

Supported assets
----------------
Crypto  : BTC, ETH, SOL, XRP, ADA, DOGE  (6h candles, ~500 weeks)
Stocks  : AAPL, GOOG, NVDA, META, NFLX, ASTS  (1d candles, ~1000 weeks)

Output format
-------------
DataFrame columns: [timestamp (datetime64), open, high, low, close, volume]
    - Sorted ascending by timestamp
    - No nulls in close or volume (rows with NaN are dropped)
    - timestamp is tz-naive UTC
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path resolution — locate data/ directory relative to project root
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent  # agents/research/predictions/ → TradeBot/
_DATA_TABLES = _PROJECT_ROOT / "data" / "datasets" / "data_tables"



# ---------------------------------------------------------------------------
# Asset → CSV path mapping
# ---------------------------------------------------------------------------

# Crypto assets use 6h candles; stocks use 1d candles.
# Keys match TradeBot asset identifiers (as stored in tradebot.db).
_CRYPTO_ASSETS = {"BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD", "DOGE/USD"}
_STOCK_ASSETS  = {"AAPL", "GOOG", "NVDA", "META", "NFLX", "ASTS"}

# Maps asset identifier → CSV file path (relative to _DATA_TABLES)
_CSV_MAP: dict[str, Path] = {
    # --- Crypto ---
    "BTC/USD":  _DATA_TABLES / "crypto" / "BTC-6h-500wks-data.csv",
    "ETH/USD":  _DATA_TABLES / "crypto" / "ETH-6h-500wks-data.csv",
    "SOL/USD":  _DATA_TABLES / "crypto" / "SOL-6h-500wks-data.csv",
    "XRP/USD":  _DATA_TABLES / "crypto" / "XRP-6h-500wks-data.csv",
    "ADA/USD":  _DATA_TABLES / "crypto" / "ADA-6h-500wks-data.csv",
    "DOGE/USD": _DATA_TABLES / "crypto" / "DOGE-6h-500wks-data.csv",
    # --- Stocks ---
    "AAPL": _DATA_TABLES / "stocks" / "AAPL-1d-data.csv",
    "GOOG": _DATA_TABLES / "stocks" / "GOOG-1d-data.csv",
    "NVDA": _DATA_TABLES / "stocks" / "NVDA-1d-data.csv",
    "META": _DATA_TABLES / "stocks" / "META-1d-data.csv",
    "NFLX": _DATA_TABLES / "stocks" / "NFLX-1d-data.csv",
    "ASTS": _DATA_TABLES / "stocks" / "ASTS-1d-data.csv",
}

# Standard column names all CSVs must contain (case-insensitive on load)
_REQUIRED_COLS = {"timestamp", "open", "high", "low", "close", "volume"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_ohlcv(
    asset: str,
    max_rows: Optional[int] = None,
    min_rows: int = 100,
) -> pd.DataFrame:
    """
    Load OHLCV data for a given asset.

    Tries the tradebot.db ohlcv table first. Falls back to CSV if the table
    doesn't exist or the asset has no rows there.

    Parameters
    ----------
    asset : str
        Asset identifier, e.g. "BTC/USD" or "AAPL".
    max_rows : int, optional
        Maximum number of most-recent rows to return. None = all rows.
        Use to limit lookback (e.g. 500 candles for ARIMA, 60 for LSTM).
    min_rows : int
        Minimum acceptable row count. Raises ValueError if dataset is smaller.

    Returns
    -------
    pd.DataFrame
        Columns: timestamp (datetime64[ns]), open, high, low, close, volume
        Sorted ascending by timestamp. No nulls in close/volume.

    Raises
    ------
    ValueError
        If the asset is not in the supported list, the CSV doesn't exist,
        or the cleaned dataset has fewer than min_rows rows.
    """
    if asset not in _CSV_MAP:
        raise ValueError(
            f"Unknown asset {asset!r}. Supported: {sorted(_CSV_MAP.keys())}"
        )

    # Attempt DB first; fall back to CSV on any failure
    df = _try_load_from_db(asset)
    if df is None or df.empty:
        logger.debug("[%s] DB load skipped or empty — loading from CSV", asset)
        df = _load_from_csv(asset)
    else:
        logger.debug("[%s] Loaded %d rows from tradebot.db", asset, len(df))

    df = _clean(df, asset)

    if max_rows is not None and len(df) > max_rows:
        df = df.tail(max_rows).reset_index(drop=True)

    if len(df) < min_rows:
        raise ValueError(
            f"[{asset}] Only {len(df)} rows after cleaning — need at least {min_rows}. "
            "Ensure data collection has run."
        )

    return df


def list_supported_assets() -> dict[str, str]:
    """Return a dict of {asset: 'crypto'|'stocks'} for all supported tickers."""
    result = {}
    for a in _CRYPTO_ASSETS:
        result[a] = "crypto"
    for a in _STOCK_ASSETS:
        result[a] = "stocks"
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _try_load_from_db(asset: str) -> Optional[pd.DataFrame]:
    """
    Attempt to load from the ohlcv table in tradebot.db.
    Returns None silently if the table doesn't exist or the query fails.
    """
    try:
        from agents.common.database import engine
        query = (
            f"SELECT timestamp, open, high, low, close, volume "
            f"FROM ohlcv WHERE asset = '{asset}' ORDER BY timestamp ASC"
        )
        df = pd.read_sql(query, con=engine, parse_dates=["timestamp"])
        return df if not df.empty else None
    except Exception as exc:
        logger.debug("[%s] DB load failed (%s) — will use CSV fallback", asset, exc)
        return None


def _load_from_csv(asset: str) -> pd.DataFrame:
    """
    Load OHLCV from the pre-collected CSV file for the given asset.
    Raises ValueError if the file doesn't exist.

    NOTE: CSV files use 'date' as the timestamp column name.
    The _clean() function normalizes this to 'timestamp' automatically.
    """
    csv_path = _CSV_MAP[asset]
    if not csv_path.exists():
        raise ValueError(
            f"CSV file not found for {asset!r}: {csv_path}\n"
            "Run data collection first: python data/datasets/data_collection.py"
        )

    # Read without parse_dates — _clean() will normalize the timestamp column
    df = pd.read_csv(csv_path)

    # Rename 'date' → 'timestamp' if needed (CSV schema uses 'date')
    df.columns = [c.lower().strip() for c in df.columns]
    if "date" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"date": "timestamp"})

    logger.info("[%s] Loaded %d rows from %s", asset, len(df), csv_path.name)
    return df



def _clean(df: pd.DataFrame, asset: str) -> pd.DataFrame:
    """
    Normalize and clean a raw OHLCV DataFrame.

    - Lowercases column names
    - Ensures required columns are present
    - Converts timestamp to tz-naive UTC datetime64
    - Drops rows where close or volume is null
    - Sorts ascending by timestamp
    - Resets index
    """
    df = df.copy()
    df.columns = [c.lower().strip() for c in df.columns]

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"[{asset}] CSV/DB missing columns: {missing}")

    # Normalize timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False)
    if df["timestamp"].dt.tz is not None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)  # strip tz → naive UTC

    # Drop rows with null prices or volume
    before = len(df)
    df = df.dropna(subset=["close", "volume"])
    dropped = before - len(df)
    if dropped > 0:
        logger.warning("[%s] Dropped %d rows with null close/volume", asset, dropped)

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]
