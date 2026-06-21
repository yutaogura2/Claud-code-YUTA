# Web UI 改善 Implementation Plan（レポート出力・日本語名・単位）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Web UIからレポート（統合HTML＋Excelダウンロード）を出せるようにし、銘柄名を日本語化し、各数値に単位を付ける。

**Architecture:** `report.py` に表示ヘッダ単位付与・HTML文字列/Workbook生成の関数を追加。`screen.py` で日本語名を上書き。`web/app.py` に `/report`・`/report.xlsx` を追加。内部データキーは不変。

**Tech Stack:** Flask, openpyxl, 既存スタック, pytest。追加依存なし。

## Global Constraints

- 追加依存なし。Python実行は venv 経由: `.venv\Scripts\python`（PowerShell、プロジェクトルートから）。
- 内部のdictキー（`ticker`/`score` 等）は変更しない（store・前回比・web互換を維持）。単位は表示ヘッダのみ。
- 日本語名はマップに無ければ従来名にフォールバック（エラーにしない）。
- Excelダウンロードはディスクに残さず BytesIO で返す。
- テストはネット非依存（monkeypatch / モック）。

---

### Task 1: 単位付きヘッダ（report.header_label）と表・CLIへの適用

**Files:**
- Modify: `screener/report.py`
- Modify: `main.py`
- Modify: `tests/test_report.py`

**Interfaces:**
- Produces: `report.UNITS`(dict), `report.header_label(col) -> str`。`_table_html` のヘッダが単位付きになる。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_report.py` に追記:
```python
def test_header_label_adds_units():
    assert report.header_label("score") == "score（点）"
    assert report.header_label("PER") == "PER（倍）"
    assert report.header_label("出来高比") == "出来高比（倍）"


def test_header_label_keeps_percent_columns():
    assert report.header_label("配当%") == "配当%"
    assert report.header_label("RSI") == "RSI"


def test_table_html_header_has_unit():
    rows = [{"ticker": "7203.T", "score": 80, "PER": 9.4}]
    out = report._table_html(rows, 10, 100)
    assert "score（点）" in out and "PER（倍）" in out
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -k "header or unit" -v`
Expected: FAIL（`AttributeError: ... 'header_label'`）

- [ ] **Step 3: report に UNITS と header_label を追加**

`screener/report.py` の `_fmt` 関数の直前に追記:
```python
UNITS = {"score": "点", "value": "点", "change": "点",
         "PER": "倍", "PBR": "倍", "出来高比": "倍"}


def header_label(col):
    """表示用の列見出し。単位があれば付ける（内部キーは不変）。"""
    u = UNITS.get(col)
    return f"{col}（{u}）" if u else str(col)
```

- [ ] **Step 4: _table_html のヘッダを単位付きにする**

`screener/report.py` の `_table_html` 内のヘッダ生成行を置換:
```python
    head = "".join(f"<th>{html.escape(header_label(c))}</th>" for c in cols)
```

- [ ] **Step 5: CLI のヘッダも単位付きにする**

`main.py` の `_print_table` を置換:
```python
def _print_table(rows: list[dict], top: int):
    if not rows:
        print("該当なし")
        return
    rows = rows[:top]
    cols = list(rows[0].keys())
    labels = {c: report_mod.header_label(c) for c in cols}
    widths = {c: max(len(labels[c]), *(len(_cell(r.get(c))) for r in rows)) for c in cols}
    print(" | ".join(labels[c].ljust(widths[c]) for c in cols))
    print("-+-".join("-" * widths[c] for c in cols))
    for r in rows:
        print(" | ".join(_cell(r.get(c)).ljust(widths[c]) for c in cols))
```

- [ ] **Step 6: テストと既存全テストを確認**

Run: `.venv\Scripts\python -m pytest tests/ -q`
Expected: PASS（全件）

- [ ] **Step 7: コミット**

```bash
git add screener/report.py main.py tests/test_report.py
git commit -m "feat(ui): 表示ヘッダに単位を付与(header_label)"
```

---

### Task 2: HTML文字列/Workbook生成の分離（render_html・_build_workbook）

**Files:**
- Modify: `screener/report.py`
- Modify: `tests/test_report.py`

**Interfaces:**
- Produces: `report.render_html(sections, market, top=20, header_extra="") -> str`、
  `report._build_workbook(sections, market, top=20) -> openpyxl.Workbook`。
  既存 `build_html(...)->Path` / `build_excel(...)->Path` は契約不変（内部でこれらを利用）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_report.py` に追記:
