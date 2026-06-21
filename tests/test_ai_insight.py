from screener import ai_insight
from screener import data as dataio


def test_fetch_insight_parses(monkeypatch, tmp_path):
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(ai_insight, "_post", lambda url, payload, timeout=30: {
        "candidates": [{
            "content": {"parts": [{"text": "強気の声が多い"}]},
            "groundingMetadata": {"groundingChunks": [
                {"web": {"uri": "https://e.com/a", "title": "記事A"}}]},
        }]})
    out = ai_insight.fetch_insight("7203.T", "トヨタ自動車")
    assert out["summary"] == "強気の声が多い"
    assert out["sources"] == [("記事A", "https://e.com/a")]


def test_fetch_insight_no_key_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(dataio, "CACHE_DIR", tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ai_insight.fetch_insight("7203.T", "トヨタ") is None
