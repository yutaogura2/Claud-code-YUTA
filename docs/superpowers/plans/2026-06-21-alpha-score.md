# アルファスコア機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 財務諸表から業績変化スコア(4指標)を算出し、割安スコアと合算した2軸で銘柄をランキングする `alpha` コマンドを追加する。

**Architecture:** `data.fetch_financials` で年次財務6系列を取得・キャッシュ。`screener/alpha.py` が変化スコアと(既存)バリュースコアを合算し押し目フラグを付与。`main.py` の `alpha` モードが各銘柄に適用してランキング表示・CSV保存する。

**Tech Stack:** Python 3.12, yfinance(財務諸表), pandas, pytest。追加依存なし。

## Global Constraints

- 追加ランタイム依存なし（yfinance/pandas で財務取得可）。
- Python 実行は venv 経由: `.venv\Scripts\python`（PowerShell、プロジェクトルートから）。
- テストはネット非依存（モックの fin / StockData を使う）。
- 年次財務の系列は newest→oldest（添字0=直近期）。
- 指標の必要期数が不足/分母0/NaN の指標は 0 点。有効指標ゼロなら銘柄除外。
- ランキング列は他モードと統一して `score`（=combined）を使う（既存 store/前回比/表示を流用）。
- コメント・UI文言は日本語。

---

### Task 1: data.fetch_financials（財務取得・キャッシュ）

**Files:**
- Modify: `screener/data.py`
- Create: `tests/test_data.py`

**Interfaces:**
- Consumes: 既存 `_read_cache(key, ttl)`, `_write_cache(key, payload)`, `_cache_path`。
- Produces: `screener.data._row(df, name) -> list`（newest→oldest, float|None）、`screener.data.fetch_financials(ticker: str, ttl: int=86400) -> dict | None`。戻りは `{"revenue":[...], "net_income":[...], "ocf":[...], "fcf":[...], "total_assets":[...], "equity":[...]}` or None。

- [ ] **Step 1: 失敗するテストを書く**

Create `tests/test_data.py`:
```python
import json
import pandas as pd
from screener import data as dataio


def test_row_parses_newest_first_and_nan():
    df = pd.DataFrame(
        {pd.Timestamp("2026-03-31"): [100.0],
         pd.Timestamp("2025-03-31"): [float("nan")]},
        index=["Total Revenue"],
    )
    assert dataio._row(df, "Total Revenue") == [100.0, None]


def test_row_missing_label_returns_empty():
    df = pd.DataFrame({pd.Timestamp("2026-03-31"): [1.0]}, index=["X"])
    assert dataio._row(df, "Total Revenue") == []


def test_fetch_financials_uses_cache(tmp_path, monkeypatch):
    # キャッシュを事前に書けば fetch_financials はネット無しで返す
    fin = {"revenue": [110.0, 100.0], "net_income": [10.0, 8.0],
           "ocf": [12.0, 11.0], "fcf": [20.0, 15.0],
           "total_assets": [200.0, 190.0], "equity": [100.0, 100.0]}
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    dataio._write_cache("9999.T_fin", {"fin": fin})
    assert dataio.fetch_financials("9999.T", ttl=86400) == fin
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_data.py -v`
Expected: FAIL（`AttributeError: module 'screener.data' has no attribute '_row'`）

- [ ] **Step 3: 最小実装**