```python
def test_render_html_returns_string(sections, market):
    out = report.render_html(sections, market, header_extra="<p>DL_LINK</p>")
    assert isinstance(out, str)
    assert out.startswith("<!doctype html>")
    assert "DENSO CORP" in out
    assert "DL_LINK" in out


def test_build_workbook_returns_wb(sections, market):
    wb = report._build_workbook(sections, market)
    assert "バリュー" in wb.sheetnames and "市況" in wb.sheetnames
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_report.py -k "render_html or build_workbook" -v`
Expected: FAIL（`AttributeError: ... 'render_html'`）

- [ ] **Step 3: render_html を追加し build_html をそれ経由に**

`screener/report.py` の `build_html` 関数全体（`def build_html...return path` まで）を次に置換:
```python
def render_html(sections, market, top=20, header_extra=""):
    """レポートHTMLを文字列で返す。header_extra は H1 直下に挿入。"""
    p = [_HTML_HEAD, "<h1>株スクリーニングレポート</h1>"]
    if header_extra:
        p.append(header_extra)

    # 市況
    p.append("<section><h2>市場センチメント（Fear &amp; Greed）</h2>")
    if market.get("score") is not None:
        vix = market.get("VIX")
        vix_txt = f"（VIX {html.escape(str(vix))}）" if vix is not None else ""
        p.append(f"<div class='gauge'>{_svg_gauge(market['score'])}"
                 f"<p class='label'>{html.escape(str(market.get('label','')))}"
                 f"{vix_txt}</p></div>")
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
    return "\n".join(p)


def build_html(sections, market, path, top=20):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(sections, market, top), encoding="utf-8")
    return path
```

- [ ] **Step 4: _build_workbook を抽出し build_excel をそれ経由に**

`screener/report.py` の `build_excel` 関数全体を次に置換:
```python
def _build_workbook(sections, market, top=20):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.chart import BarChart, Reference
    from openpyxl.utils import get_column_letter

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
            cell = ws.cell(1, ci, header_label(c))
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

    return wb


def build_excel(sections, market, path, top=20):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _build_workbook(sections, market, top).save(path)
    return path
```

- [ ] **Step 5: テストと既存全テストを確認**

Run: `.venv\Scripts\python -m pytest tests/ -q`
Expected: PASS（全件。既存 build_html/build_excel テストも不変で通る）

- [ ] **Step 6: コミット**

```bash
git add screener/report.py tests/test_report.py
git commit -m "refactor(report): HTML文字列/Workbook生成を関数分離"
```

---

### Task 3: 日本語名マップ（config.names と screen._apply_names）

**Files:**
- Modify: `config.yaml`
- Modify: `screener/screen.py`
- Modify: `tests/test_screen.py`

**Interfaces:**
- Produces: `screen._apply_names(rows, names: dict) -> None`（rowsを破壊的に更新）。
  各 `compute_*` が末尾で `_apply_names(rows, cfg.get("names", {}))` を呼ぶ。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_screen.py` に追記:
```python
def test_apply_names_overwrites_known_ticker():
    rows = [{"ticker": "7203.T", "name": "TOYOTA", "score": 1},
            {"ticker": "X.T", "name": "orig", "score": 1}]
    screen._apply_names(rows, {"7203.T": "トヨタ自動車"})
    assert rows[0]["name"] == "トヨタ自動車"
    assert rows[1]["name"] == "orig"   # マップに無ければ維持
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_screen.py -k "apply_names" -v`
Expected: FAIL（`AttributeError: ... '_apply_names'`）

- [ ] **Step 3: screen に _apply_names を追加し compute_* で呼ぶ**

`screener/screen.py` の `fetch_universe` 関数の直後に追記:
```python
def _apply_names(rows, names):
    """rows の name を日本語名マップで上書き（無ければ元のまま）。"""
    for r in rows:
        r["name"] = names.get(r.get("ticker"), r.get("name"))
```

`compute_value` / `compute_contrarian` / `compute_momentum` / `compute_alpha` の各
`return rows` の直前に次の1行を挿入:
```python
    _apply_names(rows, cfg.get("names", {}))
