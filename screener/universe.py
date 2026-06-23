"""銘柄プリセット（presets/<name>.csv）の読込と config への適用。"""
from __future__ import annotations

from pathlib import Path

PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"


def load_preset(name):
    """presets/<name>.csv を (tickers, names) で返す。各行 `コード,日本語名`。
    `#` 始まり・空行・カンマ無し行はスキップ。"""
    path = PRESETS_DIR / f"{name}.csv"
    tickers, names = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "," not in s:
            continue
        code, nm = s.split(",", 1)
        code, nm = code.strip(), nm.strip()
        if not code:
            continue
        tickers.append(code)
        names[code] = nm
    return tickers, names


def apply_preset(cfg):
    """cfg["universe_preset"] が設定されていれば universe/names を差し替える。
    inline の names を優先。未設定なら何もしない。"""
    name = cfg.get("universe_preset")
    if not name:
        return
    tickers, names = load_preset(name)
    cfg["universe"] = tickers
    cfg["names"] = {**names, **(cfg.get("names") or {})}
