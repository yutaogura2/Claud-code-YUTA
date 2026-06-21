"""レポートテスト用のモックデータ（ネット非依存）。"""
import pytest


@pytest.fixture
def sections():
    return {
        "value": [
            {"ticker": "6902.T", "name": "DENSO CORP", "score": 86.0,
             "PER": 7.4, "PBR": 0.93, "配当%": 3.89, "ROE%": 8.9, "売上成長%": 9.1},
            {"ticker": "7203.T", "name": "TOYOTA MOTOR CORP", "score": 50.0,
             "PER": 9.4, "PBR": 0.91, "配当%": 3.6, "ROE%": 10.2, "売上成長%": 1.9},
        ],
        "contrarian": [
            {"ticker": "9432.T", "name": "NTT INC", "score": 5, "RSI": 40.1,
             "乖離200%": -5.3, "出来高比": 1.57,
             "該当": ["200日線下方乖離", "BB下限割れ", "低PER"]},
        ],
        "momentum": [],
    }


@pytest.fixture
def market():
    return {
        "score": 88.1, "label": "極度の強欲(Extreme Greed)", "VIX": 16.4,
        "内訳": {"RSI": 64, "SMA50乖離": 100, "SMA200乖離": 100,
                "52週高値距離": 100, "出来高比": 86, "VIX": 79},
    }
