"""バリュースコア（Vol.1）。

PER(25) + PBR(25) + 配当利回り(20) + ROE(15) + 売上成長率(15) = 100点。
各指標を config の境界値で 0〜満点に線形マッピングする。
"""
from __future__ import annotations

from .data import StockData


def _lerp(x: float | None, full: float, zero: float, weight: float) -> float:
    """x を [zero→0点, full→満点] に線形変換。full<zero でも逆向き対応。"""
    if x is None:
        return 0.0
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    if full == zero:
        return 0.0
    frac = (x - zero) / (full - zero)
    frac = max(0.0, min(1.0, frac))
    return frac * weight


def value_score(sd: StockData, weights: dict, bounds: dict) -> dict:
    info = sd.info
    per = info.get("trailingPE")
    pbr = info.get("priceToBook")
    # yfinance の dividendYield / returnOnEquity / revenueGrowth は版により
    # 小数(0.04)か百分率(4.0)で返る。1未満なら%換算する。
    div = info.get("dividendYield")
    roe = info.get("returnOnEquity")
    grw = info.get("revenueGrowth")
    div = (div * 100 if div is not None and div < 1 else div)
    roe = (roe * 100 if roe is not None and abs(roe) < 1 else roe)
    grw = (grw * 100 if grw is not None and abs(grw) < 1 else grw)
    # 異常値サニタイズ: 配当利回り>30% は yfinance のデータ不良とみなし無効化
    if div is not None and div > 30:
        div = None

    # PER/PBR は負（赤字等）なら加点しない
    s_per = _lerp(per, bounds["per"]["full"], bounds["per"]["zero"], weights["per"]) if (per and per > 0) else 0.0
    s_pbr = _lerp(pbr, bounds["pbr"]["full"], bounds["pbr"]["zero"], weights["pbr"]) if (pbr and pbr > 0) else 0.0
    s_div = _lerp(div, bounds["dividend"]["full"], bounds["dividend"]["zero"], weights["dividend"])
    s_roe = _lerp(roe, bounds["roe"]["full"], bounds["roe"]["zero"], weights["roe"])
    s_grw = _lerp(grw, bounds["growth"]["full"], bounds["growth"]["zero"], weights["growth"])

    total = s_per + s_pbr + s_div + s_roe + s_grw
    return {
        "ticker": sd.ticker,
        "name": info.get("shortName"),
        "score": round(total, 1),
        "PER": round(per, 1) if per else None,
        "PBR": round(pbr, 2) if pbr else None,
        "配当%": round(div, 2) if div is not None else None,
        "ROE%": round(roe, 1) if roe is not None else None,
        "売上成長%": round(grw, 1) if grw is not None else None,
    }
