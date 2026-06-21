from screener import alpha

WEIGHTS = {"accruals": 25, "sales_accel": 25, "fcf_margin": 25, "roe_trend": 25}
BOUNDS = {
    "accruals":    {"full": -0.05, "zero": 0.10},
    "sales_accel": {"full": 0.05,  "zero": -0.05},
    "fcf_margin":  {"full": 0.03,  "zero": -0.03},
    "roe_trend":   {"full": 0.03,  "zero": -0.03},
}
FIN_GOOD = {
    "revenue":      [121.0, 110.0, 100.0],
    "net_income":   [10.0, 8.0, 7.0],
    "ocf":          [12.0, 11.0, 10.0],
    "fcf":          [20.0, 15.0, 12.0],
    "total_assets": [200.0, 190.0, 180.0],
    "equity":       [100.0, 100.0, 95.0],
}


def test_lerp_bounds():
    assert alpha._lerp(8, 8, 25, 25) == 25
    assert alpha._lerp(25, 8, 25, 25) == 0
    assert alpha._lerp(16.5, 8, 25, 25) == 12.5


def test_change_score_submetrics():
    c = alpha.change_score(FIN_GOOD, WEIGHTS, BOUNDS)
    assert c["アクルーアルズ"] == -0.01      # (10-12)/200
    assert c["売上加速%"] == 0.0             # g0=0.10, g1=0.10
    assert c["FCFマージンΔ%"] == 2.9         # 0.1653-0.1364
    assert c["ROEΔ%"] == 2.0                 # 0.10-0.08
    assert 70 <= c["change"] <= 80           # 約76


def test_change_score_short_series_drops_accel():
    fin = {k: v[:2] for k, v in FIN_GOOD.items()}  # 2期のみ
    c = alpha.change_score(fin, WEIGHTS, BOUNDS)
    assert c is not None
    assert c["売上加速%"] is None            # 3期必要→無効
    assert c["ROEΔ%"] is not None


def test_change_score_all_missing_returns_none():
    fin = {k: [] for k in FIN_GOOD}
    assert alpha.change_score(fin, WEIGHTS, BOUNDS) is None


import numpy as np
import pandas as pd
from screener.data import StockData

CFG = {
    "value_weights": {"per": 25, "pbr": 25, "dividend": 20, "roe": 15, "growth": 15},
    "value_bounds": {
        "per": {"full": 8, "zero": 25}, "pbr": {"full": 0.8, "zero": 3.0},
        "dividend": {"full": 4.0, "zero": 0.0}, "roe": {"full": 15.0, "zero": 0.0},
        "growth": {"full": 15.0, "zero": 0.0},
    },
    "alpha_weights": WEIGHTS, "alpha_bounds": BOUNDS,
    "alpha_pullback": {"rsi_max": 35},
}


def _stock(decline=True):
    idx = pd.date_range("2025-01-01", periods=40, freq="B")
    prices = np.linspace(100, 80, 40) if decline else np.linspace(80, 100, 40)
    hist = pd.DataFrame({"Close": prices, "Volume": [1000] * 40}, index=idx)
    info = {"shortName": "TEST", "trailingPE": 10.0, "priceToBook": 1.0,
            "dividendYield": 3.0, "returnOnEquity": 0.10, "revenueGrowth": 0.08}
    return StockData("TEST.T", info, hist)


def test_alpha_screen_combines_value_and_change():
    r = alpha.alpha_screen(_stock(), FIN_GOOD, CFG)
    assert r is not None
    assert r["score"] == round((r["value"] + r["change"]) / 2, 1)
    assert r["change"] > 0
    assert r["押し目"] in ("○", "")


def test_alpha_screen_pullback_flag_on_decline():
    r = alpha.alpha_screen(_stock(decline=True), FIN_GOOD, CFG)
    assert r["押し目"] == "○"        # 下落基調→RSI低い


def test_alpha_screen_none_when_change_missing():
    fin = {k: [] for k in FIN_GOOD}
    assert alpha.alpha_screen(_stock(), fin, CFG) is None
