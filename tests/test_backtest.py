from screener import backtest


def test_metrics_basic():
    m = backtest._metrics([1.0, 1.1, 0.99, 1.2], years=1.0)
    assert m["累積%"] == 20.0
    assert m["最大DD%"] == -10.0       # 1.1→0.99 で -10%
    assert m["期間"] == 3
    assert m["勝率%"] == 66.7          # 3期中2期プラス
    assert m["CAGR%"] == 20.0
