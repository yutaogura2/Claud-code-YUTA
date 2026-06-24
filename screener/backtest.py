"""価格ベースの簡易ポートフォリオ・バックテスト。

逆張り/モメンタムの価格専用スコアで一定間隔リバランスを試算する。
取引コスト・配当・スリッページは無視。サバイバーシップ・バイアスあり。
"""
from __future__ import annotations

from . import indicators as ind


def _metrics(equity, years):
    """equity（先頭1.0規約）から指標を算出。"""
    n = len(equity)
    total = (equity[-1] - 1) if n else 0.0
    rets = [equity[i] / equity[i - 1] - 1 for i in range(1, n) if equity[i - 1]]
    win = (sum(1 for r in rets if r > 0) / len(rets) * 100) if rets else 0.0
    peak, mdd = (equity[0] if n else 1.0), 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    cagr = (equity[-1] ** (1 / years) - 1) if (n and equity[-1] > 0 and years > 0) else 0.0
    return {"累積%": round(total * 100, 1), "CAGR%": round(cagr * 100, 1),
            "最大DD%": round(mdd * 100, 1), "期間": len(rets), "勝率%": round(win, 1)}


def _contrarian_score(close, vol):
    """価格専用の逆張りスコア（0-4）。"""
    if len(close) < 20:
        return 0
    price = float(close.iloc[-1])
    rsi = ind.rsi(close)
    dev200 = ind.deviation_pct(price, ind.sma(close, 200))
    _, _, bb_low = ind.bollinger(close)
    vr = ind.volume_ratio(vol)
    return int(sum([
        rsi <= 30,
        dev200 < 0,
        price < bb_low if bb_low == bb_low else False,
        vr >= 1.5 if vr == vr else False,
    ]))


def _momentum_score(close, vol):
    """価格専用のモメンタムスコア（0-5）。"""
    if len(close) < 30:
        return 0
    price = float(close.iloc[-1])
    rsi = ind.rsi(close)
    macd_line, macd_sig = ind.macd(close)
    roc_now = ind.roc(close, 12)
    roc_prev = ind.roc(close.iloc[:-5], 12)
    vr = ind.volume_ratio(vol)
    dev200 = ind.deviation_pct(price, ind.sma(close, 200))
    return int(sum([
        rsi >= 70,
        macd_line > macd_sig,
        (roc_now == roc_now and roc_prev == roc_prev and roc_now > roc_prev),
        vr >= 1.2 if vr == vr else False,
        dev200 > 0,
    ]))


def run_strategy(histories, score_fn, top_n, step, warmup):
    """一定間隔リバランスの等金額ポートフォリオを試算。"""
    if not histories:
        return {"dates": [], "equity": [1.0], "metrics": _metrics([1.0], 1.0)}
    ref = max((h.index for h in histories.values()), key=len)
    if len(ref) <= warmup:
        return {"dates": [], "equity": [1.0], "metrics": _metrics([1.0], 1.0)}

    points = list(range(warmup, len(ref) - 1, step))
    dates, equity = [], [1.0]
    for k in range(len(points) - 1):
        d, d2 = ref[points[k]], ref[points[k + 1]]
        scored = []
        for t, h in histories.items():
            sub = h.loc[:d]
            if len(sub) < warmup:
                continue
            sc = score_fn(sub["Close"], sub["Volume"])
            if sc > 0:
                scored.append((sc, t))
        scored.sort(key=lambda x: x[0], reverse=True)
        picks = [t for _, t in scored[:top_n]]
        rets = []
        for t in picks:
            h = histories[t]
            try:
                p1 = float(h.loc[:d]["Close"].iloc[-1])
                p2 = float(h.loc[:d2]["Close"].iloc[-1])
                if p1:
                    rets.append(p2 / p1 - 1)
            except Exception:  # noqa: BLE001
                pass
        r = sum(rets) / len(rets) if rets else 0.0
        equity.append(equity[-1] * (1 + r))
        dates.append(d2)
    years = max(1e-9, max(1, len(points) - 1) * step / 252)
    return {"dates": dates, "equity": equity, "metrics": _metrics(equity, years)}


def run_backtest(histories, benchmark_close, cfg):
    bt = cfg.get("backtest", {})
    top_n = bt.get("top_n", 5)
    step = bt.get("rebalance_days", 21)
    warmup = bt.get("warmup_days", 200)
    out = {
        "contrarian": run_strategy(histories, _contrarian_score, top_n, step, warmup),
        "momentum": run_strategy(histories, _momentum_score, top_n, step, warmup),
        "benchmark": None,
    }
    if benchmark_close is not None and len(benchmark_close) > warmup:
        c = benchmark_close.iloc[warmup:]
        base = float(c.iloc[0])
        eq = ([1.0] + [float(v) / base for v in c]) if base else [1.0]
        years = max(1e-9, len(c) / 252)
        out["benchmark"] = {"equity": eq, "metrics": _metrics(eq, years)}
    return out
