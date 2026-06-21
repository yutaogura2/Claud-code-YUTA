# レポート出力機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** スクリーニング結果を色付き表＋SVGグラフのHTMLと書式付きExcelに出力し、HTMLを自動で開く `report` コマンドを追加する。

**Architecture:** 算出ロジック（compute_*）を main.py から分離し、新規 `screener/report.py` が結果を受けて HTML（自前テンプレ＋インラインSVG）と Excel（openpyxl）を生成。`report` モードが全モード＋市況を集約して両ファイルを書き出し、HTMLをブラウザで開く。

**Tech Stack:** Python 3.12, yfinance(既存), openpyxl(新規), pytest(新規・テスト用), 標準ライブラリ(html, math, webbrowser)。

## Global Constraints

- 追加ランタイム依存は `openpyxl>=3.1` のみ（HTMLは標準ライブラリのみで生成、JS/CDN不要・オフライン動作）。
- Python 実行は venv 経由: `.venv\Scripts\python`（PowerShell、プロジェクトルートから）。
- 出力先: `data/reports/`（既存 `.gitignore` の `data/` で除外済）。
- コメント・UI文言は日本語。既存コードのスタイル（端的な日本語docstring）に合わせる。
- テストはネット非依存（モックの rows / market を使う）。

---

### Task 1: 依存追加・テスト基盤・色ヘルパ

**Files:**
- Modify: `requirements.txt`
- Create: `screener/report.py`
- Create: `tests/conftest.py`
- Create: `tests/test_report.py`

**Interfaces:**
- Produces: `screener.report._mix(c1, c2, t) -> tuple`、`screener.report._score_color(score: float|None, max_score: float=100) -> str`（"#rrggbb"）。

- [ ] **Step 1: 依存追加とインストール**

`requirements.txt` に追記:
```
openpyxl>=3.1
```
インストール（pytestも入れる）:
```
.venv\Scripts\python -m pip install openpyxl pytest
```
Expected: `Successfully installed openpyxl-... pytest-...`

- [ ] **Step 2: フィクスチャ作成**

Create `tests/conftest.py`:
```python
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
```

- [ ] **Step 3: 失敗するテストを書く**

Create `tests/test_report.py`:
```python
from screener import report


def test_score_color_none_is_grey():
    assert report._score_color(None) == "#eeeeee"


def test_score_color_returns_hex():
    c = report._score_color(50, 100)
    assert c.startswith("#") and len(c) == 7


def test_score_color_high_is_greener_than_low():
    low = report._score_color(0, 100)
    high = report._score_color(100, 100)
    # 緑チャンネル(3-4文字目)が高スコアで大きい
    assert int(high[3:5], 16) > int(low[3:5], 16)
```

- [ ] **Step 4: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'screener.report'`）

- [ ] **Step 5: 最小実装**

Create `screener/report.py`:
```python
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
```

- [ ] **Step 6: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -v`
Expected: PASS（3 passed）

- [ ] **Step 7: コミット**

```bash
git add requirements.txt screener/report.py tests/
git commit -m "feat(report): 色ヘルパとテスト基盤を追加"
```

---

### Task 2: SVGグラフヘルパ

**Files:**
- Modify: `screener/report.py`
- Modify: `tests/test_report.py`

**Interfaces:**
- Consumes: `_score_color`。
- Produces: `_svg_hbar(items: list[tuple[str, float]], max_val: float, width=380, bar_h=22, gap=6) -> str`、`_svg_gauge(score: float|None) -> str`。いずれも `<svg ...>...</svg>` 文字列（空 items の場合 `_svg_hbar` は ""）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_report.py` に追記:
```python
def test_svg_hbar_contains_labels():
    svg = report._svg_hbar([("デンソー", 86.0), ("トヨタ", 50.0)], 100)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "デンソー" in svg and "トヨタ" in svg


def test_svg_hbar_empty_is_blank():
    assert report._svg_hbar([], 100) == ""


def test_svg_gauge_shows_score():
    svg = report._svg_gauge(88)
    assert svg.startswith("<svg") and "88" in svg


def test_svg_gauge_none_is_zero():
    svg = report._svg_gauge(None)
    assert ">0<" in svg
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -k "svg" -v`
Expected: FAIL（`AttributeError: ... has no attribute '_svg_hbar'`）

- [ ] **Step 3: 最小実装**

`screener/report.py` の `_score_color` の後に追記:
```python
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
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -k "svg" -v`
Expected: PASS（4 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/report.py tests/test_report.py
git commit -m "feat(report): SVG横棒グラフとゲージを追加"
```

