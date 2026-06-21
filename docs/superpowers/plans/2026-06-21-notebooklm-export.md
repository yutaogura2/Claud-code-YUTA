# NotebookLM エクスポート Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** スキャン(レポート)時点の収集情報を NotebookLM 用 Markdown で出力し、年初来騰落率(出遅れ度)と任意のニュースURLを含める。

**Architecture:** `indicators.ytd_return` で年初来騰落率を算出、`data.fetch_news` でニュース取得(任意)、`screen.collect_extras` で銘柄ごとの追加情報を集約、`screener/notebooklm.py` が Markdown を生成。Web `/report.md` と CLI `report` から出力。

**Tech Stack:** Python, Flask, yfinance, pandas, pytest。追加依存なし。

## Global Constraints

- 追加依存なし。Python実行は venv 経由: `.venv\Scripts\python`（PowerShell、プロジェクトルートから）。
- 数値はツールで算出してから渡す（NotebookLMは計算が苦手）。出力形式は Markdown。
- ニュース収集は既定オフ（明示時のみ）。取得失敗は `[]`（致命的にしない）。
- 内部dictキー（ticker/score 等）は不変。表示ヘッダの単位は `report.header_label` を流用。
- テストはネット非依存（monkeypatch / モック / キャッシュ事前書き込み）。

---

### Task 1: 年初来騰落率（indicators.ytd_return）

**Files:**
- Modify: `screener/indicators.py`
- Create: `tests/test_indicators.py`

**Interfaces:**
- Produces: `indicators.ytd_return(close: pd.Series) -> float`（当年最初の終値比の騰落率%、空系列は nan）。

- [ ] **Step 1: 失敗するテストを書く**

Create `tests/test_indicators.py`:
```python
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
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_indicators.py -v`
Expected: FAIL（`AttributeError: ... 'ytd_return'`）

- [ ] **Step 3: 実装**

`screener/indicators.py` の末尾に追記:
```python
def ytd_return(close: pd.Series) -> float:
    """当年最初の終値に対する直近終値の騰落率(%)。空系列は nan。"""
    if close is None or len(close) == 0:
        return float("nan")
    year = close.index[-1].year
    ytd = close[close.index.year == year]
    base = ytd.iloc[0]
    if not base or base != base:
        return float("nan")
    return float((close.iloc[-1] / base - 1) * 100)
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_indicators.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/indicators.py tests/test_indicators.py
git commit -m "feat(notebooklm): 年初来騰落率 ytd_return を追加"
```

---

### Task 2: ニュース取得と追加情報集約（data.fetch_news・screen.collect_extras）

**Files:**
- Modify: `screener/data.py`
- Modify: `screener/screen.py`
- Modify: `tests/test_data.py`
- Modify: `tests/test_screen.py`

**Interfaces:**
- Consumes: 既存 `_read_cache`/`_write_cache`、`indicators.ytd_return`、`StockData`。
- Produces: `data.fetch_news(ticker, limit=3, ttl=86400) -> list[tuple[str, str]]`、
  `screen.collect_extras(stocks, with_news=False) -> dict[str, dict]`（`{"年初来%": float|None, "news": list}`）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_data.py` に追記:
```python
def test_fetch_news_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    dataio._write_cache("9999.T_news", {"news": [["タイトルA", "https://example.com/a"]]})
    out = dataio.fetch_news("9999.T")
    assert out == [("タイトルA", "https://example.com/a")]
