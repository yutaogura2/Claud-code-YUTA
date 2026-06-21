"""アルファスコア（Vol.1 AlphaScreener）。

財務諸表から業績変化スコア(4指標)を算出し、バリュースコア(割安)と
合算した2軸で銘柄を評価する。
"""
from __future__ import annotations

from . import indicators as ind
from .data import StockData
from .value import value_score


def _lerp(x, full, zero, weight):
    """x を [zero→0点, full→満点] に線形変換。full<zero でも逆向き対応。"""
    if x is None or full == zero:
        return 0.0
    frac = max(0.0, min(1.0, (x - zero) / (full - zero)))
    return frac * weight


def _safe(a, b):
    """a/b。引数欠損や分母0は None。"""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _get(seq, i):
    return seq[i] if seq is not None and len(seq) > i else None


def change_score(fin: dict, weights: dict, bounds: dict) -> dict | None:
    rev, ni = fin.get("revenue"), fin.get("net_income")
    ocf, fcf = fin.get("ocf"), fin.get("fcf")
    assets, eq = fin.get("total_assets"), fin.get("equity")

    total = 0.0
    valid = 0

    # 1. アクルーアルズ（利益の質）= (NI0 - OCF0)/Assets0。低いほど良い
    accr = None
    n0, o0, a0 = _get(ni, 0), _get(ocf, 0), _get(assets, 0)
    if n0 is not None and o0 is not None:
        accr = _safe(n0 - o0, a0)
    if accr is not None:
        b = bounds["accruals"]; total += _lerp(accr, b["full"], b["zero"], weights["accruals"]); valid += 1

    # 2. 売上加速度 = g0 - g1（3期必要）
    accel = None
    r0, r1, r2 = _get(rev, 0), _get(rev, 1), _get(rev, 2)
    g0, g1 = _safe(r0, r1), _safe(r1, r2)
    if g0 is not None and g1 is not None:
        accel = (g0 - 1) - (g1 - 1)
        b = bounds["sales_accel"]; total += _lerp(accel, b["full"], b["zero"], weights["sales_accel"]); valid += 1

    # 3. FCFマージン変化 = FCF0/Rev0 - FCF1/Rev1
    dmargin = None
    m0, m1 = _safe(_get(fcf, 0), r0), _safe(_get(fcf, 1), r1)
    if m0 is not None and m1 is not None:
        dmargin = m0 - m1
        b = bounds["fcf_margin"]; total += _lerp(dmargin, b["full"], b["zero"], weights["fcf_margin"]); valid += 1

    # 4. ROE趨勢 = NI0/Eq0 - NI1/Eq1
    droe = None
    roe0, roe1 = _safe(_get(ni, 0), _get(eq, 0)), _safe(_get(ni, 1), _get(eq, 1))
    if roe0 is not None and roe1 is not None:
        droe = roe0 - roe1
        b = bounds["roe_trend"]; total += _lerp(droe, b["full"], b["zero"], weights["roe_trend"]); valid += 1

    if valid == 0:
        return None
    return {
        "change": round(total, 1),
        "アクルーアルズ": round(accr, 3) if accr is not None else None,
        "売上加速%": round(accel * 100, 1) if accel is not None else None,
        "FCFマージンΔ%": round(dmargin * 100, 1) if dmargin is not None else None,
        "ROEΔ%": round(droe * 100, 1) if droe is not None else None,
    }


def alpha_screen(sd: StockData, fin: dict, cfg: dict) -> dict | None:
    if not sd.info:
        return None
    c = change_score(fin, cfg["alpha_weights"], cfg["alpha_bounds"])
    if c is None:
        return None
    v = value_score(sd, cfg["value_weights"], cfg["value_bounds"])

    pullback = False
    if sd.ok:
        close = sd.history["Close"]
        price = float(close.iloc[-1])
        rsi = ind.rsi(close)
        _, _, bb_low = ind.bollinger(close)
        pullback = (rsi <= cfg["alpha_pullback"]["rsi_max"]) or (price < bb_low)

    combined = (v["score"] + c["change"]) / 2
    return {
        "ticker": sd.ticker,
        "name": sd.info.get("shortName"),
        "score": round(combined, 1),
        "value": v["score"],
        "change": c["change"],
        "押し目": "○" if pullback else "",
        "アクルーアルズ": c["アクルーアルズ"],
        "売上加速%": c["売上加速%"],
        "FCFマージンΔ%": c["FCFマージンΔ%"],
        "ROEΔ%": c["ROEΔ%"],
    }
