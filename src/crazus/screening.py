"""Scoring quantitatif (momentum, qualité, croissance, valorisation, consensus)."""

from __future__ import annotations

import math
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

_cache_dir = Path(tempfile.gettempdir()) / f"crazus-yf-{os.getpid()}"
_cache_dir.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(_cache_dir))


@contextmanager
def _no_stdout() -> Any:
    """yfinance prints failures to stdout, which would break MCP stdio JSON-RPC."""
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old

DISCLAIMER = (
    "Ceci n'est pas un conseil en investissement. Le score combine des données "
    "Yahoo Finance (yfinance) : momentum, qualité, croissance, valorisation et "
    "consensus analystes. Les données peuvent être incomplètes, retardées ou "
    "erronées. Les performances passées ne préjugent pas des performances futures."
)

STYLE_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {
        "momentum": 0.30,
        "quality": 0.25,
        "growth": 0.20,
        "valuation": 0.15,
        "analyst": 0.10,
    },
    "momentum": {
        "momentum": 0.55,
        "quality": 0.15,
        "growth": 0.15,
        "valuation": 0.05,
        "analyst": 0.10,
    },
    "quality": {
        "momentum": 0.15,
        "quality": 0.40,
        "growth": 0.15,
        "valuation": 0.20,
        "analyst": 0.10,
    },
    "growth": {
        "momentum": 0.20,
        "quality": 0.15,
        "growth": 0.40,
        "valuation": 0.10,
        "analyst": 0.15,
    },
    "value": {
        "momentum": 0.10,
        "quality": 0.25,
        "growth": 0.10,
        "valuation": 0.45,
        "analyst": 0.10,
    },
}


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def pct_return(closes: pd.Series, trading_days: int) -> float | None:
    series = closes.dropna()
    if len(series) <= trading_days:
        if len(series) < 2:
            return None
        start, end = float(series.iloc[0]), float(series.iloc[-1])
    else:
        start, end = float(series.iloc[-trading_days - 1]), float(series.iloc[-1])
    if start == 0:
        return None
    return (end / start) - 1.0


def realized_vol(closes: pd.Series, window: int = 63) -> float | None:
    rets = closes.dropna().pct_change().dropna()
    if len(rets) < 10:
        return None
    sample = rets.iloc[-window:] if len(rets) > window else rets
    return float(sample.std() * math.sqrt(252))


def max_drawdown(closes: pd.Series) -> float | None:
    series = closes.dropna()
    if len(series) < 5:
        return None
    peak = series.cummax()
    dd = (series / peak) - 1.0
    return float(dd.min())


def score_momentum(r1m: float | None, r3m: float | None, r6m: float | None, r1y: float | None) -> float:
    parts = []
    for ret, scale in ((r1m, 40.0), (r3m, 25.0), (r6m, 18.0), (r1y, 12.0)):
        if ret is None:
            continue
        parts.append(clamp(50.0 + ret * scale * 100.0))
    if not parts:
        return 40.0
    return sum(parts) / len(parts)


def score_quality(
    roe: float | None,
    profit_margin: float | None,
    operating_margin: float | None,
    debt_to_equity: float | None,
) -> float:
    pieces: list[float] = []
    if roe is not None:
        pieces.append(clamp(50.0 + roe * 150.0))
    if profit_margin is not None:
        pieces.append(clamp(50.0 + profit_margin * 200.0))
    if operating_margin is not None:
        pieces.append(clamp(50.0 + operating_margin * 180.0))
    if not pieces:
        quality = 45.0
    else:
        quality = sum(pieces) / len(pieces)
    if debt_to_equity is not None:
        if debt_to_equity < 0:
            quality -= 8
        elif debt_to_equity > 200:
            quality -= 15
        elif debt_to_equity > 100:
            quality -= 8
        elif debt_to_equity < 40:
            quality += 5
    return clamp(quality)


def score_growth(revenue_growth: float | None, earnings_growth: float | None) -> float:
    parts: list[float] = []
    if revenue_growth is not None:
        parts.append(clamp(50.0 + revenue_growth * 120.0))
    if earnings_growth is not None:
        parts.append(clamp(50.0 + earnings_growth * 80.0))
    if not parts:
        return 45.0
    return sum(parts) / len(parts)


def score_valuation(
    pe: float | None,
    forward_pe: float | None,
    peg: float | None,
    pb: float | None,
) -> float:
    parts: list[float] = []
    pe_used = forward_pe if forward_pe and forward_pe > 0 else pe
    if pe_used is not None and pe_used > 0:
        if pe_used < 8:
            parts.append(55.0)
        elif pe_used > 80:
            parts.append(20.0)
        else:
            parts.append(clamp(100.0 - (pe_used - 12.0) * 1.4))
    if peg is not None and peg > 0:
        parts.append(clamp(100.0 - peg * 35.0))
    if pb is not None and pb > 0:
        parts.append(clamp(90.0 - pb * 12.0))
    if not parts:
        return 50.0
    return sum(parts) / len(parts)


