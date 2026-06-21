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


def _svg_hbar(items, max_val, width=380, bar_h=22, gap=6):
    """items=[(label, value)] の横棒グラフ SVG を返す。空なら ""。"""
    if not items:
        return ""
    n = len(items)
    height = n * (bar_h + gap) + gap
    label_w = 130
    bar_area = width - label_w - 45
    out = []
    for i, (label, value) in enumerate(items):
        y = gap + i * (bar_h + gap)
        v = value if (value is not None and value == value) else 0
        w = max(2, bar_area * (v / max_val if max_val else 0))
        color = _score_color(v, max_val)
        lab = html.escape(str(label))
        out.append(
            f'<text x="0" y="{y+bar_h*0.7:.0f}" font-size="12">{lab}</text>'
            f'<rect x="{label_w}" y="{y}" width="{w:.0f}" height="{bar_h}" '
            f'fill="{color}" rx="3"/>'
            f'<text x="{label_w+w+5:.0f}" y="{y+bar_h*0.7:.0f}" '
            f'font-size="11">{v}</text>'
        )
    return (f'<svg viewBox="0 0 {width} {height}" width="{width}" '
            f'xmlns="http://www.w3.org/2000/svg">' + "".join(out) + "</svg>")


def _svg_gauge(score):
    """0-100 の半円ゲージ SVG。score=None は 0 扱い。"""
    s = 0 if score is None else max(0, min(100, score))
    angle = math.pi * (1 - s / 100)  # 0点=左(180°), 100点=右(0°)
    cx, cy, r = 110, 110, 90
    x = cx + r * math.cos(angle)
    y = cy - r * math.sin(angle)
    return (
        '<svg viewBox="0 0 220 130" width="220" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<path d="M20 110 A90 90 0 0 1 200 110" fill="none" '
        'stroke="#ddd" stroke-width="16"/>'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{_score_color(s)}"/>'
        f'<text x="110" y="100" font-size="30" text-anchor="middle" '
        f'font-weight="bold">{int(s)}</text>'
        '</svg>'
    )