`screener/data.py` の末尾（`fetch` 関数の後）に追記:
```python
def _row(df, name):
    """財務DataFrameの1行を newest→oldest の list[float|None] で返す。無い行は []。"""
    try:
        s = df.loc[name]
    except (KeyError, AttributeError, TypeError):
        return []
    out = []
    for v in s.tolist():
        try:
            f = float(v)
            out.append(None if f != f else f)  # NaN→None
        except (TypeError, ValueError):
            out.append(None)
    return out


def fetch_financials(ticker: str, ttl: int = 86400) -> dict | None:
    """年次財務6系列を newest→oldest で取得（24hキャッシュ）。取得不能は None。"""
    key = ticker + "_fin"
    cached = _read_cache(key, ttl)
    if cached is not None:
        return cached.get("fin")

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            t = yf.Ticker(ticker)
            inc, bal, cf = t.income_stmt, t.balance_sheet, t.cashflow
            fin = {
                "revenue": _row(inc, "Total Revenue"),
                "net_income": _row(inc, "Net Income"),
                "ocf": _row(cf, "Operating Cash Flow"),
                "fcf": _row(cf, "Free Cash Flow"),
                "total_assets": _row(bal, "Total Assets"),
                "equity": _row(bal, "Stockholders Equity"),
            }
            if all(len(v) == 0 for v in fin.values()):
                raise ValueError("no financials")
            _write_cache(key, {"fin": fin})
            return fin
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"  [warn] {ticker} 財務取得失敗: {last_err}")
    return None
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_data.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/data.py tests/test_data.py
git commit -m "feat(alpha): 財務諸表の取得とキャッシュを追加"
```

---

### Task 2: alpha.change_score（変化スコア4指標）

**Files:**
- Create: `screener/alpha.py`
- Create: `tests/test_alpha.py`

**Interfaces:**
- Produces: `screener.alpha._lerp(x, full, zero, weight) -> float`、`screener.alpha._safe(a, b) -> float|None`、`screener.alpha.change_score(fin: dict, weights: dict, bounds: dict) -> dict | None`。戻りキー: `change`(float), `アクルーアルズ`, `売上加速%`, `FCFマージンΔ%`, `ROEΔ%`（無効指標は None）。有効指標ゼロなら None。

- [ ] **Step 1: 失敗するテストを書く**

Create `tests/test_alpha.py`:
```python
from screener import alpha

WEIGHTS = {"accruals": 25, "sales_accel": 25, "fcf_margin": 25, "roe_trend": 25}
BOUNDS = {
    "accruals":    {"full": -0.05, "zero": 0.10},
    "sales_accel": {"full": 0.05,  "zero": -0.05},
    "fcf_margin":  {"full": 0.03,  "zero": -0.03},
    "roe_trend":   {"full": 0.03,  "zero": -0.03},
}
FIN_GOOD = {
    "revenue":      [121.0, 110.0, 100.0],
    "net_income":   [10.0, 8.0, 7.0],
    "ocf":          [12.0, 11.0, 10.0],
    "fcf":          [20.0, 15.0, 12.0],
    "total_assets": [200.0, 190.0, 180.0],
    "equity":       [100.0, 100.0, 95.0],
}


def test_lerp_bounds():
    assert alpha._lerp(8, 8, 25, 25) == 25
    assert alpha._lerp(25, 8, 25, 25) == 0
    assert alpha._lerp(16.5, 8, 25, 25) == 12.5


def test_change_score_submetrics():
    c = alpha.change_score(FIN_GOOD, WEIGHTS, BOUNDS)
    assert c["アクルーアルズ"] == -0.01      # (10-12)/200
    assert c["売上加速%"] == 0.0             # g0=0.10, g1=0.10
    assert c["FCFマージンΔ%"] == 2.9         # 0.1653-0.1364
    assert c["ROEΔ%"] == 2.0                 # 0.10-0.08
    assert 70 <= c["change"] <= 80           # 約76


def test_change_score_short_series_drops_accel():
    fin = {k: v[:2] for k, v in FIN_GOOD.items()}  # 2期のみ
    c = alpha.change_score(fin, WEIGHTS, BOUNDS)
    assert c is not None
    assert c["売上加速%"] is None            # 3期必要→無効
    assert c["ROEΔ%"] is not None


def test_change_score_all_missing_returns_none():
    fin = {k: [] for k in FIN_GOOD}
    assert alpha.change_score(fin, WEIGHTS, BOUNDS) is None
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_alpha.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'screener.alpha'`）

- [ ] **Step 3: 最小実装**