def score_analyst(recommendation_mean: float | None, target_upside: float | None) -> float:
    parts: list[float] = []
    if recommendation_mean is not None:
        # Yahoo: 1 = strong buy, 5 = sell
        parts.append(clamp((3.5 - recommendation_mean) * 40.0))
    if target_upside is not None:
        parts.append(clamp(50.0 + target_upside * 80.0))
    if not parts:
        return 50.0
    return sum(parts) / len(parts)


def composite_score(components: dict[str, float], style: str) -> float:
    weights = STYLE_WEIGHTS.get(style, STYLE_WEIGHTS["balanced"])
    total = sum(components[key] * weight for key, weight in weights.items())
    return round(clamp(total), 1)


def download_closes(tickers: list[str], period: str = "1y") -> dict[str, pd.Series]:
    if not tickers:
        return {}
    with _no_stdout():
        raw = yf.download(
            tickers=tickers,
            period=period,
            auto_adjust=True,
            progress=False,
            threads=False,
            group_by="column",
        )
    if raw.empty:
        return {}

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close = raw["Close"]
        else:
            close = raw.xs("Close", axis=1, level=1, drop_level=True)
        if isinstance(close, pd.Series):
            return {tickers[0]: close.dropna()}
        return {str(col): close[col].dropna() for col in close.columns if close[col].dropna().shape[0] >= 5}

    close = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]
    return {tickers[0]: close.dropna()}