```

`tests/test_screen.py` に追記:
```python
def test_collect_extras_computes_ytd(monkeypatch):
    import numpy as np
    import pandas as pd
    from screener.data import StockData
    idx = pd.date_range("2026-01-02", periods=20, freq="B")
    hist = pd.DataFrame({"Close": np.linspace(100, 110, 20), "Volume": [1] * 20}, index=idx)
    s = StockData("7203.T", {"shortName": "x"}, hist)
    extras = screen.collect_extras([s], with_news=False)
    assert extras["7203.T"]["年初来%"] == 10.0
    assert extras["7203.T"]["news"] == []
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_data.py tests/test_screen.py -k "news or extras" -v`
Expected: FAIL（`AttributeError: ... 'fetch_news'` / `'collect_extras'`）

- [ ] **Step 3: data.fetch_news を実装**

`screener/data.py` の末尾に追記:
```python
def fetch_news(ticker: str, limit: int = 3, ttl: int = 86400) -> list[tuple[str, str]]:
    """yfinance のニュースから (タイトル, URL) を最大 limit 件。失敗は []（24hキャッシュ）。"""
    key = ticker + "_news"
    cached = _read_cache(key, ttl)
    if cached is not None:
        return [tuple(x) for x in cached.get("news", [])]
    out: list[tuple[str, str]] = []
    try:
        for it in (yf.Ticker(ticker).news or [])[:limit]:
            content = it.get("content") or {}
            title = it.get("title") or content.get("title")
            link = it.get("link")
            if not link:
                link = ((content.get("canonicalUrl") or {}).get("url")
                        or (content.get("clickThroughUrl") or {}).get("url"))
            if title and link:
                out.append((title, link))
    except Exception:  # noqa: BLE001
        out = []
    _write_cache(key, {"news": out})
    return out
```

- [ ] **Step 4: screen.collect_extras を実装**

`screener/screen.py` の import 群に追記:
```python
from . import indicators as ind
```
`_apply_names` 関数の後に追記:
```python
def collect_extras(stocks, with_news=False):
    """銘柄ごとの追加情報 {ticker: {"年初来%", "news"}} を返す。"""
    out = {}
    for s in stocks:
        ytd = ind.ytd_return(s.history["Close"]) if s.ok else float("nan")
        out[s.ticker] = {
            "年初来%": round(ytd, 1) if ytd == ytd else None,
            "news": dataio.fetch_news(s.ticker) if with_news else [],
        }
    return out
```

- [ ] **Step 5: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_data.py tests/test_screen.py -v`
Expected: PASS（全件）

- [ ] **Step 6: コミット**

```bash
git add screener/data.py screener/screen.py tests/test_data.py tests/test_screen.py
git commit -m "feat(notebooklm): ニュース取得と追加情報集約(collect_extras)を追加"
```

---

### Task 3: Markdown 生成（screener/notebooklm.py）

**Files:**
- Create: `screener/notebooklm.py`
- Create: `tests/test_notebooklm.py`

**Interfaces:**
- Consumes: `report.SECTION_META`、`report.header_label`。
- Produces: `notebooklm.build_markdown(sections, market, extras=None, top=20) -> str`。

- [ ] **Step 1: 失敗するテストを書く**

Create `tests/test_notebooklm.py`:
```python
from screener import notebooklm


def test_build_markdown_has_sections_and_ytd(sections, market):
    extras = {"6902.T": {"年初来%": 12.3, "news": []},
              "7203.T": {"年初来%": -4.5, "news": []}}
    md = notebooklm.build_markdown(sections, market, extras)
    assert md.startswith("# 株スクリーニング スナップショット")
    assert "## 市況" in md
    assert "DENSO CORP" in md
    assert "年初来%" in md and "12.3" in md
    assert "| ticker |" in md
    assert "該当なし" in md            # momentum は空


def test_build_markdown_includes_news(sections, market):
    extras = {"6902.T": {"年初来%": 1.0,
                         "news": [("好決算", "https://example.com/n1")]},
              "7203.T": {"年初来%": 1.0, "news": []}}
    md = notebooklm.build_markdown(sections, market, extras)
    assert "## ニュース" in md
    assert "[好決算](https://example.com/n1)" in md
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_notebooklm.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'screener.notebooklm'`）

- [ ] **Step 3: 実装**

