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


def test_fetch_universe_parallel_preserves_order(monkeypatch):
    from screener.data import StockData
    calls = []
    monkeypatch.setattr("screener.screen.dataio.fetch",
                        lambda t, ttl=86400: (calls.append(t), StockData(t))[1])
    cfg = {"universe": ["A.T", "B.T", "C.T"], "fetch": {"max_workers": 4}}
    out = screen.fetch_universe(cfg)
    assert [s.ticker for s in out] == ["A.T", "B.T", "C.T"]  # 並列でも順序維持
    assert sorted(calls) == ["A.T", "B.T", "C.T"]            # 全件取得


def test_compute_value_filters_and_sorts():
    stocks = [_stock("A.T", 8, True), _stock("B.T", 30, False)]
    rows = screen.compute_value(CFG, stocks)
    assert [r["ticker"] for r in rows] == ["A.T"]  # B は min_score未満で除外


def test_collect_extras_computes_ytd(monkeypatch):
    import numpy as np
    import pandas as pd
    from screener.data import StockData
    idx = pd.date_range("2026-01-02", periods=20, freq="B")
    hist = pd.DataFrame({"Close": np.linspace(100, 110, 20), "Volume": [1] * 20}, index=idx)
    s = StockData("7203.T", {"shortName": "x"}, hist)
    extras = screen.collect_extras([s], with_news=False)
    assert extras["7203.T"]["年初来%"] == 10.0
    assert extras["7203.T"]["news"] == []


def test_apply_names_overwrites_known_ticker():
    rows = [{"ticker": "7203.T", "name": "TOYOTA", "score": 1},
            {"ticker": "X.T", "name": "orig", "score": 1}]
    screen._apply_names(rows, {"7203.T": "トヨタ自動車"})
    assert rows[0]["name"] == "トヨタ自動車"
    assert rows[1]["name"] == "orig"   # マップに無ければ維持