def fetch_fundamentals(ticker: str) -> dict[str, Any]:
    stock = yf.Ticker(ticker)
    info: dict[str, Any] = {}
    try:
        with _no_stdout():
            info = stock.info or {}
    except Exception:
        info = {}

    price = _finite(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"))
    target = _finite(info.get("targetMeanPrice"))
    upside = None
    if price and target and price > 0:
        upside = (target / price) - 1.0

    return {
        "ticker": ticker,
        "name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "price": price,
        "market_cap": _finite(info.get("marketCap")),
        "pe": _finite(info.get("trailingPE")),
        "forward_pe": _finite(info.get("forwardPE")),
        "peg": _finite(info.get("pegRatio")),
        "pb": _finite(info.get("priceToBook")),
        "roe": _finite(info.get("returnOnEquity")),
        "profit_margin": _finite(info.get("profitMargins")),
        "operating_margin": _finite(info.get("operatingMargins")),
        "debt_to_equity": _finite(info.get("debtToEquity")),
        "revenue_growth": _finite(info.get("revenueGrowth")),
        "earnings_growth": _finite(info.get("earningsGrowth") or info.get("earningsQuarterlyGrowth")),
        "recommendation_mean": _finite(info.get("recommendationMean")),
        "recommendation_key": info.get("recommendationKey"),
        "target_mean": target,
        "target_upside": upside,
        "beta": _finite(info.get("beta")),
        "fifty_two_week_high": _finite(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low": _finite(info.get("fiftyTwoWeekLow")),
        "average_volume": _finite(info.get("averageVolume")),
    }


def fetch_quote(ticker: str) -> dict[str, Any]:
    stock = yf.Ticker(ticker)
    fast: dict[str, Any] = {}
    try:
        with _no_stdout():
            fast = dict(stock.fast_info) if stock.fast_info is not None else {}
    except Exception:
        fast = {}
    info = fetch_fundamentals(ticker)
    last = _finite(fast.get("lastPrice") or fast.get("last_price")) or info.get("price")
    prev = _finite(fast.get("previousClose") or fast.get("previous_close"))
    change = None
    if last is not None and prev not in (None, 0):
        change = (last / prev) - 1.0
    return {
        **info,
        "price": last,
        "previous_close": prev,
        "day_change": change,
        "day_high": _finite(fast.get("dayHigh") or fast.get("day_high")),
        "day_low": _finite(fast.get("dayLow") or fast.get("day_low")),
        "volume": _finite(fast.get("lastVolume") or fast.get("last_volume")),
        "market_cap": _finite(fast.get("marketCap") or fast.get("market_cap")) or info.get("market_cap"),
    }


def fetch_news(ticker: str, limit: int = 8) -> list[dict[str, Any]]:
    stock = yf.Ticker(ticker)
    items = []
    try:
        with _no_stdout():
            raw = stock.news or []
    except Exception:
        raw = []
    for entry in raw[:limit]:
        content = entry.get("content") if isinstance(entry.get("content"), dict) else entry
        title = content.get("title") or entry.get("title")
        url = None
        click = content.get("clickThroughUrl") or content.get("canonicalUrl") or {}
        if isinstance(click, dict):
            url = click.get("url")
        url = url or entry.get("link")
        pub = content.get("pubDate") or entry.get("providerPublishTime")
        items.append({"title": title, "url": url, "published": pub})
    return items


def search_tickers(query: str, limit: int = 8) -> list[dict[str, Any]]:
    try:
        with _no_stdout():
            raw = yf.Search(query, max_results=limit).quotes
    except Exception:
        return []
    results = []
    for item in raw[:limit]:
        results.append(
            {
                "ticker": item.get("symbol"),
                "name": item.get("shortname") or item.get("longname"),
                "exchange": item.get("exchange"),
                "type": item.get("quoteType"),
            }
        )
    return results


def _momentum_snapshot(closes: pd.Series) -> dict[str, Any]:
    r1m = pct_return(closes, 21)
    r3m = pct_return(closes, 63)
    r6m = pct_return(closes, 126)
    r1y = pct_return(closes, 252)
    vol = realized_vol(closes)
    dd = max_drawdown(closes)
    last = float(closes.dropna().iloc[-1]) if not closes.dropna().empty else None
    return {
        "price": last,
        "return_1m": r1m,
        "return_3m": r3m,
        "return_6m": r6m,
        "return_1y": r1y,
        "volatility": vol,
        "max_drawdown": dd,
        "momentum_score": round(score_momentum(r1m, r3m, r6m, r1y), 1),
    }


def screen_tickers(
    tickers: list[str],
    style: str = "balanced",
    top_n: int = 10,
    min_market_cap: float | None = None,
    fundamental_pool: int = 25,
) -> dict[str, Any]:
    if style not in STYLE_WEIGHTS:
        raise ValueError(f"Style inconnu: {style}. Choix: {', '.join(STYLE_WEIGHTS)}")
    top_n = max(1, min(top_n, 30))
    fundamental_pool = max(top_n, min(fundamental_pool, 40))

    closes_map = download_closes(tickers)
    pre_ranked: list[dict[str, Any]] = []
    for ticker in tickers:
        closes = closes_map.get(ticker)
        if closes is None or closes.empty:
            continue
        snap = _momentum_snapshot(closes)
        pre_ranked.append({"ticker": ticker, **snap})
    pre_ranked.sort(key=lambda row: row["momentum_score"], reverse=True)
    pool = [row["ticker"] for row in pre_ranked[:fundamental_pool]]
    snaps = {row["ticker"]: row for row in pre_ranked}

    fundamentals: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool_exec:
        futures = {pool_exec.submit(fetch_fundamentals, ticker): ticker for ticker in pool}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                fundamentals[ticker] = future.result()
            except Exception as exc:
                fundamentals[ticker] = {"ticker": ticker, "error": str(exc)}

    ranked: list[dict[str, Any]] = []
    for ticker in pool:
        snap = snaps[ticker]
        info = fundamentals.get(ticker, {"ticker": ticker})
        if min_market_cap and info.get("market_cap") and info["market_cap"] < min_market_cap:
            continue
        components = {
            "momentum": snap["momentum_score"],
            "quality": round(
                score_quality(
                    info.get("roe"),
                    info.get("profit_margin"),
                    info.get("operating_margin"),
                    info.get("debt_to_equity"),
                ),
                1,
            ),
            "growth": round(score_growth(info.get("revenue_growth"), info.get("earnings_growth")), 1),
            "valuation": round(
                score_valuation(info.get("pe"), info.get("forward_pe"), info.get("peg"), info.get("pb")),
                1,
            ),
            "analyst": round(score_analyst(info.get("recommendation_mean"), info.get("target_upside")), 1),
        }
        ranked.append(
            {
                **info,
                **{k: snap[k] for k in ("return_1m", "return_3m", "return_6m", "return_1y", "volatility", "max_drawdown")},
                "components": components,
                "score": composite_score(components, style),
                "style": style,
            }
        )

    ranked.sort(key=lambda row: row["score"], reverse=True)
    return {
        "disclaimer": DISCLAIMER,
        "style": style,
        "universe_size": len(tickers),
        "scored": len(ranked),
        "results": ranked[:top_n],
    }


def score_one(ticker: str, style: str = "balanced") -> dict[str, Any]:
    payload = screen_tickers([ticker], style=style, top_n=1, fundamental_pool=1)
    if not payload["results"]:
        return {"ticker": ticker, "error": "Données introuvables", "disclaimer": DISCLAIMER}
    return payload["results"][0] | {"disclaimer": DISCLAIMER}
