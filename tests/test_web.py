import pytest
from screener import fear_greed as fg
from screener import screen
from web.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_home_lists_modes(client):
    html = client.get("/").get_data(as_text=True)
    assert "value" in html and "alpha" in html and "market" in html


def test_screen_value_links_ticker(client, monkeypatch):
    monkeypatch.setattr(screen, "fetch_universe", lambda cfg: [])
    monkeypatch.setattr(screen, "compute_value",
                        lambda cfg, stocks: [{"ticker": "7203.T", "name": "TOYOTA", "score": 80.0}])
    html = client.get("/screen?mode=value&top=5").get_data(as_text=True)
    assert "TOYOTA" in html and '/stock/7203.T' in html


def test_screen_market(client, monkeypatch):
    monkeypatch.setattr(fg, "fear_greed",
                        lambda i, v, ttl: {"score": 88.0, "label": "強欲",
                                           "VIX": 16.0, "内訳": {"RSI": 60}})
    html = client.get("/screen?mode=market").get_data(as_text=True)
    assert "強欲" in html and "<svg" in html


def test_screen_bad_mode_400(client):
    assert client.get("/screen?mode=bogus").status_code == 400


def test_stock_detail(client, monkeypatch):
    import numpy as np
    import pandas as pd
    from screener import data as dataio
    from screener.data import StockData
    idx = pd.date_range("2025-01-01", periods=30, freq="B")
    hist = pd.DataFrame({"Close": np.linspace(100, 120, 30), "Volume": [1] * 30}, index=idx)
    info = {"shortName": "TOYOTA", "trailingPE": 10.0, "priceToBook": 1.0,
            "dividendYield": 3.0, "returnOnEquity": 0.1, "revenueGrowth": 0.08}
    monkeypatch.setattr(dataio, "fetch", lambda t, ttl=86400: StockData("7203.T", info, hist))
    monkeypatch.setattr(dataio, "fetch_financials", lambda t, ttl=86400: None)
    html = client.get("/stock/7203.T").get_data(as_text=True)
    assert "TOYOTA" in html
    assert "バリュー内訳" in html
    assert "財務データなし" in html
