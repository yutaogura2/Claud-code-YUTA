from screener import backtest


import numpy as np
import pandas as pd


def _series(values):
    idx = pd.date_range("2023-01-01", periods=len(values), freq="B")
    return pd.Series(values, index=idx)


def test_metrics_basic():
    m = backtest._metrics([1.0, 1.1, 0.99, 1.2], years=1.0)
    assert m["累積%"] == 20.0
    assert m["最大DD%"] == -10.0       # 1.1→0.99 で -10%
    assert m["期間"] == 3
    assert m["勝率%"] == 66.7          # 3期中2期プラス
    assert m["CAGR%"] == 20.0


def test_contrarian_score_on_decline():
    close = _series(np.linspace(200, 100, 260))   # 下落基調
    vol = _series([1000] * 260)
    s = backtest._contrarian_score(close, vol)
    assert 0 <= s <= 4 and s >= 1                  # 売られすぎ条件に該当


def test_momentum_score_on_rise():
    close = _series(np.linspace(100, 200, 260))    # 上昇基調
    vol = _series([1000] * 260)
    s = backtest._momentum_score(close, vol)
    assert 0 <= s <= 5 and s >= 1                  # 強さ条件に該当


def test_run_strategy_picks_riser():
    idx = pd.date_range("2023-01-01", periods=10, freq="B")
    up = pd.DataFrame({"Close": np.linspace(10, 20, 10), "Volume": [1] * 10}, index=idx)
    down = pd.DataFrame({"Close": np.linspace(20, 10, 10), "Volume": [1] * 10}, index=idx)
    histories = {"UP.T": up, "DOWN.T": down}
    score = lambda close, vol: 1 if close.iloc[-1] > close.iloc[0] else 0  # 上昇を選好
    res = backtest.run_strategy(histories, score, top_n=1, step=1, warmup=2)
    assert res["equity"][0] == 1.0
    assert res["metrics"]["累積%"] > 0          # 上昇銘柄を保有→プラス
    assert len(res["dates"]) >= 1


def test_run_backtest_keys():
    idx = pd.date_range("2023-01-01", periods=300, freq="B")
    a = pd.DataFrame({"Close": np.linspace(100, 200, 300), "Volume": [1000] * 300}, index=idx)
    b = pd.DataFrame({"Close": np.linspace(200, 100, 300), "Volume": [1000] * 300}, index=idx)
    bench = pd.Series(np.linspace(100, 150, 300), index=idx)
    cfg = {"backtest": {"top_n": 1, "rebalance_days": 21, "warmup_days": 60}}
    res = backtest.run_backtest({"A.T": a, "B.T": b}, bench, cfg)
    assert set(res) == {"contrarian", "momentum", "benchmark"}
    assert res["benchmark"] is not None and "累積%" in res["benchmark"]["metrics"]
