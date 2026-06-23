from screener import universe


def _write(tmp_path, monkeypatch, text):
    monkeypatch.setattr(universe, "PRESETS_DIR", tmp_path)
    (tmp_path / "dummy.csv").write_text(text, encoding="utf-8")


def test_load_preset_parses_and_skips(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch,
           "# comment\n\n7203.T,トヨタ自動車\n6758.T, ソニーグループ \nINVALIDLINE\n")
    tickers, names = universe.load_preset("dummy")
    assert tickers == ["7203.T", "6758.T"]          # コメント/空/不正行はスキップ
    assert names["7203.T"] == "トヨタ自動車"
    assert names["6758.T"] == "ソニーグループ"        # 前後空白は除去


def test_apply_preset_overrides_universe_inline_names_win(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, "7203.T,トヨタ\n6758.T,ソニー\n")
    cfg = {"universe_preset": "dummy", "universe": ["X.T"],
           "names": {"7203.T": "トヨタ自動車(独自)"}}
    universe.apply_preset(cfg)
    assert cfg["universe"] == ["7203.T", "6758.T"]
    assert cfg["names"]["7203.T"] == "トヨタ自動車(独自)"  # inline優先
    assert cfg["names"]["6758.T"] == "ソニー"             # presetから


def test_apply_preset_noop_when_unset():
    cfg = {"universe": ["A.T"], "names": {"A.T": "x"}}
    universe.apply_preset(cfg)
    assert cfg["universe"] == ["A.T"] and cfg["names"] == {"A.T": "x"}
