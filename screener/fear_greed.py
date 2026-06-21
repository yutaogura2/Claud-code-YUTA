"""Fear & Greed スコア（Vol.3）。

市場全体の過熱/恐怖を6指標合成で 0〜100 点化する。
基準指数（日経平均）+ VIX を使用。高いほど Greed（強気）。
"""
from __future__ import annotations

from . import indicators as ind
from .data import fetch


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def fear_greed(index_ticker: str, vix_ticker: str, ttl: int) -> dict:
    idx = fetch(index_ticker, ttl=ttl, period="2y")
    if not idx.ok:
        return {"score": None, "label": "データ取得失敗"}

    close = idx.history["Close"]
    vol = idx.history["Volume"]
    price = float(close.iloc[-1])

    # 1. RSI(14): 0→100 をそのまま
    rsi = ind.rsi(close)
    s_rsi = _clamp(rsi, 0, 100)

    # 2. SMA50 乖離: -5%→0, +5%→100
    dev50 = ind.deviation_pct(price, ind.sma(close, 50))
    s_sma50 = _clamp((dev50 + 5) / 10 * 100, 0, 100)

    # 3. SMA200 乖離: -10%→0, +10%→100
    dev200 = ind.deviation_pct(price, ind.sma(close, 200))
    s_sma200 = _clamp((dev200 + 10) / 20 * 100, 0, 100)

    # 4. 52週高値からの距離: -20%→0, 0%→100
    d_high = ind.dist_from_high(close)
    s_high = _clamp((d_high + 20) / 20 * 100, 0, 100)

    # 5. 出来高比: 0.7→0(閑散=fear気味), 1.3→100
    vr = ind.volume_ratio(vol)
    s_vol = _clamp((vr - 0.7) / 0.6 * 100, 0, 100) if vr == vr else 50.0

    # 6. VIX: 高い=fear。VIX10→100(greed), 40→0(fear)
    vx = fetch(vix_ticker, ttl=ttl, period="6mo")
    if vx.ok:
        vix_val = float(vx.history["Close"].iloc[-1])
        s_vix = _clamp((40 - vix_val) / 30 * 100, 0, 100)
    else:
        vix_val, s_vix = None, 50.0

    parts = {
        "RSI": s_rsi, "SMA50乖離": s_sma50, "SMA200乖離": s_sma200,
        "52週高値距離": s_high, "出来高比": s_vol, "VIX": s_vix,
    }
    score = round(sum(parts.values()) / len(parts), 1)

    if score >= 75:   label = "極度の強欲(Extreme Greed)"
    elif score >= 55: label = "強欲(Greed)"
    elif score >= 45: label = "中立(Neutral)"
    elif score >= 25: label = "恐怖(Fear)"
    else:             label = "極度の恐怖(Extreme Fear)"

    return {
        "score": score,
        "label": label,
        "VIX": round(vix_val, 1) if vix_val is not None else None,
        "内訳": {k: round(v, 0) for k, v in parts.items()},
    }
