"""逆張りスクリーニング（Vol.3）。

売られすぎ条件: RSI<=30 / 200日線下方乖離 / ボリンジャー下限割れ /
出来高急増 / 低PER・低PBR。条件該当数を contrarian_score とする。
"""
from __future__ import annotations

from . import indicators as ind
from .data import StockData


def contrarian_screen(sd: StockData, cfg: dict) -> dict | None:
    if not sd.ok:
        return None
    close = sd.history["Close"]
    vol = sd.history["Volume"]
    price = float(close.iloc[-1])

    rsi = ind.rsi(close)
    sma200 = ind.sma(close, 200)
    dev200 = ind.deviation_pct(price, sma200)
    _, _, bb_low = ind.bollinger(close)
    vr = ind.volume_ratio(vol)
    per = sd.info.get("trailingPE")
    pbr = sd.info.get("priceToBook")

    flags = {
        "RSI売られすぎ": rsi <= cfg["rsi_max"],
        "200日線下方乖離": dev200 < 0,
        "BB下限割れ": price < bb_low,
        "出来高急増": vr >= cfg["vol_surge"],
        "低PER": bool(per and 0 < per <= cfg["per_max"]),
        "低PBR": bool(pbr and 0 < pbr <= cfg["pbr_max"]),
    }
    hits = sum(1 for v in flags.values() if v)
    return {
        "ticker": sd.ticker,
        "name": sd.info.get("shortName"),
        "score": hits,                 # 0〜6（該当条件数）
        "RSI": round(rsi, 1),
        "乖離200%": round(dev200, 1) if dev200 == dev200 else None,
        "出来高比": round(vr, 2) if vr == vr else None,
        "該当": [k for k, v in flags.items() if v],
    }
