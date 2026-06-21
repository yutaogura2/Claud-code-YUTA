# 株 購入銘柄選定 — 日本株スクリーニングツール

Qiita @okikusan-public の連載（Vol.1〜3）のスクリーニングロジックを
yfinance ベースで実装した日本株向けツール。

- Vol.1: バリュースコア（PER/PBR/配当/ROE/売上成長 = 100点）
- Vol.3: 逆張り（売られすぎ）・モメンタム・市場 Fear&Greed
- Vol.2: 結果の蓄積（CSV履歴・前回比）

> 投資は自己責任。本ツールの出力は投資助言ではない。

## セットアップ（初回のみ・実施済み）

```powershell
winget install Python.Python.3.12     # 導入済み
python -m venv .venv                   # 作成済み
.venv\Scripts\python -m pip install -r requirements.txt
```

## 使い方

`run.ps1` が venv と文字コードを自動設定する。

```powershell
.\run.ps1 value         # バリュー（割安株）
.\run.ps1 contrarian    # 逆張り（売られすぎ）
.\run.ps1 momentum      # モメンタム（強い銘柄）
.\run.ps1 market        # 市場 Fear & Greed
.\run.ps1 all           # 3スクリーニング + 市況をまとめて
.\run.ps1 report        # HTML+Excelレポートを生成しHTMLを自動で開く
```

オプション: `--top N`（表示件数）, `--no-save`（CSV保存しない）, `--no-open`（reportでHTMLを開かない）, `--config 別設定.yaml`

## 設定

`config.yaml` を編集する。

- `universe`: 監視銘柄（`証券コード.T`）。自分のリストに置換可
- `value_weights` / `value_bounds`: バリュースコアの配分と閾値
- `contrarian` / `momentum`: 各判定の閾値
- `min_score`: バリューの表示下限

## 出力

- コンソールに上位ランキング表示
- `data/history/<mode>_<日付>.csv` に保存（gitignore対象）
- 同モードを別日に再実行すると `前回比` 列でスコア変化を表示
- `report`: `data/reports/report_<日付>.html`（色付き表+SVGグラフ）と `.xlsx`（書式・カラースケール・棒グラフ）を生成

## 構成

```
main.py              CLI エントリ
config.yaml          設定（銘柄・閾値・スコア配分）
screener/
  data.py            yfinance取得（24hキャッシュ・リトライ・サニタイズ）
  indicators.py      RSI/SMA/ボリンジャー/MACD/ROC/出来高比
  value.py           バリュースコア（Vol.1）
  contrarian.py      逆張り（Vol.3）
  momentum.py        モメンタム（Vol.3）
  fear_greed.py      市場センチメント6指標（Vol.3）
  store.py           結果蓄積・前回比（Vol.2軽量版）
  report.py          HTML/Excelレポート生成（色付き表・SVGグラフ）
tests/               レポート生成のテスト（pytest）
```

## 注記・制約

- データ源は yfinance（無料・非公式）。配当利回り等に異常値が混じることがあり、
  一部はサニタイズ済み。重要判断は証券会社の正式データで再確認すること。
- Fear&Greed の VIX は日本版が無いため米 VIX を代理利用。
- Neo4j / ベクトル検索 / Grok API（Vol.2-3の重い機能）は未実装。
