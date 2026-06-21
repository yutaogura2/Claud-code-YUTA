"""日本株スクリーニング CLI。

使い方:
  python main.py value        # バリュースクリーニング（割安株）
  python main.py contrarian   # 逆張り（売られすぎ）
  python main.py momentum     # モメンタム（強い銘柄）
  python main.py market       # 市場の Fear & Greed
  python main.py all          # 上記スクリーニング3種をまとめて

オプション:
  --config config.yaml  設定ファイル
  --top N               上位N件表示（既定20）
  --no-save             結果CSVを保存しない
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from datetime import date
from pathlib import Path

import yaml

from screener import ai_insight
from screener import fear_greed as fg
from screener import notebooklm
from screener import report as report_mod
from screener import screen
from screener import store

ROOT = Path(__file__).resolve().parent


def load_cfg(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _cell(v) -> str:
    if isinstance(v, list):
        return " / ".join(v)
    return "" if v is None else str(v)


def _print_table(rows: list[dict], top: int):
    if not rows:
        print("該当なし")
        return
    rows = rows[:top]
    cols = list(rows[0].keys())
    labels = {c: report_mod.header_label(c) for c in cols}
    widths = {c: max(len(labels[c]), *(len(_cell(r.get(c))) for r in rows)) for c in cols}
    print(" | ".join(labels[c].ljust(widths[c]) for c in cols))
    print("-+-".join("-" * widths[c] for c in cols))
    for r in rows:
        print(" | ".join(_cell(r.get(c)).ljust(widths[c]) for c in cols))


def run_value(cfg, stocks, top, save):
    rows = screen.compute_value(cfg, stocks)
    _attach_diff_and_show("value", rows, top, save, "■ バリュースクリーニング（割安株 / 100点満点）")


def run_contrarian(cfg, stocks, top, save):
    rows = screen.compute_contrarian(cfg, stocks)
    _attach_diff_and_show("contrarian", rows, top, save, "■ 逆張り（売られすぎ / 該当条件数 0-6）")


def run_momentum(cfg, stocks, top, save):
    rows = screen.compute_momentum(cfg, stocks)
    _attach_diff_and_show("momentum", rows, top, save, "■ モメンタム（強い銘柄 / 該当条件数 0-5）")


def _attach_diff_and_show(mode, rows, top, save, title):
    diff = store.diff_scores(mode, rows)
    for r in rows:
        if r["ticker"] in diff:
            d = diff[r["ticker"]]
            r["前回比"] = f"+{d}" if d > 0 else str(d)
    print(f"\n{title}")
    _print_table(rows, top)
    if save and rows:
        p = store.save(mode, rows)
        print(f"\n保存: {p.relative_to(ROOT)}")


def run_alpha(cfg, stocks, top, save):
    rows = screen.compute_alpha(cfg, stocks)
    _attach_diff_and_show("alpha", rows, top, save,
                          "■ アルファ（割安×業績改善 / combined＝(value+change)/2）")


def run_market(cfg):
    print("\n■ 市場センチメント（Fear & Greed）")
    r = fg.fear_greed(cfg["index"], cfg["vix"], cfg.get("cache_ttl", 86400))
    if r["score"] is None:
        print(r["label"]); return
    print(f"  スコア: {r['score']} / 100  → {r['label']}")
    if r.get("VIX") is not None:
        print(f"  VIX: {r['VIX']}")
    print("  内訳:", "  ".join(f"{k}={v:.0f}" for k, v in r["内訳"].items()))


def run_report(cfg, stocks, top, open_after, news=False, insight=False):
    sections = {
        "value": screen.compute_value(cfg, stocks),
        "contrarian": screen.compute_contrarian(cfg, stocks),
        "momentum": screen.compute_momentum(cfg, stocks),
    }
    market = fg.fear_greed(cfg["index"], cfg["vix"], cfg.get("cache_ttl", 86400))

    rdir = ROOT / "data" / "reports"
    stamp = f"{date.today():%Y%m%d}"
    html_path = report_mod.build_html(sections, market, rdir / f"report_{stamp}.html", top)
    xlsx_path = report_mod.build_excel(sections, market, rdir / f"report_{stamp}.xlsx", top)
    extras = screen.collect_extras(stocks, with_news=news)
    insights = None
    if insight:
        ai_cfg = cfg.get("ai_insight", {})
        model = ai_cfg.get("model", "gemini-2.5-flash")
        names = cfg.get("names", {})
        insights = {}
        for r in sections["value"][:ai_cfg.get("top_n", 10)]:
            t = r["ticker"]
            ins = ai_insight.fetch_insight(t, names.get(t) or r.get("name") or t, model=model)
            if ins:
                insights[t] = ins
    md_path = rdir / f"report_{stamp}.md"
    md_path.write_text(
        notebooklm.build_markdown(sections, market, extras, top, insights=insights),
        encoding="utf-8")
    print(f"HTML : {html_path.relative_to(ROOT)}")
    print(f"Excel: {xlsx_path.relative_to(ROOT)}")
    print(f"MD   : {md_path.relative_to(ROOT)}")

    if open_after:
        try:
            webbrowser.open(html_path.as_uri())
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] 自動オープン失敗: {e}")


def main(argv=None):
    p = argparse.ArgumentParser(description="日本株スクリーニング")
    p.add_argument("mode", choices=["value", "contrarian", "momentum",
                                    "market", "all", "report", "alpha"])
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--no-open", action="store_true", help="reportでHTMLを自動で開かない")
    p.add_argument("--news", action="store_true", help="reportのMarkdownにニュースを含める")
    p.add_argument("--insight", action="store_true", help="reportのMarkdownにAI考察を含める")
    a = p.parse_args(argv)

    cfg = load_cfg(a.config)
    save = not a.no_save

    if a.mode == "market":
        run_market(cfg)
        return

    stocks = screen.fetch_universe(cfg)
    if a.mode == "report":
        run_report(cfg, stocks, a.top, open_after=not a.no_open, news=a.news, insight=a.insight)
        return
    if a.mode == "alpha":
        run_alpha(cfg, stocks, a.top, save)
        return
    if a.mode in ("value", "all"):
        run_value(cfg, stocks, a.top, save)
    if a.mode in ("contrarian", "all"):
        run_contrarian(cfg, stocks, a.top, save)
    if a.mode in ("momentum", "all"):
        run_momentum(cfg, stocks, a.top, save)
    if a.mode == "all":
        run_market(cfg)


if __name__ == "__main__":
    sys.exit(main())
