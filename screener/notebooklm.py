"""NotebookLM 投入用 Markdown 生成。

スキャン時点の収集情報（指標・年初来騰落率・任意のニュース）を、NotebookLM が
取り込みやすい Markdown 文書にまとめる。数値は本ツールで算出済みを前提とする。
"""
from __future__ import annotations

from datetime import date

from . import report


def _cell(v):
    if isinstance(v, list):
        return " / ".join(v)
    return "" if v is None else str(v)


def _md_table(rows, top, extras):
    if not rows:
        return "該当なし\n"
    rows = rows[:top]
    cols = list(rows[0].keys())
    show_ytd = extras is not None
    headers = [report.header_label(c) for c in cols] + (["年初来%"] if show_ytd else [])
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        vals = [_cell(r.get(c)).replace("|", "/") for c in cols]
        if show_ytd:
            y = (extras.get(r.get("ticker")) or {}).get("年初来%")
            vals.append("" if y is None else str(y))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def build_markdown(sections, market, extras=None, top=20, insights=None):
    out = [f"# 株スクリーニング スナップショット（{date.today():%Y-%m-%d}）", "",
           "> 投資は自己責任。本資料は情報整理であり投資助言ではありません。", ""]

    out.append("## 市況（Fear & Greed）")
    if market.get("score") is not None:
        out.append(f"- スコア: {market['score']} / 100（{market.get('label', '')}）")
        if market.get("VIX") is not None:
            out.append(f"- VIX: {market['VIX']}")
    else:
        out.append("- 取得失敗")
    out.append("")

    for key, (title, _mv, _sheet) in report.SECTION_META.items():
        out.append(f"## {title}")
        out.append(_md_table(sections.get(key, []), top, extras))

    if extras:
        seen, blocks = set(), []
        for key, (_t, _mv, _s) in report.SECTION_META.items():
            for r in sections.get(key, [])[:top]:
                t = r.get("ticker")
                news = (extras.get(t) or {}).get("news") or []
                if news and t not in seen:
                    seen.add(t)
                    blocks.append((t, r.get("name"), news))
        if blocks:
            out.append("## ニュース")
            for t, name, news in blocks:
                out.append(f"### {t} {name or ''}".rstrip())
                for title_, url in news:
                    out.append(f"- [{title_}]({url})")
            out.append("")

    if insights:
        names = {}
        for key, (_t, _mv, _s) in report.SECTION_META.items():
            for r in sections.get(key, [])[:top]:
                names.setdefault(r.get("ticker"), r.get("name"))
        out.append("## AI考察")
        out.append("> ネット論調の要約（参考・出典付き）。投資助言ではありません。")
        out.append("")
        for t, ins in insights.items():
            if not ins:
                continue
            out.append(f"### {t} {names.get(t) or ''}".rstrip())
            out.append(ins.get("summary", ""))
            for title_, url in ins.get("sources", []):
                out.append(f"- [{title_}]({url})")
            out.append("")

    return "\n".join(out)
