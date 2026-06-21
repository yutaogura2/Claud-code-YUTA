import numpy as np
import pandas as pd
from screener import screen
from screener.data import StockData

CFG = {
    "value_weights": {"per": 25, "pbr": 25, "dividend": 20, "roe": 15, "growth": 15},
    "value_bounds": {
        "per": {"full": 8, "zero": 25}, "pbr": {"full": 0.8, "zero": 3.0},
        "dividend": {"full": 4.0, "zero": 0.0}, "roe": {"full": 15.0, "zero": 0.0},
        "growth": {"full": 15.0, "zero": 0.0},
    },
    "min_score": 50,
}


def _stock(ticker, per, good=True):
    idx = pd.date_range("2025-01-01", periods=5, freq="B")
    hist = pd.DataFrame({"Close": [100] * 5, "Volume": [1] * 5}, index=idx)
    info = {"shortName": ticker, "trailingPE": per,
            "priceToBook": 1.0 if good else 5.0,
            "dividendYield": 4.0 if good else 0.0,
            "returnOnEquity": 0.15 if good else 0.0,
            "revenueGrowth": 0.15 if good else 0.0}
    return StockData(ticker, info, hist)


def test_compute_value_filters_and_sorts():
    stocks = [_stock("A.T", 8, True), _stock("B.T", 30, False)]
    rows = screen.compute_value(CFG, stocks)
    assert [r["ticker"] for r in rows] == ["A.T"]  # B は min_score未満で除外
