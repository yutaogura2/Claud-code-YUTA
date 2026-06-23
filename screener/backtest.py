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