---

### Task 3: HTML生成（build_html）

**Files:**
- Modify: `screener/report.py`
- Modify: `tests/test_report.py`

**Interfaces:**
- Consumes: `_score_color`, `_svg_hbar`, `_svg_gauge`。
- Produces: モジュール定数 `SECTION_META`、`_fmt(v) -> str`、`_table_html(rows, top, max_val) -> str`、`build_html(sections: dict, market: dict, path, top: int=20) -> Path`。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_report.py` に追記:
```python
def test_build_html_writes_file(tmp_path, sections, market):
    out = report.build_html(sections, market, tmp_path / "r.html")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "DENSO CORP" in text          # バリュー銘柄
    assert "NTT INC" in text             # 逆張り銘柄
    assert "バリュー" in text and "逆張り" in text and "モメンタム" in text
    assert "極度の強欲" in text          # 市況ラベル


def test_build_html_empty_section_shows_none(tmp_path, sections, market):
    out = report.build_html(sections, market, tmp_path / "r.html")
    # momentum は空 → 「該当なし」
    assert "該当なし" in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -k "build_html" -v`
Expected: FAIL（`AttributeError: ... 'build_html'`）

- [ ] **Step 3: 最小実装**

`screener/report.py` に追記:
```python
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
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -k "build_html" -v`
Expected: PASS（2 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/report.py tests/test_report.py
git commit -m "feat(report): HTMLレポート生成を追加"
```

---

### Task 4: Excel生成（build_excel）

**Files:**
- Modify: `screener/report.py`
- Modify: `tests/test_report.py`

**Interfaces:**
- Consumes: モジュール定数 `SECTION_META`（Task 3 で定義済）。
- Produces: `build_excel(sections: dict, market: dict, path, top: int=20) -> Path`。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_report.py` に追記:
```python
def test_build_excel_sheets(tmp_path, sections, market):
    import openpyxl
    out = report.build_excel(sections, market, tmp_path / "r.xlsx")
    assert out.exists()
    wb = openpyxl.load_workbook(out)
    for s in ["サマリ", "バリュー", "逆張り", "モメンタム", "市況"]:
        assert s in wb.sheetnames


def test_build_excel_value_has_ticker(tmp_path, sections, market):
    import openpyxl
    out = report.build_excel(sections, market, tmp_path / "r.xlsx")
    wb = openpyxl.load_workbook(out)
    vals = [c.value for row in wb["バリュー"].iter_rows() for c in row]
    assert "6902.T" in vals and "score" in vals


def test_build_excel_empty_sheet(tmp_path, sections, market):
    import openpyxl
    out = report.build_excel(sections, market, tmp_path / "r.xlsx")
    wb = openpyxl.load_workbook(out)
    assert wb["モメンタム"]["A1"].value == "該当なし"
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -k "excel" -v`
Expected: FAIL（`AttributeError: ... 'build_excel'`）

- [ ] **Step 3: 最小実装**

`screener/report.py` に追記:
```python
def build_excel(sections, market, path, top=20):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.chart import BarChart, Reference
    from openpyxl.utils import get_column_letter

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    # サマリシート
    ws = wb.active
    ws.title = "サマリ"
    ws["A1"] = "株スクリーニングレポート"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A3"] = "市況 Fear&Greed"; ws["B3"] = market.get("score")
    ws["A4"] = "判定";            ws["B4"] = market.get("label")
    ws["A5"] = "VIX";             ws["B5"] = market.get("VIX")
    row = 7
    for key, (title, mv, _sheet) in SECTION_META.items():
        ws.cell(row, 1, title).font = Font(bold=True)
        ws.cell(row, 2, f"{len(sections.get(key, []))} 件")
        row += 1
    ws.column_dimensions["A"].width = 36

    header_fill = PatternFill("solid", fgColor="305496")
    header_font = Font(bold=True, color="FFFFFF")

    # 各スクリーニングシート
    for key, (title, mv, sheet) in SECTION_META.items():
        rows = sections.get(key, [])[:top]
        ws = wb.create_sheet(sheet)
        if not rows:
            ws["A1"] = "該当なし"
            continue
        cols = list(rows[0].keys())
        for ci, c in enumerate(cols, 1):
            cell = ws.cell(1, ci, c)
            cell.fill = header_fill
            cell.font = header_font
        for ri, r in enumerate(rows, 2):
            for ci, c in enumerate(cols, 1):
                v = r.get(c)
                ws.cell(ri, ci, " / ".join(v) if isinstance(v, list) else v)
        ws.freeze_panes = "A2"
        # スコア列カラースケール
        if "score" in cols:
            col = get_column_letter(cols.index("score") + 1)
            rng = f"{col}2:{col}{len(rows) + 1}"
            ws.conditional_formatting.add(rng, ColorScaleRule(
                start_type="num", start_value=0, start_color="F8696B",
                mid_type="num", mid_value=mv / 2, mid_color="FFEB84",
                end_type="num", end_value=mv, end_color="63BE7B"))

    # 市況シート（内訳）
    ws = wb.create_sheet("市況")
    ws["A1"] = "指標"; ws["B1"] = "スコア"
    ws["A1"].fill = ws["B1"].fill = header_fill
    ws["A1"].font = ws["B1"].font = header_font
    for i, (k, v) in enumerate(market.get("内訳", {}).items(), 2):
        ws.cell(i, 1, k); ws.cell(i, 2, v)

    # バリューに棒グラフ（スコア上位）
    vrows = sections.get("value", [])[:top]
    if vrows and "score" in vrows[0]:
        vs = wb["バリュー"]
        cols = list(vrows[0].keys())
        sc = cols.index("score") + 1
        namec = (cols.index("name") + 1) if "name" in cols else 1
        chart = BarChart()
        chart.type = "bar"
        chart.title = "バリュースコア"
        data = Reference(vs, min_col=sc, min_row=1, max_row=len(vrows) + 1)
        cats = Reference(vs, min_col=namec, min_row=2, max_row=len(vrows) + 1)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.height = 8; chart.width = 16
        vs.add_chart(chart, f"{get_column_letter(len(cols) + 2)}2")

    wb.save(path)
    return path
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -k "excel" -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 全テスト確認**

