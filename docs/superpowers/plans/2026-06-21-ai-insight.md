# AI考察（ネット論調）付加 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 各銘柄にネット論調の要約（Gemini API・出典付き・参考）を、レポートMarkdownとWeb銘柄詳細へ付加する。

**Architecture:** `screener/ai_insight.py` が Gemini REST（google_search grounding）を呼び要約＋出典を返す（環境変数キー・24hキャッシュ・既定オフ）。`notebooklm` の Markdown と Web `/stock`・`/report.md` から明示時のみ呼ぶ。

**Tech Stack:** Python, requests, Flask, Gemini API, pytest。

## Global Constraints

- Python実行は venv 経由: `.venv\Scripts\python`（PowerShell、プロジェクトルートから）。
- APIキーは環境変数 `GEMINI_API_KEY` のみ（リポジトリ・configに書かない）。未設定・失敗は機能オフ（None、致命的にしない）。
- 既定オフ＋上位N限定＋オンデマンド＋24hキャッシュでコスト/レートを抑制。
- 各考察に「ネット論調の要約（参考・出典付き）。投資助言ではありません」を明記。
- 追加依存は `requests>=2` のみ。テストはネット非依存（monkeypatch）。

---

### Task 1: ai_insight.fetch_insight（Gemini呼び出し）

**Files:**
- Create: `screener/ai_insight.py`
- Modify: `requirements.txt`
- Create: `tests/test_ai_insight.py`

**Interfaces:**
- Consumes: `data._read_cache`/`data._write_cache`（既存）。
- Produces: `ai_insight._post(url, payload, timeout=30) -> dict`、
  `ai_insight.fetch_insight(ticker, name, model="gemini-2.5-flash", ttl=86400) -> dict | None`
  （`{"summary": str, "sources": [(title, url), ...]}` or None）。

- [ ] **Step 1: requirements に requests を明示追加**

`requirements.txt` に追記:
```
requests>=2
```
（yfinance 経由で導入済のはず。未導入なら `.venv\Scripts\python -m pip install "requests>=2"`）

- [ ] **Step 2: 失敗するテストを書く**

Create `tests/test_ai_insight.py`:
```python
from screener import ai_insight
from screener import data as dataio


def test_fetch_insight_parses(monkeypatch, tmp_path):
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(ai_insight, "_post", lambda url, payload, timeout=30: {
        "candidates": [{
            "content": {"parts": [{"text": "強気の声が多い"}]},
            "groundingMetadata": {"groundingChunks": [
                {"web": {"uri": "https://e.com/a", "title": "記事A"}}]},
        }]})
    out = ai_insight.fetch_insight("7203.T", "トヨタ自動車")
    assert out["summary"] == "強気の声が多い"
    assert out["sources"] == [("記事A", "https://e.com/a")]


def test_fetch_insight_no_key_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ai_insight.fetch_insight("7203.T", "トヨタ") is None
```

- [ ] **Step 3: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_ai_insight.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'screener.ai_insight'`）

- [ ] **Step 4: 実装**

Create `screener/ai_insight.py`:
```python
"""銘柄ごとのネット論調要約（Gemini API・google_search grounding）。

要約と出典を返す参考情報。APIキーは環境変数 GEMINI_API_KEY のみ。
未設定・失敗時は None（機能オフ）。結果は24hキャッシュ。
"""
from __future__ import annotations

import os

import requests