```

- [ ] **Step 4: config.yaml に names を追加**

`config.yaml` の `universe:` の直前に追記:
```yaml
# 銘柄コード→日本語名（表示用。無いコードは取得元の名前を使用）
names:
  "7203.T": "トヨタ自動車"
  "6758.T": "ソニーグループ"
  "6861.T": "キーエンス"
  "9984.T": "ソフトバンクグループ"
  "8306.T": "三菱UFJフィナンシャル・グループ"
  "9432.T": "日本電信電話(NTT)"
  "6098.T": "リクルートホールディングス"
  "4063.T": "信越化学工業"
  "8035.T": "東京エレクトロン"
  "6501.T": "日立製作所"
  "7974.T": "任天堂"
  "9433.T": "KDDI"
  "8058.T": "三菱商事"
  "8001.T": "伊藤忠商事"
  "8031.T": "三井物産"
  "6902.T": "デンソー"
  "7267.T": "本田技研工業"
  "6594.T": "ニデック"
  "4502.T": "武田薬品工業"
  "4519.T": "中外製薬"
  "6367.T": "ダイキン工業"
  "6273.T": "SMC"
  "6954.T": "ファナック"
  "6981.T": "村田製作所"
  "7741.T": "HOYA"
  "8316.T": "三井住友フィナンシャルグループ"
  "8411.T": "みずほフィナンシャルグループ"
  "8766.T": "東京海上ホールディングス"
  "9983.T": "ファーストリテイリング"
  "2914.T": "日本たばこ産業(JT)"
  "4661.T": "オリエンタルランド"
  "4568.T": "第一三共"
  "7011.T": "三菱重工業"
  "5108.T": "ブリヂストン"
  "3382.T": "セブン&アイ・ホールディングス"
  "6752.T": "パナソニックホールディングス"
  "7751.T": "キヤノン"
  "6503.T": "三菱電機"
  "4543.T": "テルモ"
  "8053.T": "住友商事"
```

- [ ] **Step 5: テストと実データ確認**

Run: `.venv\Scripts\python -m pytest tests/test_screen.py -q`
Expected: PASS

Run: `.venv\Scripts\python main.py value --top 5 --no-save`
Expected: name 列が日本語（例: デンソー / 日本電信電話(NTT) / トヨタ自動車）になる。

- [ ] **Step 6: コミット**

```bash
git add config.yaml screener/screen.py tests/test_screen.py
git commit -m "feat(ui): 銘柄名の日本語マップを追加"
```

---

### Task 4: Web レポート（/report・/report.xlsx）と導線・README

**Files:**
- Modify: `web/app.py`
- Modify: `tests/test_web.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `report.render_html`, `report._build_workbook`, `screen.compute_*`, `fear_greed.fear_greed`。
- Produces: ルート `/report`, `/report.xlsx`、ホームのレポート導線。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_web.py` に追記:
```python
def test_report_page(client, monkeypatch):
    monkeypatch.setattr(screen, "fetch_universe", lambda cfg: [])
    monkeypatch.setattr(screen, "compute_value",
                        lambda cfg, stocks: [{"ticker": "7203.T", "name": "トヨタ自動車", "score": 80.0}])
    monkeypatch.setattr(screen, "compute_contrarian", lambda cfg, stocks: [])
    monkeypatch.setattr(screen, "compute_momentum", lambda cfg, stocks: [])
    monkeypatch.setattr(fg, "fear_greed",
                        lambda i, v, ttl: {"score": 80.0, "label": "強欲", "VIX": 16.0, "内訳": {"RSI": 60}})
    html = client.get("/report").get_data(as_text=True)
    assert "トヨタ自動車" in html and "/report.xlsx" in html