Create `screener/alpha.py`:
```python
"""アルファスコア（Vol.1 AlphaScreener）。

財務諸表から業績変化スコア(4指標)を算出し、バリュースコア(割安)と
合算した2軸で銘柄を評価する。
"""
from __future__ import annotations

from . import indicators as ind
from .data import StockData
from .value import value_score


def _lerp(x, full, zero, weight):
    """x を [zero→0点, full→満点] に線形変換。full<zero でも逆向き対応。"""
    if x is None or full == zero:
        return 0.0
    frac = max(0.0, min(1.0, (x - zero) / (full - zero)))
    return frac * weight


def _safe(a, b):
    """a/b。引数欠損や分母0は None。"""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _get(seq, i):
    return seq[i] if seq is not None and len(seq) > i else None


def change_score(fin: dict, weights: dict, bounds: dict) -> dict | None:
    rev, ni = fin.get("revenue"), fin.get("net_income")
    ocf, fcf = fin.get("ocf"), fin.get("fcf")
    assets, eq = fin.get("total_assets"), fin.get("equity")

    total = 0.0
    valid = 0

    # 1. アクルーアルズ（利益の質）= (NI0 - OCF0)/Assets0。低いほど良い
    accr = None
    n0, o0, a0 = _get(ni, 0), _get(ocf, 0), _get(assets, 0)
    if n0 is not None and o0 is not None:
        accr = _safe(n0 - o0, a0)
    if accr is not None:
        b = bounds["accruals"]; total += _lerp(accr, b["full"], b["zero"], weights["accruals"]); valid += 1

    # 2. 売上加速度 = g0 - g1（3期必要）
    accel = None
    r0, r1, r2 = _get(rev, 0), _get(rev, 1), _get(rev, 2)
    g0, g1 = _safe(r0, r1), _safe(r1, r2)
    if g0 is not None and g1 is not None:
        accel = (g0 - 1) - (g1 - 1)
        b = bounds["sales_accel"]; total += _lerp(accel, b["full"], b["zero"], weights["sales_accel"]); valid += 1

    # 3. FCFマージン変化 = FCF0/Rev0 - FCF1/Rev1
    dmargin = None
    m0, m1 = _safe(_get(fcf, 0), r0), _safe(_get(fcf, 1), r1)
    if m0 is not None and m1 is not None:
        dmargin = m0 - m1
        b = bounds["fcf_margin"]; total += _lerp(dmargin, b["full"], b["zero"], weights["fcf_margin"]); valid += 1

    # 4. ROE趨勢 = NI0/Eq0 - NI1/Eq1
    droe = None
    roe0, roe1 = _safe(_get(ni, 0), _get(eq, 0)), _safe(_get(ni, 1), _get(eq, 1))
    if roe0 is not None and roe1 is not None:
        droe = roe0 - roe1
        b = bounds["roe_trend"]; total += _lerp(droe, b["full"], b["zero"], weights["roe_trend"]); valid += 1

    if valid == 0:
        return None
    return {
        "change": round(total, 1),
        "アクルーアルズ": round(accr, 3) if accr is not None else None,
        "売上加速%": round(accel * 100, 1) if accel is not None else None,
        "FCFマージンΔ%": round(dmargin * 100, 1) if dmargin is not None else None,
        "ROEΔ%": round(droe * 100, 1) if droe is not None else None,
    }
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_alpha.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/alpha.py tests/test_alpha.py
git commit -m "feat(alpha): 変化スコア4指標を追加"
```

---

### Task 3: alpha.alpha_screen（2軸合算・押し目）

**Files:**
- Modify: `screener/alpha.py`
- Modify: `tests/test_alpha.py`

**Interfaces:**
- Consumes: `change_score`、`value.value_score(sd, weights, bounds)`、`indicators.rsi/bollinger`。
- Produces: `screener.alpha.alpha_screen(sd: StockData, fin: dict, cfg: dict) -> dict | None`。戻り行キー: `ticker, name, score(=combined), value, change, 押し目, アクルーアルズ, 売上加速%, FCFマージンΔ%, ROEΔ%`。change算出不能 or info欠損なら None。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_alpha.py` に追記:
```python
import numpy as np
import pandas as pd
from screener.data import StockData

