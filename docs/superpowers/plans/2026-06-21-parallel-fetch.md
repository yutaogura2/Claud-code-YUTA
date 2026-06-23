# 並列取得の高速化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `fetch_universe` と `compute_alpha` の yfinance 取得を ThreadPoolExecutor で並列化し、取得待ち時間を短縮する。

**Architecture:** 標準ライブラリ `concurrent.futures.ThreadPoolExecutor` で I/O バウンドな取得を並列化。`ex.map` で元の順序を保ち、戻り値の型・並びは不変。並列数は config（既定8）。

**Tech Stack:** Python 標準ライブラリ（concurrent.futures）、既存スタック、pytest。追加依存なし。

## Global Constraints

- 追加依存なし。Python実行は venv 経由: `.venv\Scripts\python`（PowerShell、プロジェクトルートから）。
- 並列数は `cfg["fetch"]["max_workers"]`（既定 8）。`fetch` 未設定でも既定で動く。
- 戻り値の型・並び順は不変（`ex.map` で順序保証）。1銘柄の失敗は他に波及しない（既存挙動）。
- テストはネット非依存（`dataio.fetch`/`fetch_financials`・`alpha.alpha_screen` を monkeypatch）。

---

### Task 1: fetch_universe の並列化（config.fetch 追加）

**Files:**
- Modify: `config.yaml`
- Modify: `screener/screen.py`
- Modify: `tests/test_screen.py`

**Interfaces:**
- Produces: `screen.fetch_universe(cfg) -> list[StockData]`（universe順を維持、`cfg["fetch"]["max_workers"]` 既定8で並列取得）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_screen.py` に追記:
```python
def test_fetch_universe_parallel_preserves_order(monkeypatch):
    from screener.data import StockData
    calls = []
    monkeypatch.setattr("screener.screen.dataio.fetch",
                        lambda t, ttl=86400: (calls.append(t), StockData(t))[1])
    cfg = {"universe": ["A.T", "B.T", "C.T"], "fetch": {"max_workers": 4}}
    out = screen.fetch_universe(cfg)
    assert [s.ticker for s in out] == ["A.T", "B.T", "C.T"]  # 並列でも順序維持
    assert sorted(calls) == ["A.T", "B.T", "C.T"]            # 全件取得
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_screen.py -k "parallel" -v`
Expected: FAIL（現行は逐次で `calls` 順は維持されるが、`max_workers` 未対応で並列化テストの意図不一致／実装変更前のため、実装後の比較用にここでは失敗を確認）。
※ 既存逐次実装でもこのテストは通る可能性があるため、確実な失敗確認として次の Step 3 まで進み、並列実装後に Step 4 で再確認する。

- [ ] **Step 3: config.yaml に fetch を追加**

`config.yaml` の `cache_ttl:` 行の直後に追記:
```yaml
# 取得の並列数（Yahooのレート制限回避のため過大にしない）
fetch:
  max_workers: 8
```

- [ ] **Step 4: screen.fetch_universe を並列化**

`screener/screen.py` の import 群に追記:
```python
from concurrent.futures import ThreadPoolExecutor
```

`screener/screen.py` の `fetch_universe` を次に置換:
```python
def fetch_universe(cfg):
    tickers = cfg["universe"]
    ttl = cfg.get("cache_ttl", 86400)
    workers = cfg.get("fetch", {}).get("max_workers", 8)
    print(f"取得中… {len(tickers)}銘柄（並列{workers}）")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        out = list(ex.map(lambda t: dataio.fetch(t, ttl=ttl), tickers))
    print(f"完了 {len(out)}件")
    return out
```

- [ ] **Step 5: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_screen.py -v`
Expected: PASS（全件。順序・全件取得を確認）

- [ ] **Step 6: コミット**

```bash
git add config.yaml screener/screen.py tests/test_screen.py
git commit -m "perf: fetch_universe を並列化(ThreadPoolExecutor)"
```

---

### Task 2: compute_alpha の財務取得を並列化

