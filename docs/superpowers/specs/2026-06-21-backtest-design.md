# 簡易バックテスト 設計

作成日: 2026-06-21

## 目的

価格ベースで再現できる逆張り/モメンタムのシグナルを、過去データで簡易検証する。
一定間隔でリバランスする等金額ポートフォリオの資産曲線と指標を、日経平均(買い持ち)
と比較する。CLI と Web で表示する。

## 前提・割り切り（重要・出力にも明記）

- **価格ベースのみ**: スコアは価格・出来高で計算できる指標に限定（RSI/200日乖離/
  ボリンジャー/MACD/ROC/出来高）。逆張りの低PER/低PBRは過去再現不可のため除外
  （ライブ版とは別の「価格専用スコア」）。
- **サバイバーシップ・バイアス**: universe は現構成銘柄。過去に退出/未上場の銘柄を
  含まないため結果は楽観側に歪む。
- **取引コスト・スリッページ・配当は無視**（株価リターンのみ）。
- 本機能は傾向把握用であり、実運用成績の保証ではない。

## スコープ

- 逆張り・モメンタムの2戦略を価格専用スコアでバックテスト
- 簡易ポートフォリオ（等金額・上位N・一定間隔リバランス）
- 指標: 累積リターン%・CAGR%・最大DD%・期間数・勝率%、ベンチ(日経平均)比較
- CLI `backtest` と Web `/backtest`（資産曲線SVG）

非対象（YAGNI）: value/alpha のバックテスト（財務がpoint-in-timeで再現不可）、
取引コストモデル、最適化、複数パラメータ探索。

## アーキテクチャ

### データ取得: data.fetch_history

- `fetch_history(ticker, period="3y", ttl=86400) -> pandas.DataFrame | None`
  - 長期の日次 OHLCV を取得。キャッシュキーは `<ticker>_hist_<period>`
    （既存の1年取得・スクリーニングのキャッシュとは独立）。
  - 取得失敗・空は None（best-effort）。リトライは既存 `fetch` に準拠。

### 価格専用スコア（screener/backtest.py）

- `_contrarian_score(close, vol) -> int`: 価格専用の該当条件数。
  RSI<=30 / 200日線下方乖離 / ボリンジャー下限割れ / 出来高急増（既存indicators流用）。
- `_momentum_score(close, vol) -> int`: RSI過熱 / MACD GC / ROC加速 / 出来高増 /
  200日線上方乖離。
- いずれも与えられた window（その時点までの系列）で算出。データ不足は score 0。

### シミュレーション（screener/backtest.py）

- `run_strategy(histories, score_fn, top_n, step, warmup) -> dict`
  - `histories`: `{ticker: DataFrame(Close,Volume,...)}`（共通の日次インデックス前提）。
  - 基準日列 = いずれかの十分長い系列の index（または共通部分）。`warmup` 本以降から
    `step` 本ごとにリバランス日を取る。
  - 各リバランス日 d で、`histories[t]` の d までの window から `score_fn` を算出。
    score 上位 `top_n`（同点は任意順）を等金額保有。
  - 次のリバランス日 d2 までの各銘柄リターン `close[d2]/close[d]-1` の平均を期リターンに。
  - `equity = cumprod(1+期リターン)`、`dates = リバランス日`。
  - 指標を算出: `total_return`, `cagr`, `max_drawdown`, `periods`, `win_rate`。
- `_metrics(dates, equity) -> dict`: 上記指標を計算。
- `run_backtest(histories, benchmark_close, cfg) -> dict`
  - `{"contrarian": result, "momentum": result, "benchmark": {...}}`。
  - benchmark: 日経平均の buy&hold（同期間の total_return/cagr/max_dd と equity）。

### CLI（main.py）

- `backtest` モード: universe の長期履歴＋`^N225` を取得 → `run_backtest` →
  逆張り/モメンタム/ベンチの指標を表表示。割り切り注記を出力。

### Web（web/app.py）

- `GET /backtest`: 同様に算出し、指標テーブル＋資産曲線（`report._svg_line` で
  逆張り/モメンタム/ベンチを重ねず各曲線を順に表示）＋注記。ホームに導線。

### 設定（config.yaml）

```yaml
backtest:
  period: "3y"        # 取得期間
  top_n: 5            # 各期の保有銘柄数
  rebalance_days: 21  # リバランス間隔(営業日≒1ヶ月)
  warmup_days: 200    # 指標安定までの助走(SMA200等)
```

## データフロー

```
backtest → fetch_history(universe + ^N225, period)
  → run_backtest(histories, benchmark) （価格専用スコアでリバランス試算）
  → 指標 + 資産曲線 → CLI表 / Web(テーブル+SVG)
```

## エラー処理

- 履歴不足の銘柄は各リバランス期で対象外（score 0 扱いで自然に下位）。
- 有効銘柄が0の期は期リターン0（または前期equity維持）でスキップ。
- benchmark 取得失敗時はベンチ比較を省略（注記）。

## テスト（実装時 TDD・ネット非依存）

1. `_metrics`: 既知の equity 列で total_return/max_drawdown/win_rate/cagr が手計算と一致。
2. `run_strategy`: 合成 histories（上昇1銘柄・下落1銘柄）で、score_fn をスタブして
   上位N選択・期リターン平均・equity が期待通り。warmup/step が効くこと。
3. `_contrarian_score`/`_momentum_score`: 明確な下落/上昇系列で妥当なスコア（境界）。
4. `run_backtest`: スタブ score で contrarian/momentum/benchmark の3結果が返る。

## 依存・影響範囲

- 追加依存なし。
- 新規: `screener/backtest.py`, `tests/test_backtest.py`。
- 変更: `screener/data.py`（fetch_history 追加）, `main.py`（backtest モード・load_cfg は既存）,
  `web/app.py`（/backtest・ホーム導線）, `config.yaml`（backtest）, `run.ps1` は既存の
  main 経由で動くため変更不要, `README.md`。
