# アルファスコア機能 設計（ブラッシュアップ#3）

作成日: 2026-06-21

## 目的

Vol.1 の AlphaScreener を実装する。財務諸表から「業績が良い方向に変化しているか」
を定量化する**変化スコア**を算出し、既存の**バリュースコア（割安）**と組み合わせて
「割安 × 業績改善」の2軸でスクリーニングする。

> 投資は自己責任。本ツールの出力は投資助言ではない。

## スコープ

- 新コマンド `alpha`（割安×改善の2軸スクリーニング）
- 変化スコア4指標: アクルーアルズ / 売上加速度 / FCFマージン変化 / ROE趨勢
- 2軸の出し方: value と change を両方表示し、合算（平均）で降順ランキング
- 押し目フラグ: 既存テクニカル指標を流用し「押し目」列に ○ を付与
- 結果は data/history に保存し前回比に対応（既存 store.py 流用）

非対象（YAGNI）: レポート(HTML/Excel)への alpha 追加、四半期財務対応、EquityQuery。

## アプローチ

採用案A: 年次財務（直近3〜4期）から4指標を算出。各指標を config の境界で
0〜満点（既定25点）に線形マッピングし合計100点の変化スコアにする。
combined = (value_score + change_score) / 2 でランキング。

不採用:
- 案B（四半期 TTM/YoY）: 日本株はノイズ・欠損が多い。
- 案C（info の ROE/成長率のみ）: トレンド・アクルーアルズが計算不可。

## 指標定義

yfinance の年次財務（newest→oldest）から以下を使用する。

- income_stmt: `Net Income`, `Total Revenue`
- balance_sheet: `Total Assets`, `Stockholders Equity`
- cashflow: `Operating Cash Flow`, `Free Cash Flow`

添字 0=直近期, 1=前期, 2=前々期 とする。

1. **アクルーアルズ（利益の質）** = `(NetIncome[0] − OperatingCF[0]) / TotalAssets[0]`
   低いほど良い（利益がキャッシュ裏付け）。境界 full=-0.05, zero=+0.10。
2. **売上加速度** = `g0 − g1`、`g_t = Revenue[t]/Revenue[t+1] − 1`。
   正なら成長が加速。境界 full=+0.05, zero=-0.05。3期必要。
3. **FCFマージン変化** = `(FCF[0]/Revenue[0]) − (FCF[1]/Revenue[1])`。
   境界 full=+0.03, zero=-0.03。
4. **ROE趨勢** = `(NetIncome[0]/Equity[0]) − (NetIncome[1]/Equity[1])`。
   境界 full=+0.03, zero=-0.03。

各指標スコア = clamp((x−zero)/(full−zero), 0, 1) × weight（既定25）。
変化スコア = 4指標の合計（最大100）。重み・境界は config 化。

算出に必要な期数が足りない（系列<3 または分母0/NaN）指標は 0 点として扱い、
有効指標が1つも無ければ change=None としてその銘柄を除外する。

## アーキテクチャ

### コマンド

```
run.ps1 alpha [--top N] [--no-save]
```

### 新規 screener/alpha.py

- `change_score(fin: dict, weights: dict, bounds: dict) -> dict | None`
  - `fin` = `{"revenue":[...], "net_income":[...], "ocf":[...], "fcf":[...],
    "total_assets":[...], "equity":[...]}`（newest→oldest, float, 欠損は None）
  - 戻り: `{"change": float, "アクルーアルズ": float|None, "売上加速%": ...,
    "FCFマージンΔ%": ..., "ROEΔ%": ...}`。有効指標ゼロなら None。
- `alpha_screen(sd: StockData, fin: dict, cfg: dict) -> dict | None`
  - value_score（既存 value.py）と change_score を呼び、
    `combined=(value+change)/2` を計算。押し目フラグを既存 indicators で判定。
  - 戻り行: `{ticker, name, combined, value, change, 押し目, アクルーアルズ,
    売上加速%, FCFマージンΔ%, ROEΔ%}`。change=None なら None（除外）。

### data.py 拡張

- `fetch_financials(ticker: str, ttl: int=86400) -> dict | None`
  - `yf.Ticker(ticker)` の income_stmt / balance_sheet / cashflow から
    6系列を newest→oldest で抽出して上記 `fin` 形を返す。
  - `data/cache/<ticker>_fin.json` に24hキャッシュ。リトライ・例外は既存 fetch に準拠。
  - 取得不能なら None。

### main.py

- `compute_alpha(cfg, stocks) -> list[dict]`: 各 stock について
  `fetch_financials` を呼び `alpha_screen` を適用。combined 降順。
- `run_alpha(cfg, stocks, top, save)`: `_attach_diff_and_show("alpha", ...)` で
  表示・保存（前回比は combined 基準）。
- argparse の choices に `alpha` 追加、main 分岐に追加。

### config.yaml 追記

```
alpha_weights: {accruals: 25, sales_accel: 25, fcf_margin: 25, roe_trend: 25}
alpha_bounds:
  accruals:    {full: -0.05, zero: 0.10}
  sales_accel: {full: 0.05,  zero: -0.05}
  fcf_margin:  {full: 0.03,  zero: -0.03}
  roe_trend:   {full: 0.03,  zero: -0.03}
alpha_pullback: {rsi_max: 35}   # 押し目フラグ判定
```

## データフロー

```
_fetch_all(info+history) → 各銘柄 fetch_financials
  → value_score & change_score → combined & 押し目
  → combined降順 → コンソール表示 + data/history/alpha_<日付>.csv 保存
```

## エラー処理

- 財務系列<3 or 分母0/NaN の指標は 0 点。有効指標ゼロ → 銘柄除外（change=None）。
- 財務取得失敗 → 警告のみ、その銘柄は除外。
- value 側が算出不能（info欠損）→ combined 計算不可のため除外。

## テスト（実装時 TDD）

ネット非依存のモック `fin` / StockData を使う。

1. `change_score`: 既知系列で4指標値と合計が期待通り（手計算と一致）。
2. `change_score`: 系列2期のみ → 売上加速度は0点、他は計算され change が返る。
3. `change_score`: 全系列欠損 → None。
4. `_lerp` 境界: full/zero/中間で 25 / 0 / 12.5。
5. `alpha_screen`: value と change から combined=平均、押し目フラグの有無。

## 依存・影響範囲

- 追加依存なし（yfinance/pandas で財務取得可）。
- 変更: `screener/data.py`（fetch_financials 追加）, `main.py`（compute_alpha/run_alpha/mode）,
  `config.yaml`（alpha 設定）, `README.md`（alpha コマンド追記）。
- 新規: `screener/alpha.py`, `tests/test_alpha.py`。
