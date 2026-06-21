"""テクニカル指標。RSI / SMA / ボリンジャーバンド / MACD / ROC / 出来高比。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    val = 100 - 100 / (1 + rs)
    return float(val.iloc[-1]) if not val.empty and not np.isnan(val.iloc[-1]) else float("nan")


def sma(close: pd.Series, period: int) -> float:
    if len(close) < period:
        return float("nan")
    return float(close.rolling(period).mean().iloc[-1])


def deviation_pct(price: float, ma: float) -> float:
    """移動平均からの乖離率(%)。負=下方乖離。"""
    if not ma or np.isnan(ma):
        return float("nan")
    return (price - ma) / ma * 100


def bollinger(close: pd.Series, period: int = 20, k: float = 2.0) -> tuple[float, float, float]:
    """(中心, 上限, 下限) を返す。"""
    if len(close) < period:
        return (float("nan"),) * 3
    mid = close.rolling(period).mean().iloc[-1]
    std = close.rolling(period).std().iloc[-1]
    return float(mid), float(mid + k * std), float(mid - k * std)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float]:
    """(MACD線, シグナル線) を返す。MACD>シグナル でゴールデンクロス気味。"""
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    line = ema_f - ema_s
    sig = line.ewm(span=signal, adjust=False).mean()
    return float(line.iloc[-1]), float(sig.iloc[-1])


def roc(close: pd.Series, period: int = 12) -> float:
    """変化率(%)。"""
    if len(close) <= period:
        return float("nan")
    return (close.iloc[-1] / close.iloc[-period - 1] - 1) * 100


def volume_ratio(volume: pd.Series, period: int = 20) -> float:
    """直近出来高 / 平均出来高。"""
    if len(volume) < period:
        return float("nan")
    avg = volume.rolling(period).mean().iloc[-1]
    if not avg:
        return float("nan")
    return float(volume.iloc[-1] / avg)


def dist_from_high(close: pd.Series, window: int = 252) -> float:
    """52週高値からの距離(%)。0に近いほど高値圏。"""
    w = close.tail(window)
    hi = w.max()
    if not hi:
        return float("nan")
    return (close.iloc[-1] - hi) / hi * 100
