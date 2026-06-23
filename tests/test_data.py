import json
import pandas as pd
from screener import data as dataio


def test_row_parses_newest_first_and_nan():
    df = pd.DataFrame(
        {pd.Timestamp("2026-03-31"): [100.0],
         pd.Timestamp("2025-03-31"): [float("nan")]},
        index=["Total Revenue"],
    )
    assert dataio._row(df, "Total Revenue") == [100.0, None]


def test_row_missing_label_returns_empty():
    df = pd.DataFrame({pd.Timestamp("2026-03-31"): [1.0]}, index=["X"])
    assert dataio._row(df, "Total Revenue") == []


def test_fetch_history_uses_cache(tmp_path, monkeypatch):
    import pandas as pd
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=idx)
    dataio._write_cache("9999.T_hist_3y", {"history": df.to_json(orient="split", date_format="iso")})
    out = dataio.fetch_history("9999.T", period="3y")
    assert out is not None and list(out["Close"]) == [1.0, 2.0, 3.0]


def test_fetch_news_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    dataio._write_cache("9999.T_news", {"news": [["タイトルA", "https://example.com/a"]]})
    out = dataio.fetch_news("9999.T")
    assert out == [("タイトルA", "https://example.com/a")]


def test_fetch_financials_uses_cache(tmp_path, monkeypatch):
    # キャッシュを事前に書けば fetch_financials はネット無しで返す
    fin = {"revenue": [110.0, 100.0], "net_income": [10.0, 8.0],
           "ocf": [12.0, 11.0], "fcf": [20.0, 15.0],
           "total_assets": [200.0, 190.0], "equity": [100.0, 100.0]}
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    dataio._write_cache("9999.T_fin", {"fin": fin})
    assert dataio.fetch_financials("9999.T", ttl=86400) == fin
