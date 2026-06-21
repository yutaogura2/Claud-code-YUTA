# レポート出力機能 設計（ブラッシュアップ#6）

作成日: 2026-06-21

## 目的

株スクリーニング結果を、コンソール表示に加えて **HTML** と **Excel** の
見映えするレポートとして出力する。グラフ付き・1ファイル統合・生成後に
HTMLを自動で開く。

## スコープ

- 対象: value / contrarian / momentum の3スクリーニング + market(Fear&Greed)
- 形式: HTML と Excel の両方を生成
- 構成: 各形式 1ファイルに全モードを統合
- グラフ: あり
- 生成後: HTML をブラウザで自動オープン

非対象（YAGNI）: PDF出力、メール送信、定期実行、Web配信。

## アプローチ

採用案A: HTMLは自前テンプレ + インラインSVGグラフ、Excelは openpyxl の
ネイティブ書式・グラフ。追加依存は `openpyxl` のみ。ネット不要でオフライン動作。

不採用:
- 案B (Jinja2 + matplotlib): 依存が重い。
- 案C (pandas Styler / to_excel): グラフ表現が貧弱。

## アーキテクチャ

### コマンド

```
run.ps1 report [--top N] [--no-open]
```

`report` モードで全モード+市況を一括算出し、`data/reports/` に
`report_<YYYYMMDD>.html` と `report_<YYYYMMDD>.xlsx` を生成する。

### main.py のリファクタ

算出と表示を分離する（重複排除）。

- `compute_value(cfg, stocks) -> list[dict]`
- `compute_contrarian(cfg, stocks) -> list[dict]`
- `compute_momentum(cfg, stocks) -> list[dict]`

既存の `run_value/run_contrarian/run_momentum` は `compute_*` を呼んで
表示・保存するだけにする。`report` モードは `compute_*` + `fear_greed`
の結果を集約して `report.build_html` / `report.build_excel` に渡す。

### 新規 screener/report.py

- `build_html(sections: dict, market: dict, path: Path) -> Path`
  - `sections` = `{"value": rows, "contrarian": rows, "momentum": rows}`
  - 1ファイル統合。各モードを色付きランキング表（スコア高=緑〜低=赤の
    グラデーション）+ インラインSVG横棒グラフ。
  - 市況セクションは半円ゲージ + 6指標内訳バー。
  - CSS は `<style>` 埋込、JavaScript 不要（オフラインで開ける）。
- `build_excel(sections: dict, market: dict, path: Path) -> Path`
  - シート: サマリ / バリュー / 逆張り / モメンタム / 市況。
  - ヘッダ行を装飾（太字・背景色・固定）。
  - スコア列に ColorScaleRule（カラースケール条件付き書式）。
  - バリューシートにネイティブ BarChart（上位N スコア）。
- 内部ヘルパ: `_svg_hbar(...)`, `_svg_gauge(...)`, `_score_color(score)` を
  分離し単体で理解・テスト可能にする。

### データフロー

```
fetch(universe) → compute_value/contrarian/momentum + fear_greed
  → {mode: rows} + market dict
  → report.build_html() / report.build_excel()
  → data/reports/ に保存 → webbrowser で HTML を開く
```

## エラー処理

- セクションが0件: 表の代わりに「該当なし」を表示。
- `openpyxl` 未導入: 明示的なエラーメッセージで導入方法を案内。
- 自動オープン失敗: 警告のみ（致命的にしない）。ファイルパスは必ず表示。
- 既存の data 層のリトライ・サニタイズはそのまま利用。

## テスト（実装時 TDD）

ネット非依存のモック rows / market を使う。

1. `build_html`: 生成ファイルに銘柄名・スコア・各モード見出しが含まれる。
2. `build_html`: 0件セクションで「該当なし」が出る。
3. `build_excel`: 想定シート（サマリ/バリュー/逆張り/モメンタム/市況）が存在。
4. `build_excel`: スコア列・ヘッダが書き込まれている。
5. `_score_color` / SVGヘルパ: 入力に対し妥当な出力（境界値）。

## 依存追加

`requirements.txt` に `openpyxl>=3.1` を追加。

## 影響範囲

- 変更: `main.py`（compute抽出 + report モード）, `requirements.txt`,
  `README.md`（使い方追記）, `.gitignore`（`data/reports/` は既存 `data/` で対象済）。
- 新規: `screener/report.py`, テスト。
