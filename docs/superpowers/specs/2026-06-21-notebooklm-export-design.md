# NotebookLM 連携用エクスポート 設計

作成日: 2026-06-21

## 目的

スキャン（レポート生成）をトリガーに、その時点で収集した情報を **NotebookLM
で活用しやすい Markdown** として出力する。あわせて「年初来騰落率＝出遅れ度」を
追加し、任意でニュース見出し・URLも収集する。

> 投資は自己責任。本ツールの出力は投資助言ではない。

## 背景・方針

- NotebookLM は投入資料のみを根拠に出典付きで要約・横断する用途が得意。
- CSV/Excelの直アップロードは不安定なため、**Markdown** で渡すのが確実。
- 数値計算は NotebookLM が苦手 → 騰落率・出遅れ度・指標は**本ツールで算出**して
  表として渡す（役割分担）。

## スコープ

- 年初来騰落率（出遅れ度）の算出を追加
- スキャン時点の情報を NotebookLM 用 Markdown で出力（Web ダウンロード＋CLI）
- 任意でニュース見出し・URL を収集して Markdown に付記
- 公開サイトの速度配慮: ニュース収集は既定オフ（明示時のみ）

非対象（YAGNI）: NotebookLMへの自動アップロード（公式APIなし）、CSV直対応、Google連携。

## アーキテクチャ

### ① 年初来騰落率（indicators.ytd_return）

`screener/indicators.py` に追加:
- `ytd_return(close) -> float`：当年1月1日以降の最初の終値に対する直近終値の
  騰落率(%)。当年データが無ければ `nan`。
- 「出遅れ度」はこの値の小ささで判断（負・低いほど出遅れ）。

### ② 追加情報の収集（screen.collect_extras）

`screener/screen.py` に追加:
- `collect_extras(stocks, with_news=False) -> dict`：
  `{ticker: {"年初来%": float|None, "news": [(title, url), ...]}}`
  - 年初来% は `stocks` の history から `ytd_return` で算出。
  - news は `with_news=True` のとき `data.fetch_news(ticker)` を best-effort 呼び出し。
- `data.fetch_news(ticker, limit=3) -> list[(title, url)]`：yfinance の news から
  上位 limit 件を抽出。失敗・空は `[]`（例外は握りつぶす）。キャッシュ24h。

### ③ Markdown 生成（screener/notebooklm.py）

`build_markdown(sections, market, extras=None, top=20) -> str`：
- 見出し（`# 株スクリーニング スナップショット（<日付>）`）＋免責1行。
- 市況: Fear&Greed スコア・判定・VIX を箇条書き。
- 各モード（value/contrarian/momentum）: Markdown表（日本語名・score・主要指標、
  extras があれば **年初来%** 列を付加）。`header_label` の単位表記を流用。
- ニュース節（extras に news があるとき）: 銘柄ごとに `- [タイトル](URL)`。
- 文字列を返す（ファイル書き込みは呼び出し側）。

### ④ 出力の配線

- **Web**:
  - `GET /report.md`：`_report_sections()` ＋ `collect_extras(stocks, with_news=False)`
    → `notebooklm.build_markdown` → `text/markdown` で添付ダウンロード。
  - `/report` ページに「NotebookLM用Markdownダウンロード」リンク追加。
  - 公開サイト速度配慮でニュースは既定オフ。
- **CLI**:
  - `report` モードで `data/reports/report_<日付>.md` も生成（html/xlsx に加えて）。
  - `--news` 指定時のみ news を収集して md に含める。

## データフロー

```
スキャン(report) → fetch_universe → compute_* + fear_greed
  → collect_extras(stocks, with_news) （年初来%・任意でnews）
  → notebooklm.build_markdown → .md 出力 / ダウンロード
  → ユーザが NotebookLM に投入し、IR資料と合わせて出典付きまとめを生成
```

## エラー処理

- 当年データ不足の年初来% は `None`（表は空欄）。
- news 取得失敗は `[]`（致命的にしない）。
- セクション0件は「該当なし」。

## テスト（実装時 TDD・ネット非依存）

1. `indicators.ytd_return`: 当年始から上昇する系列で正の値、当年データ無しで nan。
2. `notebooklm.build_markdown`: Markdown文字列に日本語名・`## 市況`等の見出し・
   `| ticker |` 表・extras の年初来%列を含む。空セクションで「該当なし」。
3. `notebooklm.build_markdown`: extras に news があると `- [タイトル](URL)` を含む。
4. `screen.collect_extras`: mock stocks で年初来% を算出、with_news=False で news 空。
5. `GET /report.md`: 200・`Content-Disposition: attachment`・`text/markdown`・本文に銘柄名。

## 依存・影響範囲

- 追加依存なし。
- 新規: `screener/notebooklm.py`, `tests/test_notebooklm.py`。
- 変更: `screener/indicators.py`（ytd_return）, `screener/screen.py`（collect_extras）,
  `screener/data.py`（fetch_news）, `web/app.py`（/report.md・リンク）,
  `main.py`（report モードで .md 生成・--news）, `README.md`。