from .data import _read_cache, _write_cache

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _post(url, payload, timeout=30):
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_insight(ticker, name, model="gemini-2.5-flash", ttl=86400):
    cache_key = ticker + "_insight"
    cached = _read_cache(cache_key, ttl)
    if cached is not None:
        ins = cached.get("insight")
        if not ins:
            return None
        return {"summary": ins["summary"], "sources": [tuple(s) for s in ins["sources"]]}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    prompt = (f"日本株「{name}（{ticker}）」について、ネット上の論調・強気/弱気の"
              "見方・主なリスクを日本語で200字程度に要約してください。"
              "投資助言ではなく、事実と意見の整理として記述してください。")
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "tools": [{"google_search": {}}]}
    url = _ENDPOINT.format(model=model) + f"?key={api_key}"
    try:
        data = _post(url, payload)
        cand = (data.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        summary = "".join(p.get("text", "") for p in parts).strip()
        chunks = (cand.get("groundingMetadata") or {}).get("groundingChunks") or []
        sources = []
        for ch in chunks:
            web = ch.get("web") or {}
            uri = web.get("uri")
            if uri:
                sources.append((web.get("title") or uri, uri))
            if len(sources) >= 5:
                break
        if not summary:
            return None
        _write_cache(cache_key, {"insight": {"summary": summary, "sources": sources}})
        return {"summary": summary, "sources": sources}
    except Exception:  # noqa: BLE001
        return None
```

- [ ] **Step 5: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_ai_insight.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: コミット**

```bash
git add screener/ai_insight.py requirements.txt tests/test_ai_insight.py
git commit -m "feat(insight): Gemini APIによる銘柄ネット論調要約を追加"
```

---

### Task 2: Markdown に AI考察節（notebooklm.build_markdown）

**Files:**
- Modify: `screener/notebooklm.py`
- Modify: `tests/test_notebooklm.py`

**Interfaces:**
- Consumes: `ai_insight.fetch_insight` の戻り形 `{"summary", "sources"}`。
- Produces: `build_markdown(sections, market, extras=None, top=20, insights=None) -> str`
  （`insights`: `{ticker: {"summary", "sources"}}`）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_notebooklm.py` に追記:
```python
def test_build_markdown_includes_insights(sections, market):
    insights = {"6902.T": {"summary": "強気の声が多い",
                           "sources": [("記事A", "https://e.com/a")]}}
    md = notebooklm.build_markdown(sections, market, insights=insights)
    assert "## AI考察" in md
    assert "強気の声が多い" in md
    assert "[記事A](https://e.com/a)" in md
    assert "投資助言ではありません" in md
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_notebooklm.py -k "insights" -v`
Expected: FAIL（`TypeError: build_markdown() got an unexpected keyword argument 'insights'`）

- [ ] **Step 3: 実装**

`screener/notebooklm.py` の `build_markdown` を次に置換（シグネチャに `insights=None` を追加し、ニュース節の後に AI考察節を追加）:
```python
def build_markdown(sections, market, extras=None, top=20, insights=None):
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

    if insights:
        names = {}
        for key, (_t, _mv, _s) in report.SECTION_META.items():
            for r in sections.get(key, [])[:top]:
                names.setdefault(r.get("ticker"), r.get("name"))
        out.append("## AI考察")
        out.append("> ネット論調の要約（参考・出典付き）。投資助言ではありません。")
        out.append("")
        for t, ins in insights.items():
            if not ins:
                continue
            out.append(f"### {t} {names.get(t) or ''}".rstrip())
            out.append(ins.get("summary", ""))
            for title_, url in ins.get("sources", []):
                out.append(f"- [{title_}]({url})")
            out.append("")

    return "\n".join(out)
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_notebooklm.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/notebooklm.py tests/test_notebooklm.py
git commit -m "feat(insight): MarkdownにAI考察節を追加"
```

---

### Task 3: Web 連携（/stock?insight・/report.md?insight・config）

**Files:**
- Modify: `config.yaml`
- Modify: `web/app.py`
- Modify: `tests/test_web.py`

**Interfaces:**
- Consumes: `ai_insight.fetch_insight`、`notebooklm.build_markdown(..., insights=...)`、`CFG["ai_insight"]`。

- [ ] **Step 1: config.yaml に ai_insight を追記**

`config.yaml` の `alpha_pullback:` ブロックの直後（`# 結果の最低スコア` の前）に追記:
```yaml
# AI考察（ネット論調要約・Gemini）。キーは環境変数 GEMINI_API_KEY
ai_insight:
  provider: gemini
  model: "gemini-2.5-flash"
  top_n: 10
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_web.py` に追記:
```python
def test_stock_insight_on_demand(client, monkeypatch):
    import numpy as np
    import pandas as pd
    from screener import ai_insight
    from screener import data as dataio
    from screener.data import StockData
    idx = pd.date_range("2026-01-02", periods=30, freq="B")
    hist = pd.DataFrame({"Close": np.linspace(100, 120, 30), "Volume": [1] * 30}, index=idx)
    info = {"shortName": "TOYOTA", "trailingPE": 10.0, "priceToBook": 1.0,
            "dividendYield": 3.0, "returnOnEquity": 0.1, "revenueGrowth": 0.08}
    monkeypatch.setattr(dataio, "fetch", lambda t, ttl=86400: StockData("7203.T", info, hist))
    monkeypatch.setattr(dataio, "fetch_financials", lambda t, ttl=86400: None)
    monkeypatch.setattr(ai_insight, "fetch_insight",
                        lambda ticker, name, model="gemini-2.5-flash": {
                            "summary": "強気の声が多い", "sources": [("記事A", "https://e.com/a")]})
    # insight=1 で考察表示
    html = client.get("/stock/7203.T?insight=1").get_data(as_text=True)
    assert "AI考察" in html and "強気の声が多い" in html and "https://e.com/a" in html
    # 既定は取得リンクのみ
    html2 = client.get("/stock/7203.T").get_data(as_text=True)
    assert "AI考察を取得" in html2 and "強気の声が多い" not in html2


def test_report_md_insight(client, monkeypatch):
    from screener import ai_insight
    monkeypatch.setattr(screen, "fetch_universe", lambda cfg: [])
    monkeypatch.setattr(screen, "compute_value",
                        lambda cfg, stocks: [{"ticker": "7203.T", "name": "トヨタ自動車", "score": 80.0}])
    monkeypatch.setattr(screen, "compute_contrarian", lambda cfg, stocks: [])
    monkeypatch.setattr(screen, "compute_momentum", lambda cfg, stocks: [])
    monkeypatch.setattr(screen, "collect_extras", lambda stocks, with_news=False: {})
    monkeypatch.setattr(fg, "fear_greed",
                        lambda i, v, ttl: {"score": 80.0, "label": "強欲", "VIX": 16.0, "内訳": {"RSI": 60}})
    monkeypatch.setattr(ai_insight, "fetch_insight",
                        lambda ticker, name, model="gemini-2.5-flash": {
                            "summary": "強気の声が多い", "sources": []})
    md = client.get("/report.md?insight=1").get_data(as_text=True)
    assert "## AI考察" in md and "強気の声が多い" in md
```

- [ ] **Step 3: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_web.py -k "insight" -v`
Expected: FAIL（`AI考察を取得` 等が無く assert 失敗）

- [ ] **Step 4: web/app.py に import を追加**

`web/app.py` の import 群に追記:
```python
from screener import ai_insight  # noqa: E402
```

- [ ] **Step 5: /stock に insight 対応を追加**

`web/app.py` の `stock_page` 内、`body = (...)` を組み立てる直前（`c_html = ...` ブロックの後）に追記:
```python
    disp = CFG.get("names", {}).get(ticker) or sd.info.get("shortName") or ticker
    if request.args.get("insight") == "1":
        model = CFG.get("ai_insight", {}).get("model", "gemini-2.5-flash")
        ins = ai_insight.fetch_insight(ticker, disp, model=model)
        if ins:
            srcs = "".join(
                f'<li><a href="{html.escape(u)}">{html.escape(t_)}</a></li>'
                for t_, u in ins.get("sources", []))
            insight_html = (f"<p>{html.escape(ins['summary'])}</p>"
                            f"<ul>{srcs}</ul>"
                            "<p class='empty'>※ネット論調の要約（参考）。投資助言ではありません。</p>")
        else:
            insight_html = "<p class='empty'>AI考察を取得できませんでした（APIキー未設定の可能性）。</p>"
    else:
        insight_html = f'<p><a href="/stock/{safe_ticker}?insight=1">AI考察を取得</a></p>'
```

`web/app.py` の `stock_page` の `body = (...)` を次に置換（AI考察セクションを追加）:
```python
    body = (f"{_nav()}<h1>{name} <small>{safe_ticker}</small></h1>"
            f"<section><h2>株価</h2>{chart}</section>"
            f"<section><h2>バリュー内訳</h2>{report._table_html(v_rows, 10, 100)}</section>"
            f"<section><h2>変化スコア内訳</h2>{c_html}</section>"
            f"<section><h2>AI考察</h2>{insight_html}</section>")
    return _page(body)
```

- [ ] **Step 6: /report.md に insight 対応・/report にリンク追加**

`web/app.py` の `report_md` 関数を次に置換:
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
    insights = None
    if request.args.get("insight") == "1":
        ai_cfg = CFG.get("ai_insight", {})
        model = ai_cfg.get("model", "gemini-2.5-flash")
        top_n = ai_cfg.get("top_n", 10)
        names = CFG.get("names", {})
        insights = {}
        for r in sections["value"][:top_n]:
            t = r["ticker"]
            ins = ai_insight.fetch_insight(t, names.get(t) or r.get("name") or t, model=model)
            if ins:
                insights[t] = ins
    md = notebooklm.build_markdown(sections, market, extras, top=20, insights=insights)
    buf = BytesIO(md.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name=f"report_{date.today():%Y%m%d}.md",
        mimetype="text/markdown; charset=utf-8",
    )
```

`web/app.py` の `report_page` の `extra` に AI考察リンクを追記:
```python
    extra = ('<p><a href="/">← ホーム</a>　'
             '<a href="/report.xlsx">Excelダウンロード</a>　'
             '<a href="/report.md">NotebookLM用Markdown</a>　'
             '<a href="/report.md?insight=1">AI考察つきMarkdown</a></p>')
```

- [ ] **Step 7: テスト確認**

Run: `.venv\Scripts\python -m pytest tests/test_web.py -q`
Expected: PASS（全件）

- [ ] **Step 8: コミット**

```bash
git add config.yaml web/app.py tests/test_web.py
git commit -m "feat(insight): Web(/stock・/report.md)にAI考察を配線"
```

---

### Task 4: CLI 連携（report --insight）・手順書・README

**Files:**
- Modify: `main.py`
- Create: `docs/AI_INSIGHT.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `ai_insight.fetch_insight`、`notebooklm.build_markdown(..., insights=...)`、`cfg["ai_insight"]`。

- [ ] **Step 1: main.py に import を追加**

`main.py` の import 群に追記:
```python
from screener import ai_insight
```

- [ ] **Step 2: run_report に insight を追加**

`main.py` の `run_report` を次に置換:
```python
def run_report(cfg, stocks, top, open_after, news=False, insight=False):
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
    insights = None
    if insight:
        ai_cfg = cfg.get("ai_insight", {})
        model = ai_cfg.get("model", "gemini-2.5-flash")
        names = cfg.get("names", {})
        insights = {}
        for r in sections["value"][:ai_cfg.get("top_n", 10)]:
            t = r["ticker"]
            ins = ai_insight.fetch_insight(t, names.get(t) or r.get("name") or t, model=model)
            if ins:
                insights[t] = ins
    md_path = rdir / f"report_{stamp}.md"
    md_path.write_text(
        notebooklm.build_markdown(sections, market, extras, top, insights=insights),
        encoding="utf-8")
    print(f"HTML : {html_path.relative_to(ROOT)}")
    print(f"Excel: {xlsx_path.relative_to(ROOT)}")
    print(f"MD   : {md_path.relative_to(ROOT)}")

    if open_after:
        try:
            webbrowser.open(html_path.as_uri())
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] 自動オープン失敗: {e}")
```

- [ ] **Step 3: argparse に --insight、分岐に受け渡し**

`main.py` の argparse に追記（`--news` の後）:
```python
    p.add_argument("--insight", action="store_true", help="reportのMarkdownにAI考察を含める")
