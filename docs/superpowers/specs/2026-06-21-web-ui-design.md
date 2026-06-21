# Web UI 機能 設計

作成日: 2026-06-21

## 目的

既存 CLI スクリーナーをブラウザから操作できるようにする。モードを選んで実行し、
結果を色付き表＋グラフで表示し、銘柄をクリックして個別詳細（チャート・財務）を見る。

> 投資は自己責任。本ツールの出力は投資助言ではない。

## スコープ

- 起動: `run.ps1 web` で Flask を 127.0.0.1:5000 に起動しブラウザを開く
- 操作: モード(value/contrarian/momentum/alpha/market)選択 → top件数指定 → 実行 → 結果表示
- 個別銘柄詳細: 株価チャート＋主要指標＋財務6系列＋value/change内訳
- 描画は既存 `screener/report.py` の関数を流用
- 技術: 軽量 Flask（追加依存は flask のみ）

非対象（YAGNI）: 銘柄/閾値のブラウザ編集（config.yaml を直接編集）、HTML/Excelレポート生成ボタン、認証、非同期ジョブ。

## アプローチ

採用案A: Flask アプリ。`main.py` の算出ロジックを `screener/screen.py` に切り出し、
CLI と Web で共用する。描画は `report.py` の `_table_html` / `_svg_hbar` /
`_svg_gauge` / `_score_color` / `SECTION_META` を再利用。

不採用:
- 案B（main.py を import）: main は argparse を持ち Web から使いにくい。
- 案C（Streamlit）: 依存が重い。

## アーキテクチャ

### リファクタ（土台）: screener/screen.py 新設

`main.py` から以下を移動し、CLI と Web の共通サービス層にする。

- `fetch_universe(cfg) -> list[StockData]`（現 `_fetch_all` 相当。進捗 print は残す）
- `compute_value(cfg, stocks) -> list[dict]`
- `compute_contrarian(cfg, stocks) -> list[dict]`
- `compute_momentum(cfg, stocks) -> list[dict]`
- `compute_alpha(cfg, stocks) -> list[dict]`

`main.py` はこれらを import して表示・保存・CLI 引数処理に専念する（外部挙動は不変）。

### 新規 web/app.py（Flask）

ルート:

- `GET /` — ホーム。モード選択 `<select>`、top件数 `<input>`、実行ボタンの
  フォーム。送信時に簡易スピナーを出す最小 JS。
- `GET /screen?mode=<m>&top=<n>` — 指定モードを算出して結果を表示。
  - screener系: `screen.compute_*` → `report._table_html` の表 ＋ `report._svg_hbar`。
    銘柄コード列は `/stock/<ticker>` へのリンク。
  - `market`: `fear_greed.fear_greed` → `report._svg_gauge` ＋6指標バー。
- `GET /stock/<ticker>` — 個別詳細。
  - `data.fetch` の info/history、`data.fetch_financials` の6系列を表示。
  - 株価ラインチャート（新規 `report._svg_line`）。
  - 主要指標（PER/PBR/配当/ROE/時価総額/52週高安）と、value・change の内訳。

ホームと各ページは共通の最小レイアウト（`report._HTML_HEAD` のスタイルを流用）。
universe・cfg は起動時に1回 `yaml.safe_load` して app に保持。

### report.py への追加

- `_svg_line(series, width=640, height=180) -> str` — 終値の折れ線 SVG。
  既存 `_score_color` 等と同じく標準ライブラリのみ。

### 起動スクリプト

- `web/app.py` に `if __name__ == "__main__":` を置き、`webbrowser.open(...)` の後
  `app.run(host="127.0.0.1", port=5000)` する。
- `run.ps1 web` は `.venv\Scripts\python web\app.py` を実行する（他の run.ps1 と同様に
  venv・UTF-8 を設定）。

## データフロー

```
ブラウザ → Flaskルート
  → screen.fetch_universe (24hキャッシュ) → compute_* / fear_greed / fetch_financials
  → report の描画関数で HTML 生成 → 返却
```

yfinance は24hキャッシュ済のため2回目以降は高速。

## エラー処理

- 取得失敗銘柄はスキップ（既存 data 層の挙動）。
- 該当0件は「該当なし」表示。
- 個別詳細で財務が無い場合は「財務データなし」。
- 未知の mode / 不正な top は 400、想定外例外は簡潔な 500 ページ。

## テスト（実装時 TDD）

ネット非依存。Flask の test client と monkeypatch を使う。

1. `screen.compute_value` 等: モック `StockData` 一覧で rows を返す（既存ロジックの移設確認）。
2. `report._svg_line`: 系列を渡すと `<svg>...</svg>` を返し、空系列で ""。
3. `GET /`: 200 で各モードの選択肢を含む。
4. `GET /screen`: `compute_*` を monkeypatch し、200 で銘柄名・スコアを含む。
5. `GET /screen?mode=market`: `fear_greed` を monkeypatch し、ゲージとラベルを含む。
6. `GET /stock/<t>`: `fetch`/`fetch_financials` を monkeypatch し、指標・財務見出しを含む。
7. 不正 mode: 400。

## 依存・影響範囲

- 追加依存: `flask>=3.0`（requirements.txt）。
- 新規: `web/app.py`, `web/__init__.py`, `screener/screen.py`, `tests/test_screen.py`, `tests/test_web.py`。
- 変更: `main.py`（compute_* を screen.py から import）, `report.py`（`_svg_line` 追加）,
  `run.ps1`（web 分岐）, `README.md`（web コマンド追記）, `requirements.txt`。

## 将来の公開（スコープ外メモ）

- 本番 WSGI サーバ（waitress 等）、認証、レート制限、長時間処理の非同期ジョブ化。
- v1 は localhost 同期実行（単一ユーザ前提）。
