# Web UI 改善 設計（レポート出力・日本語名・単位）

作成日: 2026-06-21

## 目的

3点を改善する。
1. Web UI からレポート（全モードまとめ＋Excelダウンロード）を出せるようにする。
2. 銘柄名を正しい日本語で表示する（現状は yfinance の英語名）。
3. 各数値に単位を付ける。

> 投資は自己責任。本ツールの出力は投資助言ではない。

## スコープ

- `GET /report`（統合HTML）と `GET /report.xlsx`（Excelダウンロード）を Web に追加、ホームに導線
- `config.yaml` に `names`（証券コード→日本語名）を追加し、全モード・CLI・Web・レポートに反映
- 表示ヘッダに単位を付与（内部キーは不変）

非対象（YAGNI）: Google連携、銘柄/閾値のWeb編集、CSVのダウンロード、英語UI。

## アーキテクチャ

### ① Web レポート出力

- `web/app.py` に2ルート追加:
  - `GET /report`: `screen.compute_value/contrarian/momentum` ＋ `fear_greed` を算出し、
    `report.build_html` で生成したHTMLをそのまま返す（ファイル保存はしない）。
    冒頭に `/report.xlsx` へのダウンロードリンクと `/`(ホーム) リンクを差し込む。
  - `GET /report.xlsx`: 同じ算出結果を `report.build_excel` で **BytesIO** に書き出し、
    `flask.send_file(..., as_attachment=True, download_name="report_<日付>.xlsx")` で返す。
    ディスクに残さない（Render無料枠の揮発FSでも問題なし）。
- ホーム（`/`）に「レポート（全モードまとめ）」リンクを追加。

`report.build_html(sections, market, path, top)` は現状 `path` 必須でファイル書き込みする。
Web では文字列が欲しいので、`build_html` を `path=None` 許容にして
**HTML文字列を返す**（path 指定時は従来どおり書き込みも行う）よう小改修する。
`build_excel` も `path` に文字列パスだけでなく BytesIO 等のファイルライクを受けられるよう、
`Workbook.save()` にそのまま渡す形にする（openpyxl は BytesIO 対応）。

### ② 日本語名

- `config.yaml` に `names:` を追加（証券コード→日本語名、全universe分）。
- `screener/screen.py` に `_apply_names(rows, names)` を追加し、各 `compute_*` の最後で
  `row["name"]` を `names.get(ticker, row["name"])` で上書き（マップに無ければ従来名）。
- これで CLI・Web・レポートすべてに日本語名が反映される（描画は `name` を参照済み）。

### ③ 単位

- `screener/report.py` に `UNITS = {"score":"点","value":"点","change":"点","PER":"倍","PBR":"倍","出来高比":"倍"}` と
  `header_label(col) -> str`（`col` に単位があれば `f"{col}（{unit}）"`、無ければ `col`）を追加。
- 表示ヘッダのみ単位付きにする:
  - `report._table_html` のヘッダ生成で `header_label(c)` を使用。
  - `web` は `_table_html` 流用のため自動反映。
  - CLI `main._print_table` のヘッダも `report.header_label` を使用。
- 既に `%` を含む列（配当% / ROE% / 売上成長% / 乖離200% / ROC% / 売上加速% / FCFマージンΔ% / ROEΔ%）は据え置き。
  RSI・アクルーアルズは無単位の指標としてそのまま。
- **内部のdictキーは変更しない**（`score`/`ticker` を使う store・前回比・web の互換維持）。

## データフロー（レポート）

```
GET /report  → compute_* + fear_greed → build_html(sections, market, path=None) → HTML返却
GET /report.xlsx → 同算出 → build_excel(sections, market, BytesIO) → send_file
```

## エラー処理

- 取得失敗銘柄はスキップ（既存）。該当0は「該当なし」。
- レポートのExcel生成失敗時は500（簡潔メッセージ）。
- 名前マップに無いコードは英語名にフォールバック（エラーにしない）。

## テスト（実装時 TDD）

ネット非依存（monkeypatch / モック）。
1. `report.header_label`: `"score"→"score（点）"`, `"PER"→"PER（倍）"`, `"配当%"→"配当%"`（不変）。
2. `report.build_html(path=None)`: HTML文字列を返し、銘柄名・見出しを含む。
3. `report.build_excel(BytesIO)`: 例外なく書き込め、読み戻すと想定シートがある。
4. `screen._apply_names`: マップ該当は上書き、非該当は元名を維持。
5. `GET /report`（compute_* と fear_greed をmonkeypatch）: 200・日本語名・ダウンロードリンクを含む。
6. `GET /report.xlsx`: 200・`Content-Disposition: attachment`・xlsxバイト列。

## 依存・影響範囲

- 追加依存なし。
- 変更: `web/app.py`（/report, /report.xlsx, ホーム導線）, `screener/report.py`
  （build_html の path=None 対応・build_excel のファイルライク対応・UNITS/header_label・_table_html ヘッダ）,
  `screener/screen.py`（_apply_names）, `config.yaml`（names）, `main.py`（_print_table ヘッダ）,
  `README.md`（Web機能追記）。
- 新規: `tests/test_labels.py`（または既存 test_report に追記）。