Create `screener/notebooklm.py`:
```python
"""NotebookLM 投入用 Markdown 生成。

スキャン時点の収集情報（指標・年初来騰落率・任意のニュース）を、NotebookLM が
取り込みやすい Markdown 文書にまとめる。数値は本ツールで算出済みを前提とする。
"""
from __future__ import annotations

from datetime import date

from . import report


def _cell(v):
    if isinstance(v, list):
        return " / ".join(v)
    return "" if v is None else str(v)


def _md_table(rows, top, extras):
    if not rows:
        return "該当なし\n"
    rows = rows[:top]
    cols = list(rows[0].keys())
    show_ytd = extras is not None
    headers = [report.header_label(c) for c in cols] + (["年初来%"] if show_ytd else [])
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        vals = [_cell(r.get(c)).replace("|", "/") for c in cols]
        if show_ytd:
            y = (extras.get(r.get("ticker")) or {}).get("年初来%")
            vals.append("" if y is None else str(y))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def build_markdown(sections, market, extras=None, top=20):
    out = [f"# 株スクリーニング スナップショット（{date.today():%Y-%m-%d}）", "",
           "> 投資は自己責任。本資料は情報整理であり投資助言ではありません。", ""]

    out.append("## 市況（Fear & Greed）")
    if market.get("score") is not None:
        out.append(f"- スコア: {market['score']} / 100（{market.get('label', '')}）")
        if market.get("VIX") is not None:
            out.append(f"- VIX: {market['VIX']}")
    else:
        out.append("- 取得失敗")
    out.append("")

    for key, (title, _mv, _sheet) in report.SECTION_META.items():
        out.append(f"## {title}")
        out.append(_md_table(sections.get(key, []), top, extras))

    if extras:
        seen, blocks = set(), []
        for key, (_t, _mv, _s) in report.SECTION_META.items():
            for r in sections.get(key, [])[:top]:
                t = r.get("ticker")
                news = (extras.get(t) or {}).get("news") or []
                if news and t not in seen:
                    seen.add(t)
                    blocks.append((t, r.get("name"), news))
        if blocks:
            out.append("## ニュース")
            for t, name, news in blocks:
                out.append(f"### {t} {name or ''}".rstrip())
                for title_, url in news:
                    out.append(f"- [{title_}]({url})")
            out.append("")

    return "\n".join(out)
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_notebooklm.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/notebooklm.py tests/test_notebooklm.py
git commit -m "feat(notebooklm): NotebookLM用Markdown生成を追加"
```

---

### Task 4: 出力の配線（Web /report.md・CLI report .md・README）

**Files:**
- Modify: `web/app.py`
- Modify: `main.py`
- Modify: `tests/test_web.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `notebooklm.build_markdown`, `screen.collect_extras`, `screen.compute_*`, `fear_greed.fear_greed`。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_web.py` に追記:
```python
def test_report_md_download(client, monkeypatch):
    monkeypatch.setattr(screen, "fetch_universe", lambda cfg: [])
    monkeypatch.setattr(screen, "compute_value",
                        lambda cfg, stocks: [{"ticker": "7203.T", "name": "トヨタ自動車", "score": 80.0}])
    monkeypatch.setattr(screen, "compute_contrarian", lambda cfg, stocks: [])
    monkeypatch.setattr(screen, "compute_momentum", lambda cfg, stocks: [])
    monkeypatch.setattr(screen, "collect_extras", lambda stocks, with_news=False: {})
    monkeypatch.setattr(fg, "fear_greed",
                        lambda i, v, ttl: {"score": 80.0, "label": "強欲", "VIX": 16.0, "内訳": {"RSI": 60}})
    resp = client.get("/report.md")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    assert "text/markdown" in resp.headers.get("Content-Type", "")
    assert "トヨタ自動車" in resp.get_data(as_text=True)
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_web.py -k "report_md" -v`
Expected: FAIL（404）

- [ ] **Step 3: web/app.py に import とルートを追加**

`web/app.py` の import 群（`from screener import screen` 付近）に追記:
```python
from screener import notebooklm  # noqa: E402
```

`report_xlsx` 関数の後に追記:
```python
@app.route("/report.md")
def report_md():
    stocks = screen.fetch_universe(CFG)
    sections = {
        "value": screen.compute_value(CFG, stocks),
        "contrarian": screen.compute_contrarian(CFG, stocks),
        "momentum": screen.compute_momentum(CFG, stocks),
    }
    market = fg.fear_greed(CFG["index"], CFG["vix"], CFG.get("cache_ttl", 86400))
    extras = screen.collect_extras(stocks, with_news=False)
    md = notebooklm.build_markdown(sections, market, extras, top=20)
    buf = BytesIO(md.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name=f"report_{date.today():%Y%m%d}.md",
        mimetype="text/markdown; charset=utf-8",
    )
```

- [ ] **Step 4: /report ページにMarkdownリンクをExcelの隣に追加**

