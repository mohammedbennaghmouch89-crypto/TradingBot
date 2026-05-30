"""MNQ (Micro E-mini Nasdaq-100) market-data loader for backtesting.

Fetches 1-minute OHLCV for the Micro Nasdaq future (Yahoo symbol ``MNQ=F``) and
caches it to a local CSV so backtests are **deterministic and offline-repeatable**
(per ``docs/TESTING.md``: tests must not hit the network). The coarser *context*
timeframe used for the Volume-Profile setup (default **3-minute**) is derived by
resampling the same 1m data — Yahoo has no native 3m interval, and deriving both
series from one source guarantees they align with no cross-feed drift.

Free-feed constraint discovered empirically (Yahoo): 1-minute data is limited to
**8 days per request** and only the **last ~30 days** are retained, so we fetch
1m in <=7-day chunks and concatenate, yielding the most recent ~3 weeks. A true
full calendar month at 1m needs a paid feed (Databento/Polygon/IBKR).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

MNQ_SYMBOL = "MNQ=F"
CACHE_DIR = Path(__file__).resolve().parents[3] / "data_cache"

# Columns we standardize on everywhere downstream.
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance output to lowercase OHLCV with a clean DatetimeIndex."""
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance returns a (field, ticker) MultiIndex for a single symbol.
        df = df.droplevel(1, axis=1)
    df = df.rename(columns=str.lower)
    df = df[[c for c in OHLCV_COLUMNS if c in df.columns]].copy()
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "timestamp"
    return df[~df.index.duplicated(keep="first")].sort_index()


def _fetch_1m_chunked(start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
    """Fetch 1m data in <=7-day chunks to respect Yahoo's per-request cap."""
    import yfinance as yf

    frames: list[pd.DataFrame] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + dt.timedelta(days=7), end)
        raw = yf.download(
            MNQ_SYMBOL,
            start=cursor.strftime("%Y-%m-%d"),
            end=chunk_end.strftime("%Y-%m-%d"),
            interval="1m",
            progress=False,
            auto_adjust=False,
        )
        if raw is not None and len(raw):
            frames.append(_normalize(raw))
        cursor = chunk_end
    if not frames:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    out = pd.concat(frames)
    return out[~out.index.duplicated(keep="first")].sort_index()


def resample(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Aggregate 1-minute OHLCV into a coarser timeframe (e.g. ``'3min'``).

    Yahoo has no native 3-minute interval, so the context timeframe is built by
    resampling the 1m data. Deriving both series from the same 1m source also
    guarantees they align exactly (no cross-feed drift). Empty bars (gaps,
    weekends) are dropped.
    """
    if df_1m.empty:
        return df_1m.copy()
    agg = df_1m.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return agg.dropna(subset=["open"])


def load(
    days: int = 21,
    context_rule: str = "3min",
    *,
    refresh: bool = False,
    cache_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load (and cache) MNQ 1m OHLCV and a resampled context timeframe.

    Returns ``(df_1m, df_context)`` with UTC DatetimeIndex and lowercase OHLCV
    columns. ``context_rule`` is the pandas offset for the setup timeframe
    (default ``'3min'``). Only the 1m data is fetched/cached; the context frame is
    derived from it via :func:`resample`. Network access happens only on a cache
    miss / refresh.
    """
    cdir = cache_dir or CACHE_DIR
    cdir.mkdir(parents=True, exist_ok=True)
    p1 = cdir / "mnq_1m.csv"

    if not refresh and p1.exists():
        df1 = pd.read_csv(p1, index_col="timestamp", parse_dates=["timestamp"])
    else:
        end = dt.datetime.now()
        start = end - dt.timedelta(days=days)
        df1 = _fetch_1m_chunked(start, end)
        df1.to_csv(p1)

    return df1, resample(df1, context_rule)