CFG = {
    "value_weights": {"per": 25, "pbr": 25, "dividend": 20, "roe": 15, "growth": 15},
    "value_bounds": {
        "per": {"full": 8, "zero": 25}, "pbr": {"full": 0.8, "zero": 3.0},
        "dividend": {"full": 4.0, "zero": 0.0}, "roe": {"full": 15.0, "zero": 0.0},
        "growth": {"full": 15.0, "zero": 0.0},
    },
    "alpha_weights": WEIGHTS, "alpha_bounds": BOUNDS,
    "alpha_pullback": {"rsi_max": 35},
}


def _stock(decline=True):
    idx = pd.date_range("2025-01-01", periods=40, freq="B")
    prices = np.linspace(100, 80, 40) if decline else np.linspace(80, 100, 40)
    hist = pd.DataFrame({"Close": prices, "Volume": [1000] * 40}, index=idx)
    info = {"shortName": "TEST", "trailingPE": 10.0, "priceToBook": 1.0,
            "dividendYield": 3.0, "returnOnEquity": 0.10, "revenueGrowth": 0.08}
    return StockData("TEST.T", info, hist)


def test_alpha_screen_combines_value_and_change():
    r = alpha.alpha_screen(_stock(), FIN_GOOD, CFG)
    assert r is not None
    assert r["score"] == round((r["value"] + r["change"]) / 2, 1)
    assert r["change"] > 0
    assert r["押し目"] in ("○", "")


def test_alpha_screen_pullback_flag_on_decline():
    r = alpha.alpha_screen(_stock(decline=True), FIN_GOOD, CFG)
    assert r["押し目"] == "○"        # 下落基調→RSI低い


def test_alpha_screen_none_when_change_missing():
    fin = {k: [] for k in FIN_GOOD}
    assert alpha.alpha_screen(_stock(), fin, CFG) is None
```

- [ ] **Step 2: 失敗を確認**

Run: `.venv\Scripts\python -m pytest tests/test_alpha.py -k "alpha_screen" -v`
Expected: FAIL（`AttributeError: ... 'alpha_screen'`）

- [ ] **Step 3: 最小実装**

`screener/alpha.py` の末尾に追記:
```python
def alpha_screen(sd: StockData, fin: dict, cfg: dict) -> dict | None:
    if not sd.info:
        return None
    c = change_score(fin, cfg["alpha_weights"], cfg["alpha_bounds"])
    if c is None:
        return None
    v = value_score(sd, cfg["value_weights"], cfg["value_bounds"])

    pullback = False
    if sd.ok:
        close = sd.history["Close"]
        price = float(close.iloc[-1])
        rsi = ind.rsi(close)
        _, _, bb_low = ind.bollinger(close)
        pullback = (rsi <= cfg["alpha_pullback"]["rsi_max"]) or (price < bb_low)

    combined = (v["score"] + c["change"]) / 2
    return {
        "ticker": sd.ticker,
        "name": sd.info.get("shortName"),
        "score": round(combined, 1),
        "value": v["score"],
        "change": c["change"],
        "押し目": "○" if pullback else "",
        "アクルーアルズ": c["アクルーアルズ"],
        "売上加速%": c["売上加速%"],
        "FCFマージンΔ%": c["FCFマージンΔ%"],
        "ROEΔ%": c["ROEΔ%"],
    }
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python -m pytest tests/test_alpha.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: コミット**

```bash
git add screener/alpha.py tests/test_alpha.py
git commit -m "feat(alpha): 割安×改善の2軸合算と押し目フラグを追加"
```

---

### Task 4: config・main 配線・README（aphaモード）

**Files:**
- Modify: `config.yaml`
- Modify: `main.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `screener.alpha.alpha_screen`、`screener.data.fetch_financials`、既存 `compute_*` パターン・`_attach_diff_and_show`。

- [ ] **Step 1: config.yaml に alpha 設定を追記**

`config.yaml` の `min_score` 行の直後に追記:
```yaml
# ── アルファ（割安×業績改善）── Vol.1 準拠
alpha_weights:
  accruals: 25       # アクルーアルズ（利益の質）
  sales_accel: 25    # 売上加速度
  fcf_margin: 25     # FCFマージン変化
  roe_trend: 25      # ROE趨勢
