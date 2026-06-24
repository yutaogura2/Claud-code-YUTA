"""スクリーニングの算出サービス層（CLI と Web で共用）。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from . import alpha as alp
from . import contrarian as cont
from . import data as dataio
from . import indicators as ind
from . import momentum as mom
from . import value as val


def fetch_universe(cfg):
    tickers = cfg["universe"]
    ttl = cfg.get("cache_ttl", 86400)
    workers = max(1, (cfg.get("fetch") or {}).get("max_workers", 8))
    print(f"取得中… {len(tickers)}銘柄（並列{workers}）")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        out = list(ex.map(lambda t: dataio.fetch(t, ttl=ttl), tickers))
    print(f"完了 {len(out)}件")
    return out


def fetch_histories(cfg):
    """universe の長期履歴を並列取得し {ticker: DataFrame} を返す。"""
    tickers = cfg["universe"]
    ttl = cfg.get("cache_ttl", 86400)
    period = (cfg.get("backtest") or {}).get("period", "3y")
    workers = max(1, (cfg.get("fetch") or {}).get("max_workers", 8))
    print(f"履歴取得中… {len(tickers)}銘柄（並列{workers}, {period}）")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        hists = list(ex.map(lambda t: dataio.fetch_history(t, period, ttl), tickers))
    out = {t: h for t, h in zip(tickers, hists) if h is not None and not h.empty}
    print(f"完了 {len(out)}件")
    return out


def _apply_names(rows, names):
    """rows の name を日本語名マップで上書き（無ければ元のまま）。"""
    for r in rows:
        r["name"] = names.get(r.get("ticker"), r.get("name"))


def collect_extras(stocks, with_news=False):
    """銘柄ごとの追加情報 {ticker: {"年初来%", "news"}} を返す。"""
    out = {}
    for s in stocks:
        ytd = ind.ytd_return(s.history["Close"]) if s.ok else float("nan")
        out[s.ticker] = {
            "年初来%": round(ytd, 1) if ytd == ytd else None,
            "news": dataio.fetch_news(s.ticker) if with_news else [],
        }
    return out


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
    workers = max(1, (cfg.get("fetch") or {}).get("max_workers", 8))
    print(f"財務取得中…（並列{workers}）")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fins = list(ex.map(lambda s: dataio.fetch_financials(s.ticker, ttl), stocks))
    rows = []
    for s, fin in zip(stocks, fins):
        if fin is None:
            continue
        r = alp.alpha_screen(s, fin, cfg)
        if r:
            rows.append(r)
    rows.sort(key=lambda r: r["score"], reverse=True)
    _apply_names(rows, cfg.get("names", {}))
    return rows