Run: `.venv\Scripts\python -m pytest tests/ -v`
Expected: PASS（全件）

- [ ] **Step 6: コミット**

```bash
git add screener/report.py tests/test_report.py
git commit -m "feat(report): Excelレポート生成を追加"
```

---

### Task 5: main.py の算出/表示分離（compute_* 抽出）

**Files:**
- Modify: `main.py:68-100`

**Interfaces:**
- Produces: `compute_value(cfg, stocks) -> list[dict]`、`compute_contrarian(cfg, stocks) -> list[dict]`、`compute_momentum(cfg, stocks) -> list[dict]`（スコア降順・フィルタ済の rows）。`run_value/run_contrarian/run_momentum` は内部で compute_* を呼ぶよう変更（外部挙動・出力は不変）。

- [ ] **Step 1: 既存挙動のスナップショットを確認**

Run: `.venv\Scripts\python main.py value --top 5 --no-save`
Expected: バリュースクリーニング表が表示される（キャッシュ利用で数秒）。出力を控えておく。

- [ ] **Step 2: compute_* を追加し run_* を置換**

`main.py` の `run_value`/`run_contrarian`/`run_momentum`（68-87行）を以下に置換:
```python
def compute_value(cfg, stocks):
    rows = [val.value_score(s, cfg["value_weights"], cfg["value_bounds"])
            for s in stocks if s.ok]
    rows = [r for r in rows if r["score"] >= cfg.get("min_score", 0)]
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def compute_contrarian(cfg, stocks):
    rows = [r for s in stocks if (r := cont.contrarian_screen(s, cfg["contrarian"]))]
    rows = [r for r in rows if r["score"] >= 1]
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def compute_momentum(cfg, stocks):
    rows = [r for s in stocks if (r := mom.momentum_screen(s, cfg["momentum"]))]
    rows = [r for r in rows if r["score"] >= 1]
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def run_value(cfg, stocks, top, save):
    rows = compute_value(cfg, stocks)
    _attach_diff_and_show("value", rows, top, save, "■ バリュースクリーニング（割安株 / 100点満点）")


def run_contrarian(cfg, stocks, top, save):
    rows = compute_contrarian(cfg, stocks)
    _attach_diff_and_show("contrarian", rows, top, save, "■ 逆張り（売られすぎ / 該当条件数 0-6）")


def run_momentum(cfg, stocks, top, save):
    rows = compute_momentum(cfg, stocks)
    _attach_diff_and_show("momentum", rows, top, save, "■ モメンタム（強い銘柄 / 該当条件数 0-5）")
```

- [ ] **Step 3: 挙動が不変なことを確認**

