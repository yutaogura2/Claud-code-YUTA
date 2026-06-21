"""スクリーニングの算出サービス層（CLI と Web で共用）。"""
from __future__ import annotations

from . import alpha as alp
from . import contrarian as cont
from . import data as dataio
from . import momentum as mom
from . import value as val


def fetch_universe(cfg):
    tickers = cfg["universe"]
    ttl = cfg.get("cache_ttl", 86400)
    out = []
    print(f"取得中… {len(tickers)}銘柄")
    for i, t in enumerate(tickers, 1):
        print(f"  [{i}/{len(tickers)}] {t}", end="\r")
        out.append(dataio.fetch(t, ttl=ttl))
    print()
    return out


def _apply_names(rows, names):
    """rows の name を日本語名マップで上書き（無ければ元のまま）。"""
    for r in rows:
        r["name"] = names.get(r.get("ticker"), r.get("name"))


def compute_value(cfg, stocks):
    rows = [val.value_score(s, cfg["value_weights"], cfg["value_bounds"])
            for s in stocks if s.ok]
    rows = [r for r in rows if r["score"] >= cfg.get("min_score", 0)]
    rows.sort(key=lambda r: r["score"], reverse=True)
    _apply_names(rows, cfg.get("names", {}))
    return rows


def compute_contrarian(cfg, stocks):
    rows = [r for s in stocks if (r := cont.contrarian_screen(s, cfg["contrarian"]))]
    rows = [r for r in rows if r["score"] >= 1]
    rows.sort(key=lambda r: r["score"], reverse=True)
    _apply_names(rows, cfg.get("names", {}))
    return rows


def compute_momentum(cfg, stocks):
    rows = [r for s in stocks if (r := mom.momentum_screen(s, cfg["momentum"]))]
    rows = [r for r in rows if r["score"] >= 1]
    rows.sort(key=lambda r: r["score"], reverse=True)
    _apply_names(rows, cfg.get("names", {}))
    return rows


def compute_alpha(cfg, stocks):
    ttl = cfg.get("cache_ttl", 86400)
    rows = []
    print("財務取得中…")
    for i, s in enumerate(stocks, 1):
        print(f"  [{i}/{len(stocks)}] {s.ticker}", end="\r")
        fin = dataio.fetch_financials(s.ticker, ttl)
        if fin is None:
            continue
        r = alp.alpha_screen(s, fin, cfg)
        if r:
            rows.append(r)
    print()
    rows.sort(key=lambda r: r["score"], reverse=True)
    _apply_names(rows, cfg.get("names", {}))
    return rows
