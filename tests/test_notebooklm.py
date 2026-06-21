from screener import notebooklm


def test_build_markdown_has_sections_and_ytd(sections, market):
    extras = {"6902.T": {"年初来%": 12.3, "news": []},
              "7203.T": {"年初来%": -4.5, "news": []}}
    md = notebooklm.build_markdown(sections, market, extras)
    assert md.startswith("# 株スクリーニング スナップショット")
    assert "## 市況" in md
    assert "DENSO CORP" in md
    assert "年初来%" in md and "12.3" in md
    assert "| ticker |" in md
    assert "該当なし" in md            # momentum は空


def test_build_markdown_includes_insights(sections, market):
    insights = {"6902.T": {"summary": "強気の声が多い",
                           "sources": [("記事A", "https://e.com/a")]}}
    md = notebooklm.build_markdown(sections, market, insights=insights)
    assert "## AI考察" in md
    assert "強気の声が多い" in md
    assert "[記事A](https://e.com/a)" in md
    assert "投資助言ではありません" in md


def test_build_markdown_includes_news(sections, market):
    extras = {"6902.T": {"年初来%": 1.0,
                         "news": [("好決算", "https://example.com/n1")]},
              "7203.T": {"年初来%": 1.0, "news": []}}
    md = notebooklm.build_markdown(sections, market, extras)
    assert "## ニュース" in md
    assert "[好決算](https://example.com/n1)" in md
