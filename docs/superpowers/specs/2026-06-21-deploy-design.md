# 公開デプロイ対応 設計

作成日: 2026-06-21

## 目的

Web UI（Flask）を Render に公開デプロイできるようにする。本番WSGIサーバ・
環境変数対応・Blueprint(render.yaml)・デプロイ手順書を整える。

> 投資は自己責任。本ツールの出力は投資助言ではない。

## スコープ

- ホスティング: Render（無料枠）、認証なしの完全公開
- `render.yaml`(Blueprint) によるコード化デプロイ
- 本番サーバ: gunicorn
- `web/app.py` の `__main__` を PORT 環境変数対応（ローカル挙動は不変）
- デプロイ手順書 `docs/DEPLOY.md`

非対象（YAGNI）: 認証、キャッシュ外部化(Redis等)、Docker、独自ドメイン、CI。

## アプローチ

採用案A: `render.yaml` Blueprint + gunicorn。リポ連携で自動デプロイ。設定が
コード化され再現可能。

不採用:
- 案B（ダッシュボード手動設定）: 毎回手作業。
- 案C（Dockerfile）: 過剰。

## アーキテクチャ

### 追加ファイル

**render.yaml**（リポジトリ直下）:
```yaml
services:
  - type: web
    name: kabu-screener
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn web.app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
    envVars:
      - key: PYTHON_VERSION
        value: 3.12.10
```

**requirements.txt** に追記:
```
gunicorn>=21
```

### web/app.py の変更

`if __name__ == "__main__":` のみ PORT 環境変数対応にする（ローカル実行や
`python web/app.py` 起動時。gunicorn 経由では __main__ は実行されない）。
```python
import os
...
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    webbrowser.open(f"http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port)
```
モジュール上部の `app`（gunicorn が読む `web.app:app`）とロジックは変更しない。

### docs/DEPLOY.md

Render デプロイ手順（ユーザ操作分）を記載:
1. Render にサインイン（GitHub連携）
2. New → Blueprint → リポジトリ `Claud-code-YUTA` を選択
3. `render.yaml` が自動検出されデプロイ開始
4. 発行URL `https://<name>.onrender.com` でアクセス
5. 無料枠の制約（コールドスタート・キャッシュ揮発・yfinance制限）を明記

## 本番サーバ設定の根拠

- gunicorn: Render の Python 標準。
- `--timeout 120`: 1リクエストで40銘柄を同期取得し数十秒かかるため、既定30秒だと
  ワーカーが kill される。120秒に延長。
- `--workers 1`: 無料枠512MB・Yahoo への同時アクセス抑制。

## 既知の制約（無料枠）

1. コールドスタート: 15分無アクセスで停止 → 次回30〜60秒。
2. ファイル揮発: 再起動毎に `data/cache` 消失 → 毎回全銘柄を再取得（遅い）。
3. yfinance がクラウドIPで Yahoo にレート制限/ブロックされる場合があり、
   スクリーニングが間欠的に失敗し得る。
4. 安定運用には有料枠 or キャッシュ外部化が必要（本スコープ外）。

これらは README/DEPLOY.md に明記し、利用者の期待値を揃える。

## エラー処理

- 取得失敗銘柄はスキップ（既存挙動）。全失敗時は空の表（「該当なし」）。
- gunicorn timeout 超過時は 502 をRenderが返す（コールドスタート直後に発生し得る）→
  DEPLOY.md に「数十秒待って再読込」と明記。

## テスト

- `render.yaml` が妥当なYAMLで、startCommand の対象 `web.app:app` が import 可能で
  Flask アプリであることを検証（ネット非依存）。
- 既存の web テストは不変（ロジック変更なし）。

## 依存・影響範囲

- 追加依存: `gunicorn>=21`（requirements.txt）。
- 新規: `render.yaml`, `docs/DEPLOY.md`, `tests/test_deploy.py`。
- 変更: `web/app.py`（__main__ の PORT 対応のみ）, `README.md`（公開URL/デプロイ参照を追記）。

## 役割分担

- 私（コード側）: 上記ファイル追加・変更、テスト、手順書。
- ユーザ（要認証のため）: Render サインインと Blueprint 接続・デプロイ実行。
