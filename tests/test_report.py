from screener import report


def test_score_color_none_is_grey():
    assert report._score_color(None) == "#eeeeee"


def test_score_color_returns_hex():
    c = report._score_color(50, 100)
    assert c.startswith("#") and len(c) == 7


def test_score_color_high_is_greener_than_low():
    low = report._score_color(0, 100)
    high = report._score_color(100, 100)
    # 緑チャンネル(3-4文字目)が高スコアで大きい
    assert int(high[3:5], 16) > int(low[3:5], 16)


def test_svg_hbar_contains_labels():
    svg = report._svg_hbar([("デンソー", 86.0), ("トヨタ", 50.0)], 100)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "デンソー" in svg and "トヨタ" in svg


def test_svg_hbar_empty_is_blank():
    assert report._svg_hbar([], 100) == ""


def test_svg_gauge_shows_score():
    svg = report._svg_gauge(88)
    assert svg.startswith("<svg") and "88" in svg


def test_svg_gauge_none_is_zero():
    svg = report._svg_gauge(None)
    assert ">0<" in svg


def test_build_html_writes_file(tmp_path, sections, market):
    out = report.build_html(sections, market, tmp_path / "r.html")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "DENSO CORP" in text          # バリュー銘柄
    assert "NTT INC" in text             # 逆張り銘柄
    assert "バリュー" in text and "逆張り" in text and "モメンタム" in text
    assert "極度の強欲" in text          # 市況ラベル


def test_build_html_empty_section_shows_none(tmp_path, sections, market):
    out = report.build_html(sections, market, tmp_path / "r.html")
    # momentum は空 → 「該当なし」
    assert "該当なし" in out.read_text(encoding="utf-8")
