"""銘柄ごとのネット論調要約（Gemini API・google_search grounding）。

要約と出典を返す参考情報。APIキーは環境変数 GEMINI_API_KEY のみ。
未設定・失敗時は None（機能オフ）。結果は24hキャッシュ。
"""
from __future__ import annotations

import os

import requests

from .data import _read_cache, _write_cache

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _post(url, payload, timeout=30):
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_insight(ticker, name, model="gemini-2.5-flash", ttl=86400):
    cache_key = ticker + "_insight"
    cached = _read_cache(cache_key, ttl)
    if cached is not None:
        ins = cached.get("insight")
        if not ins or not ins.get("summary"):
            return None
        return {"summary": ins["summary"],
                "sources": [tuple(s) for s in ins.get("sources", [])]}

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    prompt = (f"日本株「{name}（{ticker}）」について、ネット上の論調・強気/弱気の"
              "見方・主なリスクを日本語で200字程度に要約してください。"
              "投資助言ではなく、事実と意見の整理として記述してください。")
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "tools": [{"google_search": {}}]}
    url = _ENDPOINT.format(model=model) + f"?key={api_key}"
    try:
        data = _post(url, payload)
        cand = (data.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        summary = "".join(p.get("text", "") for p in parts).strip()
        chunks = (cand.get("groundingMetadata") or {}).get("groundingChunks") or []
        sources = []
        for ch in chunks:
            web = ch.get("web") or {}
            uri = web.get("uri")
            if uri:
                sources.append((web.get("title") or uri, uri))
            if len(sources) >= 5:
                break
        if not summary:
            return None
        _write_cache(cache_key, {"insight": {"summary": summary, "sources": sources}})
        return {"summary": summary, "sources": sources}
    except Exception:  # noqa: BLE001
        return None
