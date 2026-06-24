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
