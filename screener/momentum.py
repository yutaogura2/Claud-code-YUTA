"""モメンタムスクリーニング（Vol.3）。

強さ条件: RSI過熱圏 / MACDゴールデンクロス / ROC加速 / 出来高トレンド上昇 /
200日線上方乖離。条件該当数を momentum_score とする。
"""
from __future__ import annotations

from . import indicators as ind
from .data import StockData


def momentum_screen(sd: StockData, cfg: dict) -> dict | None:
    if not sd.ok:
        return None
    close = sd.history["Close"]
    vol = sd.history["Volume"]
    price = float(close.iloc[-1])

    rsi = ind.rsi(close)
    macd_line, macd_sig = ind.macd(close)
    roc_now = ind.roc(close, 12)
    roc_prev = ind.roc(close.iloc[:-5], 12) if len(close) > 20 else float("nan")
    vr = ind.volume_ratio(vol)
    sma200 = ind.sma(close, 200)
    dev200 = ind.deviation_pct(price, sma200)

    flags = {
        "RSI過熱": rsi >= cfg["rsi_min"],
        "MACD GC": macd_line > macd_sig,
        "ROC加速": (roc_now == roc_now and roc_prev == roc_prev and roc_now > roc_prev),
        "出来高増": vr >= cfg["vol_trend"],
        "200日線上方乖離": dev200 > 0,
    }
    hits = sum(1 for v in flags.values() if v)
    return {
        "ticker": sd.ticker,
        "name": sd.info.get("shortName"),
        "score": hits,                 # 0〜5
        "RSI": round(rsi, 1),
        "ROC%": round(roc_now, 1) if roc_now == roc_now else None,
        "乖離200%": round(dev200, 1) if dev200 == dev200 else None,
        "該当": [k for k, v in flags.items() if v],
    }