**Files:**
- Modify: `screener/screen.py`
- Modify: `tests/test_screen.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `cfg["fetch"]["max_workers"]`（Task 1）、`dataio.fetch_financials`、`alpha.alpha_screen`、`_apply_names`。
- Produces: `screen.compute_alpha(cfg, stocks) -> list[dict]`（財務取得を並列化、combined降順・名称上書きは不変）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_screen.py` に追記:
```python
def test_compute_alpha_parallel(monkeypatch):
    from screener.data import StockData
    monkeypatch.setattr("screener.screen.dataio.fetch_financials",
                        lambda t, ttl=86400: {"revenue": [1, 1, 1]})
    monkeypatch.setattr("screener.screen.alp.alpha_screen",
                        lambda s, fin, cfg: {"ticker": s.ticker, "name": s.ticker,
                                             "score": 1.0 if s.ticker == "A.T" else 2.0})
    cfg = {"fetch": {"max_workers": 4}, "names": {}, "alpha_weights": {},
           "alpha_bounds": {}, "alpha_pullback": {}}
    stocks = [StockData("A.T"), StockData("B.T")]
    rows = screen.compute_alpha(cfg, stocks)
    assert [r["ticker"] for r in rows] == ["B.T", "A.T"]   # combined降順
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_screen.py -k "compute_alpha_parallel" -v`
Expected: 現行の逐次実装でも通る可能性があるため、Step 3 実装後の Step 4 で並列版での通過を確認する（このテストは並列化後の回帰防止が目的）。

- [ ] **Step 3: compute_alpha を並列化**

`screener/screen.py` の `compute_alpha` を次に置換:
```python
def compute_alpha(cfg, stocks):
    ttl = cfg.get("cache_ttl", 86400)
    workers = cfg.get("fetch", {}).get("max_workers", 8)
    print(f"財務取得中…（並列{workers}）")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fins = list(ex.map(lambda s: dataio.fetch_financials(s.ticker, ttl), stocks))
    rows = []
    for s, fin in zip(stocks, fins):
        if fin is None:
            continue
        r = alp.alpha_screen(s, fin, cfg)
        if r:
            rows.append(r)
    rows.sort(key=lambda r: r["score"], reverse=True)
    _apply_names(rows, cfg.get("names", {}))
    return rows
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_screen.py -v`
Expected: PASS（全件）

- [ ] **Step 5: 全テストと実データ確認**

Run: `.venv\Scripts\python -m pytest tests/ -q`
Expected: PASS（全件）

Run: `.venv\Scripts\python main.py value --top 5 --no-save`
Expected: 「取得中… 40銘柄（並列8）」→「完了 40件」と表示され、従来どおりバリュー表が出る。

- [ ] **Step 6: README に並列数の記載を追記**

`README.md` の「## 設定」節の箇条書きに追記:
```markdown
- `fetch.max_workers`: 取得の並列数（既定8。Yahooのレート制限回避のため過大にしない）
```

- [ ] **Step 7: コミット**

```bash
git add screener/screen.py tests/test_screen.py README.md
git commit -m "perf: compute_alpha の財務取得を並列化"
```

---

## Self-Review

- **Spec coverage:** fetch_universe並列化=Task1 / compute_alpha財務並列化=Task2 / config.fetch.max_workers=Task1 / 順序保証(ex.map)=Task1,2 / 互換維持=戻り値不変 / テスト=各Task。全項目カバー。スコープ外(async/プロセス並列)は未着手で正しい。
- **Placeholder scan:** プレースホルダなし。全ステップ実コード/実コマンド。Step2 の「失敗確認」は逐次実装でも通り得る旨を明記し、回帰防止テストとして実装後の通過確認(Step4)で担保。
- **Type consistency:** `fetch_universe(cfg)->list[StockData]`、`compute_alpha(cfg, stocks)->list[dict]` は不変。`cfg["fetch"]["max_workers"]` を両関数が `cfg.get("fetch", {}).get("max_workers", 8)` で参照（既定一致）。`ex.map` は順序保証で `zip(stocks, fins)` 整合。`_apply_names`/`alp.alpha_screen`/`dataio.*` は既存シグネチャ。
- **注意:** テストは `screener.screen.dataio.fetch` 等を文字列パスで monkeypatch（screen が `from . import data as dataio` 済のため属性差し替え可）。
