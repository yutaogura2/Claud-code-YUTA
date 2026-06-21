"""Flask Web UI（CLIスクリーナーをブラウザから操作）。"""
from __future__ import annotations

import html
import os
import sys
import webbrowser
from pathlib import Path

import yaml
from flask import Flask, abort, request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # 'screener' を import 可能にする（スクリプト実行時）

from screener import data as dataio  # noqa: E402
from screener import fear_greed as fg  # noqa: E402
from screener import report  # noqa: E402
from screener import screen  # noqa: E402
from screener.alpha import change_score  # noqa: E402
from screener.value import value_score  # noqa: E402

app = Flask(__name__)
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))

# mode → (見出し, スコア最大値)
MODES = {
    "value":      ("バリュー（割安株 / 100点）", 100),
    "contrarian": ("逆張り（売られすぎ / 0-6）", 6),
    "momentum":   ("モメンタム（0-5）", 5),
    "alpha":      ("アルファ（割安×改善 / 100点）", 100),
}


def _page(body: str) -> str:
    return report._HTML_HEAD + body + "</body></html>"


def _nav() -> str:
    return '<p><a href="/">← ホーム</a></p>'


@app.route("/")
def home():
    opts = "".join(f'<option value="{m}">{t}</option>' for m, (t, _) in MODES.items())
    opts += '<option value="market">市場 Fear&amp;Greed</option>'
    body = f"""
<h1>株スクリーニング</h1>
<form action="/screen" method="get" onsubmit="document.getElementById('s').style.display='block'">
  <label>モード <select name="mode">{opts}</select></label>
  <label>上位 <input type="number" name="top" value="20" min="1" max="100" style="width:5em"></label>
  <button type="submit">実行</button>
</form>
<p id="s" style="display:none;color:#305496">実行中… (初回は数十秒)</p>
"""
    return _page(body)


def _market_page():
    r = fg.fear_greed(CFG["index"], CFG["vix"], CFG.get("cache_ttl", 86400))
    if r.get("score") is None:
        return _page(f"{_nav()}<p class='empty'>市況データ取得失敗</p>")
    bars = report._svg_hbar([(k, v) for k, v in r.get("内訳", {}).items()], 100)
    body = (f"{_nav()}<h1>市場センチメント（Fear &amp; Greed）</h1>"
            f"<div class='gauge'>{report._svg_gauge(r['score'])}"
            f"<p class='label'>{r['label']}（VIX {r.get('VIX')}）</p></div>{bars}")
    return _page(body)


@app.route("/screen")
def screen_route():
    mode = request.args.get("mode", "value")
    if mode == "market":
        return _market_page()
    if mode not in MODES:
        abort(400)
    top = request.args.get("top", 20, type=int) or 20
    top = max(1, min(top, 100))
    title, mv = MODES[mode]
    stocks = screen.fetch_universe(CFG)
    rows = getattr(screen, f"compute_{mode}")(CFG, stocks)
    table = report._table_html(rows, top, mv, link_base="/stock/")
    bar = report._svg_hbar(
        [(r.get("name") or r["ticker"], r["score"]) for r in rows[:10]], mv)
    body = f"{_nav()}<h1>{title}</h1>{table}{bar}"
    return _page(body)


@app.route("/stock/<ticker>")
def stock_page(ticker):
    safe_ticker = html.escape(ticker)
    sd = dataio.fetch(ticker, CFG.get("cache_ttl", 86400))
    if not sd.info and not sd.ok:
        return _page(f"{_nav()}<p class='empty'>{safe_ticker} のデータ取得失敗</p>")
    name = html.escape(sd.info.get("shortName") or ticker)

    chart = report._svg_line(sd.history["Close"]) if sd.ok else ""
    chart = chart or "<p class='empty'>価格データなし</p>"

    v = value_score(sd, CFG["value_weights"], CFG["value_bounds"])
    v_rows = [{"指標": k, "値": v.get(k)}
              for k in ("score", "PER", "PBR", "配当%", "ROE%", "売上成長%")]

    fin = dataio.fetch_financials(ticker, CFG.get("cache_ttl", 86400))
    c = change_score(fin, CFG["alpha_weights"], CFG["alpha_bounds"]) if fin else None
    if c:
        c_rows = [{"指標": k, "値": c.get(k)}
                  for k in ("change", "アクルーアルズ", "売上加速%", "FCFマージンΔ%", "ROEΔ%")]
        c_html = report._table_html(c_rows, 10, 100)
    else:
        c_html = "<p class='empty'>財務データなし</p>"

    body = (f"{_nav()}<h1>{name} <small>{safe_ticker}</small></h1>"
            f"<section><h2>株価</h2>{chart}</section>"
            f"<section><h2>バリュー内訳</h2>{report._table_html(v_rows, 10, 100)}</section>"
            f"<section><h2>変化スコア内訳</h2>{c_html}</section>")
    return _page(body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    webbrowser.open(f"http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port)
