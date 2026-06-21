# AI考察（ネット論調）付加 設計

作成日: 2026-06-21

## 目的

各銘柄に「ネット上の論調・評価・リスク」の要約（出典付き）を参考情報として
付加する。Claude のトークンを使わず、外部の Web 接続 AI（Gemini API）に委譲する。

> 各考察はネット論調の要約（参考・出典付き）であり、投資助言ではない。

## スコープ

- 外部AI: **Gemini API**（Google検索 grounding・出典付き）。キーは環境変数。
- 対象: 上位N銘柄（レポート）＋ 個別銘柄ページで都度（オンデマンド）。
- 出力: NotebookLM用Markdown の「AI考察」節 ＋ Web `/stock` ページ。
- 既定オフ（明示時のみ呼び出し）・24hキャッシュでコスト/レート抑制。

非対象（YAGNI）: 全銘柄一括の自動考察、Perplexity/Grok対応、考察の永続DB。

## アーキテクチャ

### 新規 screener/ai_insight.py

- `fetch_insight(ticker, name, model="gemini-2.5-flash", ttl=86400) -> dict | None`
  - `data/cache/<ticker>_insight.json` を24hキャッシュ参照。
  - `GEMINI_API_KEY` 環境変数が無ければ `None`（機能オフ）。
  - `requests` で Gemini REST `generateContent` を呼ぶ。`tools:[{"google_search":{}}]`
    でグラウンディング。プロンプトは「日本株 {name}（{ticker}）のネット上の論調・
    強気/弱気の見方・リスクを日本語200字程度で。投資助言ではなく整理として」。
  - 応答から `summary`（本文テキスト）と `sources`（groundingMetadata の
    web.uri/title を最大5件）を抽出。
  - 戻り: `{"summary": str, "sources": [(title, url), ...]}`。例外・空は `None`。
  - 失敗・無キーでもアプリは継続（best-effort）。

### notebooklm.py 拡張

- `build_markdown(sections, market, extras=None, top=20, insights=None)`：
  `insights`（`{ticker: {"summary", "sources"}}`）があれば末尾に `## AI考察` 節を追加。
  銘柄ごとに `### <ticker> <名>` ＋ 要約 ＋ 出典リンク ＋ 注記。

### Web（web/app.py）

- `/stock/<ticker>?insight=1`：`ai_insight.fetch_insight` を呼び、考察セクションを
  表示。`?insight=1` 無しのときは「AI考察を取得」リンクのみ（コスト発生を防ぐ）。
- `/report.md?insight=1`：value 上位 `top_n` 銘柄に対し insight を集め、Markdown に付加。
  `insight=1` 無しは従来どおり考察なし。
- `/report` ページに「AI考察つきMarkdownを取得」リンク（`/report.md?insight=1`）を追加。

### CLI（main.py）

- `report --insight`：value 上位 `top_n` 銘柄の insight を集め `.md` に付加。
  既定（フラグ無し）は呼び出さない。

### config.yaml

```yaml
ai_insight:
  provider: gemini
  model: "gemini-2.5-flash"
  top_n: 10
```

## データフロー

```
（明示時のみ）対象銘柄 → ai_insight.fetch_insight（24hキャッシュ→無ければGemini）
  → {summary, sources} → notebooklm「## AI考察」/ Web /stock に描画
```

## エラー処理・コスト

- `GEMINI_API_KEY` 未設定: 考察は付かない（UIは「未設定」または非表示）。エラーにしない。
- API 失敗・タイムアウト: その銘柄は考察なし（`None`）。
- 既定オフ＋上位N限定＋24hキャッシュ＋オンデマンドで呼び出し回数を最小化。
- 出典は最大5件。要約は数百字。

## セキュリティ

- `GEMINI_API_KEY` は環境変数のみ。リポジトリ・config にキーを書かない。
- 公開（Render）で使う場合は Render の Environment に設定。

## テスト（実装時 TDD・ネット非依存）

1. `ai_insight.fetch_insight`: HTTP呼び出し（`ai_insight._post`）をmonkeypatchし、
   ダミー応答から `summary`/`sources` を整形して返す。
2. `ai_insight.fetch_insight`: `GEMINI_API_KEY` 未設定で `None`。
3. `notebooklm.build_markdown`: `insights` 指定時に `## AI考察`・要約・出典リンクを含む。
4. `GET /stock/<t>?insight=1`: `fetch_insight` をmonkeypatchし考察表示。`insight` 無しは
   「AI考察を取得」リンクのみ。
5. `GET /report.md?insight=1`: insight をmonkeypatchし `## AI考察` を含む。

## 依存・影響範囲

- 追加依存: `requests>=2`（Gemini呼び出し。yfinance経由で導入済を明示化）。
- 新規: `screener/ai_insight.py`, `docs/AI_INSIGHT.md`, `tests/test_ai_insight.py`。
- 変更: `screener/notebooklm.py`（insights節）, `web/app.py`（/stock・/report.md の insight）,
  `main.py`（report --insight）, `config.yaml`（ai_insight）, `requirements.txt`, `README.md`。

## あなたの操作（要Googleアカウント）

1. Google AI Studio で Gemini API キーを取得（無料枠）。
2. ローカル: 環境変数 `GEMINI_API_KEY` を設定。Render: Environment に追加。
3. 詳細は `docs/AI_INSIGHT.md`。
