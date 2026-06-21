# AI考察（ネット論調）の設定

各銘柄に「ネット上の論調の要約（出典付き・参考）」を付ける機能。Gemini API を使用。

## キー取得・設定

1. Google AI Studio (https://aistudio.google.com/) で API キーを発行（無料枠あり）。
2. ローカル（PowerShell・一時的）:
   ```powershell
   $env:GEMINI_API_KEY = "取得したキー"
   .\run.ps1 report --insight
   ```
   常設するなら Windows のユーザー環境変数に `GEMINI_API_KEY` を登録。
3. 公開（Render）: サービスの Environment に `GEMINI_API_KEY` を追加。

## 使い方

- CLI: `.\run.ps1 report --insight` … 上位N銘柄の考察を `.md` に付加。
- Web: レポートの「AI考察つきMarkdown」、銘柄詳細の「AI考察を取得」。

## 注意

- 既定はオフ（明示時のみ呼び出し）。上位N（config `ai_insight.top_n`）と24hキャッシュでコスト抑制。
- 出力はネット論調の要約（参考・出典付き）であり、投資助言ではありません。
- キーは環境変数のみ。リポジトリ・config には保存しないこと。
