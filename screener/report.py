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


SECTION_META = {
    "value":      ("バリュースクリーニング（割安株 / 100点）", 100, "バリュー"),
    "contrarian": ("逆張り（売られすぎ / 0-6）", 6, "逆張り"),
    "momentum":   ("モメンタム（強い銘柄 / 0-5）", 5, "モメンタム"),
}

_HTML_HEAD = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>株スクリーニングレポート</title>
<style>
 body{font-family:'Segoe UI','Meiryo',sans-serif;margin:24px;color:#222;background:#fafafa}
 h1{font-size:22px} h2{font-size:17px;border-left:5px solid #305496;padding-left:8px;margin-top:28px}
 section{background:#fff;border:1px solid #e3e3e3;border-radius:8px;padding:14px 18px;margin:14px 0}
 table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}
 th{background:#305496;color:#fff;padding:6px 8px;text-align:left;white-space:nowrap}
 td{border-bottom:1px solid #eee;padding:5px 8px}
 .empty{color:#999;font-style:italic}
 .gauge{text-align:center} .gauge .label{font-weight:bold;font-size:15px;margin:4px}
</style></head><body>"""


def _fmt(v):
    if isinstance(v, list):
        return " / ".join(v)
    return "" if v is None else str(v)


def _table_html(rows, top, max_val):
    if not rows:
        return "<p class='empty'>該当なし</p>"
    rows = rows[:top]
    cols = list(rows[0].keys())
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    body = []
    for r in rows:
        tds = []
        for c in cols:
            v = r.get(c)
            cell = html.escape(_fmt(v))
            if c == "score":
                tds.append(f'<td style="background:{_score_color(v, max_val)};'
                           f'text-align:right;font-weight:bold">{cell}</td>')
            else:
                tds.append(f"<td>{cell}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (f"<table><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>")


def build_html(sections, market, path, top=20):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    p = [_HTML_HEAD, "<h1>株スクリーニングレポート</h1>"]

    # 市況
    p.append("<section><h2>市場センチメント（Fear &amp; Greed）</h2>")
    if market.get("score") is not None:
        p.append(f"<div class='gauge'>{_svg_gauge(market['score'])}"
                 f"<p class='label'>{html.escape(str(market.get('label','')))}"
                 f"（VIX {html.escape(str(market.get('VIX')))}）</p></div>")
        uw = market.get("内訳", {})
        p.append(_svg_hbar([(k, v) for k, v in uw.items()], 100))
    else:
        p.append("<p class='empty'>市況データ取得失敗</p>")
    p.append("</section>")

    # 各スクリーニング
    for key, (title, mv, _sheet) in SECTION_META.items():
        rows = sections.get(key, [])
        p.append(f"<section><h2>{html.escape(title)}</h2>")
        p.append(_table_html(rows, top, mv))
        bar = [(r.get("name") or r["ticker"], r["score"]) for r in rows[:10]]
        p.append(_svg_hbar(bar, mv))
        p.append("</section>")

    p.append("</body></html>")
    path.write_text("\n".join(p), encoding="utf-8")
    return path
