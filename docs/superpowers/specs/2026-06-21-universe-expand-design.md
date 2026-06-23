# 銘柄ユニバース拡張 設計

作成日: 2026-06-21

## 目的

監視銘柄を現状40から拡張する。日経225をプリセットとして同梱し、config の
切替で利用できるようにする。プリセットには日本語名も含める。

## スコープ

- `presets/nikkei225.csv`（`コード,日本語名`）を同梱（ベストエフォート・日付明記）
- `screener/universe.py`：プリセット読込と cfg への適用
- `config.yaml` の `universe_preset` で切替（既定は null＝現状の inline 40）
- 既存の取得・スクリーニング・名称解決は変更不要（cfg["universe"]/cfg["names"] を読むだけ）

非対象（YAGNI）: 構成銘柄の自動更新、他プリセット（TOPIX等）、EquityQuery動的取得。

## 留意点（重要）

- **データ正確性**: 日経225の構成・社名は入替がある。本CSVはベストエフォート（日付付き）。
  公式情報での照合を推奨。未知/上場廃止コードは取得時に空 StockData となり自動除外される。
- **公開サイト速度**: 225銘柄はRender無料枠だと初回取得が長くレート制限の懸念。既定は40の
  ままとし、`universe_preset: nikkei225` で切替（ローカルは225、公開は40運用も可）。

## アーキテクチャ

### presets/nikkei225.csv

- 1行目: コメント（`# Nikkei225 constituents (best-effort, as of 2026-06-21)`）。
- 各行: `7203.T,トヨタ自動車`（コードに `.T` 付き、日本語名）。
- 文字コード UTF-8。

### 新規 screener/universe.py

- `load_preset(name) -> tuple[list[str], dict]`
  - `presets/<name>.csv` を読み、`#` 始まり・空行はスキップ。
  - 各行を `code,name` に分割（最初のカンマで2分割、name は前後空白除去）。
  - 戻り: `(tickers, names)`。`tickers` は出現順、`names` は `{code: name}`。
  - ファイル無しは `FileNotFoundError`（明確に失敗）。
- `apply_preset(cfg) -> None`
  - `name = cfg.get("universe_preset")` が falsy なら何もしない。
  - そうでなければ `tickers, names = load_preset(name)` を読み、
    `cfg["universe"] = tickers`、`cfg["names"] = {**names, **cfg.get("names", {})}`
    （inline の names を優先）。

### 配線（DRY）

- `main.load_cfg(path)`: `yaml.safe_load` 後に `universe.apply_preset(cfg)` を呼んで返す。
- `web/app.py`: `CFG = yaml.safe_load(...)` の直後に `universe.apply_preset(CFG)`。
- これにより `screen.fetch_universe`・`compute_*`・名称解決は無改修。

### config.yaml

```yaml
universe_preset: null   # "nikkei225" にすると presets/nikkei225.csv を使用
```

## データフロー

```
config読込 → apply_preset(cfg)
  ├ universe_preset 未設定: 既存 inline の universe/names をそのまま使用
  └ "nikkei225": presets/nikkei225.csv から universe/names を差し替え（inline名は優先）
→ 以降のスクリーニングは従来どおり
```

## エラー処理

- preset ファイル無し → `FileNotFoundError`（設定ミスを早期に知らせる）。
- CSVの不正行（カンマ無し等）→ スキップ。
- 未知/廃止コード → 取得時に空 StockData → 自動除外（既存挙動）。

## テスト（実装時 TDD・ネット非依存）

1. `load_preset`: ダミーCSV（コメント行・空行・通常行・不正行）で tickers/names が正しく、
   不正行はスキップされること。
2. `apply_preset`: `universe_preset="dummy"` で cfg["universe"]/names が差し替わり、
   inline の names が優先されること。未設定なら cfg 無変更。
3. 同梱の `presets/nikkei225.csv` が `load_preset("nikkei225")` で読め、概ね 200 件以上・
   全行 `.T` 付き・名称非空であること（データ健全性の最低限チェック）。

## 依存・影響範囲

- 追加依存なし。
- 新規: `presets/nikkei225.csv`, `screener/universe.py`, `tests/test_universe.py`。
- 変更: `main.py`（load_cfg で apply_preset）, `web/app.py`（CFG後に apply_preset）,
  `config.yaml`（universe_preset 既定 null）, `README.md`（プリセット切替の記載）。