`web/app.py` の `report_page` 内の `extra` を次に置換:
```python
    extra = ('<p><a href="/">← ホーム</a>　'
             '<a href="/report.xlsx">Excelダウンロード</a>　'
             '<a href="/report.md">NotebookLM用Markdown</a></p>')
```

- [ ] **Step 5: テスト確認**

Run: `.venv\Scripts\python -m pytest tests/test_web.py -q`
Expected: PASS（全件）

- [ ] **Step 6: CLI report で .md も生成（--news 対応）**

`main.py` の import 群に追記:
```python
from screener import notebooklm
```

`main.py` の `run_report` を次に置換:
```python
def run_report(cfg, stocks, top, open_after, news=False):
    sections = {
        "value": screen.compute_value(cfg, stocks),
        "contrarian": screen.compute_contrarian(cfg, stocks),
        "momentum": screen.compute_momentum(cfg, stocks),
    }
    market = fg.fear_greed(cfg["index"], cfg["vix"], cfg.get("cache_ttl", 86400))

    rdir = ROOT / "data" / "reports"
    stamp = f"{date.today():%Y%m%d}"
    html_path = report_mod.build_html(sections, market, rdir / f"report_{stamp}.html", top)
    xlsx_path = report_mod.build_excel(sections, market, rdir / f"report_{stamp}.xlsx", top)
    extras = screen.collect_extras(stocks, with_news=news)
    md_path = rdir / f"report_{stamp}.md"
    md_path.write_text(notebooklm.build_markdown(sections, market, extras, top), encoding="utf-8")
    print(f"HTML : {html_path.relative_to(ROOT)}")
    print(f"Excel: {xlsx_path.relative_to(ROOT)}")
    print(f"MD   : {md_path.relative_to(ROOT)}")

    if open_after:
        try:
            webbrowser.open(html_path.as_uri())
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] 自動オープン失敗: {e}")
```

`main.py` の argparse に `--news` を追加（`--no-open` の後）:
```python
    p.add_argument("--news", action="store_true", help="reportのMarkdownにニュースを含める")
```

`main.py` の report 分岐を次に置換:
```python
    if a.mode == "report":
        run_report(cfg, stocks, a.top, open_after=not a.no_open, news=a.news)
        return
```

- [ ] **Step 7: 実データ確認**

Run: `.venv\Scripts\python main.py report --top 5 --no-open`
Expected: `HTML : ...` `Excel: ...` `MD   : data\reports\report_<日付>.md` が表示され、
`.md` が生成される（中に日本語名・年初来%列）。

- [ ] **Step 8: README 追記・全テスト・コミット**

`README.md` の「ブラウザUI: …レポート…」段落に追記:
```markdown
レポートは NotebookLM 用 Markdown（年初来騰落率＝出遅れ度付き）でも出力可能
（Web「NotebookLM用Markdown」／CLI `report` の `.md`）。
```

Run: `.venv\Scripts\python -m pytest tests/ -q`
Expected: PASS（全件）

```bash
git add web/app.py main.py tests/test_web.py README.md
git commit -m "feat(notebooklm): Web/CLIからMarkdown出力を配線"
```

---

## Self-Review

- **Spec coverage:** ①年初来騰落率=Task1 / ②collect_extras・fetch_news=Task2 / ③build_markdown=Task3 / ④Web `/report.md`・CLI `.md`・`--news`・README=Task4。ニュース既定オフ（Web は with_news=False、CLI は `--news` 時のみ）。全項目カバー。スコープ外（自動アップロード等）は未着手で正しい。
- **Placeholder scan:** プレースホルダなし。全ステップ実コード/実コマンド。
- **Type consistency:** `ytd_return(close)->float`(Task1) を `collect_extras`(Task2) が使用。`collect_extras(stocks, with_news=False)->dict`、`fetch_news(ticker, limit, ttl)->list[tuple]`(Task2) を Task4 が消費。`build_markdown(sections, market, extras=None, top=20)->str`(Task3) を Task4 が消費。`report.SECTION_META`/`report.header_label` 既存を流用。`run_report` に `news` 引数追加・呼び出し側も更新（Task4 整合）。
- **注意:** `collect_extras` は `screener/data.py` を `dataio` として参照する（screen.py 既存 import 名 `from . import data as dataio` を利用）。`indicators` も `from . import indicators as ind` を追加。