```

`main.py` の report 分岐を次に置換:
```python
    if a.mode == "report":
        run_report(cfg, stocks, a.top, open_after=not a.no_open, news=a.news, insight=a.insight)
        return
```

- [ ] **Step 4: 動作確認（キー未設定でも動く＝考察なし）**

Run: `.venv\Scripts\python main.py report --top 3 --no-open --insight`
Expected: `HTML/Excel/MD` が出力される（`GEMINI_API_KEY` 未設定なら AI考察は付かないが正常終了）。

- [ ] **Step 5: docs/AI_INSIGHT.md を作成**

Create `docs/AI_INSIGHT.md`:
```markdown
# AI考察（ネット論調）の設定

各銘柄に「ネット上の論調の要約（出典付き・参考）」を付ける機能。Gemini API を使用。

## キー取得・設定

1. Google AI Studio (https://aistudio.google.com/) で API キーを発行（無料枠あり）。
2. ローカル（PowerShell・一時的）:
   ```powershell
   $env:GEMINI_API_KEY = "取得したキー"
   .\run.ps1 report --insight
   ```
   常設するなら Windows のユーザー環境変数に `GEMINI_API_KEY` を登録。
3. 公開（Render）: サービスの Environment に `GEMINI_API_KEY` を追加。

## 使い方

- CLI: `.\run.ps1 report --insight` … 上位N銘柄の考察を `.md` に付加。
- Web: レポートの「AI考察つきMarkdown」、銘柄詳細の「AI考察を取得」。

## 注意

- 既定はオフ（明示時のみ呼び出し）。上位N（config `ai_insight.top_n`）と24hキャッシュでコスト抑制。
- 出力はネット論調の要約（参考・出典付き）であり、投資助言ではありません。
- キーは環境変数のみ。リポジトリ・config には保存しないこと。
```

- [ ] **Step 6: README に追記・全テスト・コミット**

`README.md` の NotebookLM の段落の後に追記:
```markdown
各銘柄のネット論調を Gemini API で要約する「AI考察」も付加可能
（要 `GEMINI_API_KEY`、既定オフ。詳細は [docs/AI_INSIGHT.md](docs/AI_INSIGHT.md)）。
```

Run: `.venv\Scripts\python -m pytest tests/ -q`
Expected: PASS（全件）

```bash
git add main.py docs/AI_INSIGHT.md README.md
git commit -m "feat(insight): CLI report --insight と手順書を追加"
```

---

## Self-Review

- **Spec coverage:** Gemini呼び出し・キー環境変数・24hキャッシュ=Task1 / Markdown AI考察節=Task2 / Web /stock?insight・/report.md?insight・/reportリンク・config=Task3 / CLI report --insight・docs・README=Task4。既定オフ・上位N・オンデマンドのコスト制御＝Task3/4。全項目カバー。スコープ外（全銘柄自動・他プロバイダ）は未着手で正しい。
- **Placeholder scan:** プレースホルダなし。全ステップ実コード/実コマンド。
- **Type consistency:** `fetch_insight(ticker, name, model=..., ttl=...)->{"summary","sources"}|None`(Task1) を Task2(insights節)・Task3(web)・Task4(cli) が消費。`build_markdown(..., insights=None)`(Task2) を Task3/4 が `insights=` で呼ぶ。`CFG["ai_insight"].{model,top_n}`(Task3 config) を web/cli が参照。web の monkeypatch 対象 `ai_insight.fetch_insight`/`screen.*`/`fg.fear_greed` は属性呼び出しで差し替え可能。
- **注意:** `ai_insight` は `data._read_cache/_write_cache` を再利用（同一パッケージ内・既存パターン）。テストは `data.CACHE_DIR` を monkeypatch して隔離。
