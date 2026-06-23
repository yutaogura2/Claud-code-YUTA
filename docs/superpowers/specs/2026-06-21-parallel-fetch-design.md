# 並列取得の高速化 設計

作成日: 2026-06-21

## 目的

yfinance からの銘柄取得を並列化し、スクリーニング全体（value/contrarian/momentum/
alpha/report/web）の待ち時間を短縮する。

## スコープ

- `screen.fetch_universe`（info+価格）の並列化
- `screen.compute_alpha` の財務取得（`fetch_financials`）の並列化
- 並列数は config 化（既定 `max_workers=8`）
- 戻り値の型・並び順は不変（互換維持）

非対象（YAGNI）: async化、プロセス並列、動的レート制御。

## アプローチ

`concurrent.futures.ThreadPoolExecutor` を使う（yfinance は I/O バウンドのため
スレッドで十分有効）。Yahoo のレート制限を避けるため並列数は控えめ（既定8）。

## アーキテクチャ

### screen.fetch_universe（並列化）

```
tickers = cfg["universe"]
workers = cfg.get("fetch", {}).get("max_workers", 8)
ThreadPoolExecutor(max_workers=workers) で各 ticker を dataio.fetch(t, ttl) 実行
→ 結果を「元のuniverse順」に並べて返す（順序保証）
```
- 進捗表示は「取得中… N銘柄（並列）」→ 完了後「完了 N件」に簡素化
  （並列下では逐次カウンタ（`\r`）が乱れるため）。

### screen.compute_alpha（財務取得を並列化）

```
workers で各 s.ticker の dataio.fetch_financials(ticker, ttl) を並列取得し
{ticker: fin} を作る → 元の stocks 順に alpha_screen(s, fin, cfg) を適用
→ rows を combined 降順ソート → _apply_names
```
- `fin` が None の銘柄はスキップ（既存挙動）。`alpha_screen` 自体は取得後に逐次実行
  （pandas 計算は CPU 寄りで並列化の利得が薄く、順序・可読性を優先）。

### 設定（config.yaml）

```yaml
fetch:
  max_workers: 8   # 並列取得数（Yahooのレート制限回避のため過大にしない）
```

## スレッド安全性

- キャッシュは銘柄ごとに別ファイル（`data/cache/<ticker>.json` 等）で書き込み衝突なし。
- 例外・リトライ・None返却は既存 `fetch`/`fetch_financials` の挙動を踏襲（1銘柄の失敗が
  他に波及しない）。

## エラー処理

- 個別銘柄の取得失敗は従来どおり（空 StockData / fin=None）。全体は継続。

## 互換性

- `fetch_universe(cfg) -> list[StockData]`、`compute_alpha(cfg, stocks) -> list[dict]`
  の戻り値の型・並びは不変。CLI・Web・レポート・既存テストへの影響なし。

## テスト（実装時 TDD・ネット非依存）

1. `fetch_universe`: `dataio.fetch` をモック（ticker→StockData）。返却が **universe順**で
   全件揃うこと（並列でも順序保証）。`cfg["fetch"]["max_workers"]` 未指定でも既定動作。
2. `compute_alpha`: `dataio.fetch_financials`（ticker→fin）と `alpha.alpha_screen` を
   モックし、全銘柄処理・combined降順・名称上書きが保たれること。

## 依存・影響範囲

- 追加依存なし（標準ライブラリ `concurrent.futures`）。
- 変更: `screener/screen.py`（fetch_universe・compute_alpha 並列化）, `config.yaml`（fetch）,
  `README.md`（任意で並列数の記載）。
- 既存テスト（test_screen 等）は不変で通る想定。
