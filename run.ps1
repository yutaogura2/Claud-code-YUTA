# 株スクリーニング起動ヘルパー（venv + UTF-8 を自動設定）
# 例:  .\run.ps1 value
#      .\run.ps1 all --top 15
#      .\run.ps1 market
#      .\run.ps1 web        # ブラウザUI
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$main = Join-Path $PSScriptRoot "main.py"
if ($args.Count -gt 0 -and $args[0] -eq "web") {
    & $py (Join-Path $PSScriptRoot "web\app.py")
} else {
    & $py $main @args
}
