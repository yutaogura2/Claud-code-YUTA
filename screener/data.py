"""yfinance データ取得層。

Vol.1 の「Data 層」に相当。キャッシュ（24h TTL）・リトライ・異常値の
最低限のサニタイズを担う。1銘柄ごとに info と価格ヒストリーを返す。
"""
from __future__ import annotations

import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


@dataclass
class StockData:
    ticker: str
    info: dict[str, Any] = field(default_factory=dict)
    history: pd.DataFrame | None = None  # 日次 OHLCV

    @property
    def ok(self) -> bool:
        return self.history is not None and not self.history.empty


def _cache_path(key: str) -> Path:
    safe = key.replace("^", "_idx_").replace(".", "_")
    return CACHE_DIR / f"{safe}.json"


def _read_cache(key: str, ttl: int) -> dict | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > ttl:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(key: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _cache_path(key).write_text(
            json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8"
        )
    except Exception:
        pass


def _sanitize_info(info: dict) -> dict:
    """異常値（None/負のPER等）を扱いやすい形に整える。"""
    out = {}
    for k in (
        "shortName", "trailingPE", "priceToBook", "dividendYield",
        "returnOnEquity", "revenueGrowth", "marketCap",
        "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
        "targetMeanPrice", "recommendationKey", "currentPrice",
    ):
        out[k] = info.get(k)
    return out


def fetch(ticker: str, ttl: int = 86400, period: str = "1y",
          retries: int = 3) -> StockData:
    """1銘柄の info + 日次ヒストリーを取得（キャッシュ優先）。"""
    cached = _read_cache(ticker, ttl)
    if cached is not None:
        hist = (pd.read_json(io.StringIO(cached["history"]), orient="split")
                if cached.get("history") else None)
        if hist is not None and not hist.empty:
            hist.index = pd.to_datetime(hist.index)
        return StockData(ticker, cached.get("info", {}), hist)

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker)
            info = _sanitize_info(t.info or {})
            hist = t.history(period=period, auto_adjust=True)
            if hist.empty:
                raise ValueError("empty history")
            _write_cache(ticker, {
                "info": info,
                "history": hist.to_json(orient="split", date_format="iso"),
            })
            return StockData(ticker, info, hist)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))  # レート制限対策の指数的待機
    print(f"  [warn] {ticker} 取得失敗: {last_err}")
    return StockData(ticker)


def fetch_history(ticker: str, period: str = "3y", ttl: int = 86400, retries: int = 3):
    """長期の日次OHLCVを取得。キャッシュキーは <ticker>_hist_<period>。失敗は None。"""
    key = f"{ticker}_hist_{period}"
    cached = _read_cache(key, ttl)
    if cached is not None and cached.get("history"):
        h = pd.read_json(io.StringIO(cached["history"]), orient="split")
        if not h.empty:
            h.index = pd.to_datetime(h.index)
        return h

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
            if hist.empty:
                raise ValueError("empty history")
            _write_cache(key, {"history": hist.to_json(orient="split", date_format="iso")})
            return hist
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"  [warn] {ticker} 履歴取得失敗: {last_err}")
    return None


def _row(df, name):
    """財務DataFrameの1行を newest→oldest の list[float|None] で返す。無い行は []。"""
    try:
        vals = df.loc[name].tolist()  # 行が無い/重複/df=None は例外で [] に倒す
    except (KeyError, AttributeError, TypeError):
        return []
    out = []
    for v in vals:
        try:
            f = float(v)
            out.append(None if f != f else f)  # NaN→None
        except (TypeError, ValueError):
            out.append(None)
    return out


def fetch_financials(ticker: str, ttl: int = 86400) -> dict | None:
    """年次財務6系列を newest→oldest で取得（24hキャッシュ）。取得不能は None。"""
    key = ticker + "_fin"
    cached = _read_cache(key, ttl)
    if cached is not None:
        return cached.get("fin")

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            t = yf.Ticker(ticker)
            inc, bal, cf = t.income_stmt, t.balance_sheet, t.cashflow
            fin = {
                "revenue": _row(inc, "Total Revenue"),
                "net_income": _row(inc, "Net Income"),
                "ocf": _row(cf, "Operating Cash Flow"),
                "fcf": _row(cf, "Free Cash Flow"),
                "total_assets": _row(bal, "Total Assets"),
                "equity": _row(bal, "Stockholders Equity"),
            }
            if all(len(v) == 0 for v in fin.values()):
                raise ValueError("no financials")
            _write_cache(key, {"fin": fin})
            return fin
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"  [warn] {ticker} 財務取得失敗: {last_err}")
    return None


def fetch_news(ticker: str, limit: int = 3, ttl: int = 86400) -> list[tuple[str, str]]:
    """yfinance のニュースから (タイトル, URL) を最大 limit 件。失敗は []（24hキャッシュ）。"""
    key = ticker + "_news"
    cached = _read_cache(key, ttl)
    if cached is not None:
        return [tuple(x) for x in cached.get("news", [])]
    out: list[tuple[str, str]] = []
    try:
        for it in (yf.Ticker(ticker).news or [])[:limit]:
            content = it.get("content") or {}
            title = it.get("title") or content.get("title")
            link = it.get("link")
            if not link:
                link = ((content.get("canonicalUrl") or {}).get("url")
                        or (content.get("clickThroughUrl") or {}).get("url"))
            if title and link:
                out.append((title, link))
    except Exception:  # noqa: BLE001
        out = []
    _write_cache(key, {"news": out})
    return out