def test_report_xlsx_download(client, monkeypatch):
    monkeypatch.setattr(screen, "fetch_universe", lambda cfg: [])
    monkeypatch.setattr(screen, "compute_value",
                        lambda cfg, stocks: [{"ticker": "7203.T", "name": "トヨタ自動車", "score": 80.0}])
    monkeypatch.setattr(screen, "compute_contrarian", lambda cfg, stocks: [])
    monkeypatch.setattr(screen, "compute_momentum", lambda cfg, stocks: [])
    monkeypatch.setattr(fg, "fear_greed",
                        lambda i, v, ttl: {"score": 80.0, "label": "強欲", "VIX": 16.0, "内訳": {"RSI": 60}})
    resp = client.get("/report.xlsx")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    assert resp.data[:2] == b"PK"   # xlsx(zip) シグネチャ
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_web.py -k "report" -v`
Expected: FAIL（404 で assert 失敗）

- [ ] **Step 3: web/app.py に import を追加**

`web/app.py` の import 群に追記:
```python
from datetime import date
from io import BytesIO
```
`from flask import Flask, abort, request` を次に変更:
```python
from flask import Flask, abort, request, send_file
```

- [ ] **Step 4: レポート用ヘルパとルートを追加**

`web/app.py` の `stock_page` 関数の後（`if __name__` の前）に追記:
```python
def _report_sections():
    stocks = screen.fetch_universe(CFG)
    sections = {
        "value": screen.compute_value(CFG, stocks),
        "contrarian": screen.compute_contrarian(CFG, stocks),
        "momentum": screen.compute_momentum(CFG, stocks),
    }
    market = fg.fear_greed(CFG["index"], CFG["vix"], CFG.get("cache_ttl", 86400))
    return sections, market


@app.route("/report")
def report_page():
    sections, market = _report_sections()
    extra = ('<p><a href="/">← ホーム</a>　'
             '<a href="/report.xlsx">Excelダウンロード</a></p>')
    return report.render_html(sections, market, top=20, header_extra=extra)


@app.route("/report.xlsx")
def report_xlsx():
    sections, market = _report_sections()
    buf = BytesIO()
    report._build_workbook(sections, market, top=20).save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name=f"report_{date.today():%Y%m%d}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

- [ ] **Step 5: ホームにレポート導線を追加**

`web/app.py` の `home()` 内、`<p id="s" ...>実行中…</p>` の行の直後に追記（f-string内）:
```python
<p><a href="/report">レポート（全モードまとめ＋Excelダウンロード）</a></p>
```

- [ ] **Step 6: テストを確認**

Run: `.venv\Scripts\python -m pytest tests/test_web.py -q`
Expected: PASS（全件）

- [ ] **Step 7: README にWebレポートを追記**

`README.md` の「ブラウザUI: …」の段落に追記:
```markdown
ブラウザUIの「レポート」から全モードまとめ表示＋Excelダウンロードが可能。
```

- [ ] **Step 8: 全テスト + スモーク + コミット**

Run: `.venv\Scripts\python -m pytest tests/ -q`
Expected: PASS（全件）

Run: `.venv\Scripts\python -c "from web.app import app; c=app.test_client(); print(sorted(str(r) for r in app.url_map.iter_rules()))"`
Expected: `/report` と `/report.xlsx` を含む

```bash
git add web/app.py tests/test_web.py README.md
git commit -m "feat(web): レポートページとExcelダウンロードを追加"
```

---

## Self-Review

- **Spec coverage:** ①Webレポート(/report・/report.xlsx・ホーム導線)=Task4 / build_html文字列化・build_excelファイルライク=Task2(render_html・_build_workbook) / ②日本語名(config.names・_apply_names)=Task3 / ③単位(UNITS・header_label・_table_html・CLI・Excelヘッダ)=Task1+Task2 / テスト=各Task。全項目カバー。スコープ外(Google・Web編集・CSV DL)は未着手で正しい。
- **Placeholder scan:** プレースホルダなし。全ステップ実コード。
- **Type consistency:** `render_html(sections, market, top=20, header_extra="")->str`・`_build_workbook(sections, market, top=20)->Workbook` を Task2 定義、Task4 で消費（引数名一致）。`header_label(col)->str` を Task1 定義、Task2 のExcelヘッダ・_table_html で消費。`_apply_names(rows, names)` を Task3 定義・compute_* で消費。内部キー `score`/`ticker`/`name` 不変。`build_html`/`build_excel` の戻り `Path` は不変で既存 run_report と互換。
- **注意:** Task1 で `_table_html` ヘッダが単位付きになるため、既存の `test_build_html_writes_file`（"バリュー" 等の見出し確認）は見出しテキスト（h2のSECTION_META title）を見ており列ヘッダではないので影響なし。