alpha_bounds:
  accruals:    {full: -0.05, zero: 0.10}   # 低いほど良い
  sales_accel: {full: 0.05,  zero: -0.05}
  fcf_margin:  {full: 0.03,  zero: -0.03}
  roe_trend:   {full: 0.03,  zero: -0.03}
alpha_pullback:
  rsi_max: 35        # 押し目フラグ: RSI<=35 か ボリンジャー下限割れ
```

- [ ] **Step 2: main.py に import と compute_alpha/run_alpha を追加**

`main.py` の import 群に追記（`from screener import value as val` の付近）:
```python
from screener import alpha as alp
```

`run_market` 関数の直前に追記:
```python
def compute_alpha(cfg, stocks):
    ttl = cfg.get("cache_ttl", 86400)
    rows = []
    print("財務取得中…")
    for i, s in enumerate(stocks, 1):
        print(f"  [{i}/{len(stocks)}] {s.ticker}", end="\r")
        fin = dataio.fetch_financials(s.ticker, ttl)
        if fin is None:
            continue
        r = alp.alpha_screen(s, fin, cfg)
        if r:
            rows.append(r)
    print()
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def run_alpha(cfg, stocks, top, save):
    rows = compute_alpha(cfg, stocks)
    _attach_diff_and_show("alpha", rows, top, save,
                          "■ アルファ（割安×業績改善 / combined＝(value+change)/2）")
```

- [ ] **Step 3: argparse と main 分岐に alpha を追加**

`main.py` の argparse の choices を変更:
```python
    p.add_argument("mode", choices=["value", "contrarian", "momentum",
                                    "market", "all", "report", "alpha"])
```

`main` の `stocks = _fetch_all(cfg)` の後の分岐群に追記（`report` 分岐の後）:
```python
    if a.mode == "alpha":
        run_alpha(cfg, stocks, a.top, save)
        return
```

- [ ] **Step 4: 実行確認（実データ）**

Run: `.venv\Scripts\python main.py alpha --top 10 --no-save`
Expected: 「財務取得中…」の後に「■ アルファ（…）」の表が表示され、
`ticker name score value change 押し目 アクルーアルズ 売上加速% FCFマージンΔ% ROEΔ%` 列が出る。

- [ ] **Step 5: README にコマンドを追記**

`README.md` の使い方コマンド一覧に追記（`report` 行の前）:
```
.\run.ps1 alpha         # 割安×業績改善の2軸（アルファ）
```
「## 出力」に追記:
```
- `alpha`: combined=(value+change)/2 で降順。data/history/alpha_<日付>.csv に保存
```
「## 構成」の screener 一覧に追記:
```
  alpha.py           変化スコア4指標＋2軸合算（Vol.1 AlphaScreener）
```

- [ ] **Step 6: 全テスト + コミット**

```bash
.venv\Scripts\python -m pytest tests/ -v
git add config.yaml main.py README.md
git commit -m "feat(alpha): alphaコマンドを追加し2軸スクリーニングを配線"
```

---

## Self-Review

- **Spec coverage:** 4指標(Task2) / value×change合算(Task3) / 両軸表示(行に value,change,score) / 押し目フラグ(Task3) / 財務取得・キャッシュ(Task1) / config化(Task4) / CSV保存・前回比(score列で既存 _attach_diff_and_show 流用) / 系列不足→0点・有効ゼロ→除外(Task2) / テスト(各Task TDD)。全項目カバー。スコープ外(report統合/四半期)は未着手で正しい。
- **Placeholder scan:** プレースホルダなし。全ステップに実コード。
- **Type consistency:** `change_score(fin, weights, bounds)->dict|None`、`alpha_screen(sd, fin, cfg)->dict|None`、`fetch_financials(ticker, ttl)->dict|None` を定義(Task1-3)・消費(Task3-4)で一致。fin の6キー(revenue/net_income/ocf/fcf/total_assets/equity)は Task1 生成・Task2 消費で一致。ランキング列 `score` を Task3 生成・Task4(_attach_diff_and_show/store)消費で一致。
- **注意点:** ランキング列は設計の「combined」を `score` キーで実装（既存の前回比/保存/表示機構をそのまま流用するため）。値の意味は (value+change)/2 で設計と同一。
