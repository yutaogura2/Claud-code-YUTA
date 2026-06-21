"""結果の蓄積（Vol.2 の軽量版）。

スクリーニング結果を data/history/<mode>_<日付>.csv に保存し、
最新結果と過去結果の比較（スコア変化）を可能にする。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

HIST_DIR = Path(__file__).resolve().parent.parent / "data" / "history"


def save(mode: str, rows: list[dict]) -> Path:
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    # list 列（該当）は CSV 用に文字列化
    for col in df.columns:
        if df[col].apply(lambda v: isinstance(v, list)).any():
            df[col] = df[col].apply(lambda v: " / ".join(v) if isinstance(v, list) else v)
    path = HIST_DIR / f"{mode}_{date.today():%Y%m%d}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def latest_previous(mode: str) -> pd.DataFrame | None:
    """同モードの直近(今日を除く最新)の保存結果を返す。"""
    files = sorted(HIST_DIR.glob(f"{mode}_*.csv"))
    today = f"{mode}_{date.today():%Y%m%d}.csv"
    files = [f for f in files if f.name != today]
    if not files:
        return None
    return pd.read_csv(files[-1])


def diff_scores(mode: str, rows: list[dict]) -> dict[str, float]:
    """前回保存比のスコア変化を {ticker: delta} で返す。"""
    prev = latest_previous(mode)
    if prev is None or "ticker" not in prev:
        return {}
    prev_map = dict(zip(prev["ticker"], prev["score"]))
    out = {}
    for r in rows:
        t = r["ticker"]
        if t in prev_map:
            out[t] = round(r["score"] - float(prev_map[t]), 1)
    return out
