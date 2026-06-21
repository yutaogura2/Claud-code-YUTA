"""HTML / Excel レポート生成。

スクリーニング結果(セクション)と市況(Fear&Greed)を、色付き表 +
インラインSVGグラフの 1ファイル HTML と、書式付き Excel に出力する。
"""
from __future__ import annotations

import html
import math
from pathlib import Path


def _mix(c1, c2, t):
    """2色(0-1のRGBタプル)を t で線形補間。"""
    return tuple(a + (b - a) * t for a, b in zip(c1, c2))


def _score_color(score, max_score=100):
    """スコアを赤(低)→黄→緑(高)の hex 色 "#rrggbb" に変換。"""
    if score is None:
        return "#eeeeee"
    f = score / max_score if max_score else 0
    f = max(0.0, min(1.0, f))
    red, yellow, green = (0.85, 0.19, 0.15), (1.0, 0.85, 0.20), (0.10, 0.60, 0.31)
    if f < 0.5:
        r, g, b = _mix(red, yellow, f / 0.5)
    else:
        r, g, b = _mix(yellow, green, (f - 0.5) / 0.5)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
