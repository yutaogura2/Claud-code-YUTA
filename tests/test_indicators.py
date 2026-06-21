import numpy as np
import pandas as pd
from screener import indicators as ind


def test_ytd_return_positive():
    idx = pd.date_range("2026-01-02", periods=20, freq="B")
    close = pd.Series(np.linspace(100, 120, 20), index=idx)
    assert round(ind.ytd_return(close), 1) == 20.0


def test_ytd_return_empty_is_nan():
    import math
    assert math.isnan(ind.ytd_return(pd.Series(dtype=float)))