Run: `.venv\Scripts\python main.py value --top 5 --no-save`
Expected: Step 1 と同じ表が出る。

- [ ] **Step 4: コミット**

```bash
git add main.py
git commit -m "refactor: スクリーニングの算出と表示を分離(compute_*)"
```

---

### Task 6: report モード追加・自動オープン・README

**Files:**
- Modify: `main.py`（import, argparse choices, report 関数, main 分岐）
- Modify: `README.md`

**Interfaces:**
- Consumes: `compute_value/compute_contrarian/compute_momentum`、`fg.fear_greed`、`report.build_html`、`report.build_excel`。

- [ ] **Step 1: import に report と webbrowser を追加**

`main.py` の import 群（15-28行付近）に追記:
```python
import webbrowser

from screener import report as report_mod
```

- [ ] **Step 2: report 実行関数を追加**

`main.py` の `run_market` 定義の後に追記:
```python
def run_report(cfg, stocks, top, open_after):
    sections = {
        "value": compute_value(cfg, stocks),
        "contrarian": compute_contrarian(cfg, stocks),
        "momentum": compute_momentum(cfg, stocks),
    }
    market = fg.fear_greed(cfg["index"], cfg["vix"], cfg.get("cache_ttl", 86400))

    rdir = ROOT / "data" / "reports"
    from datetime import date
    stamp = f"{date.today():%Y%m%d}"
    html_path = report_mod.build_html(sections, market, rdir / f"report_{stamp}.html", top)
    xlsx_path = report_mod.build_excel(sections, market, rdir / f"report_{stamp}.xlsx", top)
    print(f"HTML : {html_path.relative_to(ROOT)}")
    print(f"Excel: {xlsx_path.relative_to(ROOT)}")

    if open_after:
        try:
            webbrowser.open(html_path.as_uri())
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] 自動オープン失敗: {e}")
```

- [ ] **Step 3: argparse に report と --no-open を追加**

`main.py` の argparse（116-119行付近）を変更:
```python
    p.add_argument("mode", choices=["value", "contrarian", "momentum",
                                    "market", "all", "report"])
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--no-open", action="store_true", help="reportでHTMLを自動で開かない")
```

- [ ] **Step 4: main の分岐に report を追加**

`main.py` の `stocks = _fetch_all(cfg)` の後（130行付近）に追記:
```python
    if a.mode == "report":
        run_report(cfg, stocks, a.top, open_after=not a.no_open)
        return
```

- [ ] **Step 5: 実行確認**

Run: `.venv\Scripts\python main.py report --top 10 --no-open`
Expected: `HTML : data\reports\report_YYYYMMDD.html` と `Excel: ...xlsx` が表示され、両ファイルが生成される。

- [ ] **Step 6: 生成物の中身確認**

Run: `.venv\Scripts\python -c "from pathlib import Path; import glob; f=sorted(glob.glob('data/reports/*.html'))[-1]; t=Path(f).read_text(encoding='utf-8'); print('OK' if 'スクリーニングレポート' in t and '<svg' in t else 'NG')"`
Expected: `OK`

- [ ] **Step 7: README 更新**

`README.md` の「## 使い方」のコマンド一覧に追記:
```
.\run.ps1 report        # HTML+Excelレポートを生成しHTMLを自動で開く
```
オプション行に `--no-open`（reportでHTMLを開かない）を追記。
「## 出力」に `data/reports/report_<日付>.html / .xlsx` を追記。

- [ ] **Step 8: 全テスト + コミット**

```bash
.venv\Scripts\python -m pytest tests/ -v
git add main.py README.md
git commit -m "feat(report): reportコマンドとHTML自動オープンを追加"
```

---

## Self-Review

- **Spec coverage:** HTML+Excel両方(Task3,4) / 1ファイル統合(SECTION_METAで全モードを1ファイルに) / グラフあり(SVG: Task2,3、Excel BarChart: Task4) / 自動オープン(Task6) / compute_*分離(Task5) / openpyxl依存(Task1) / エラー処理(該当なし表示・自動オープンtry-except) / テスト(各Task TDD)。全項目カバー。
- **Placeholder scan:** プレースホルダなし。各ステップに実コード記載。
- **Type consistency:** `build_html(sections, market, path, top)` / `build_excel(同)` 一致。`SECTION_META` は (title, max_val, sheet) の3タプルで Task3/4 共通。`compute_*(cfg, stocks)->rows` を Task5 定義・Task6 消費で一致。
