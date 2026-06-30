"""product 도큐먼트 → 셀링 인사이트 뷰모델. DB·LLM 무관 순수 변환."""

_QUOTE_MAX = 120


def _norm_point(raw):
    """taxonomy point 항목 → PointItem. evidence는 url 있는 것 상위 2개, quote 절단."""
    raw = raw or {}
    ev = []
    for e in (raw.get("evidence") or []):
        if not e or not e.get("url"):
            continue
        ev.append({
            "source": e.get("source") or "",
            "date": e.get("date") or "",
            "url": e.get("url"),
            "quote": (e.get("quote") or "")[:_QUOTE_MAX],
        })
        if len(ev) == 2:
            break
    return {"point": raw.get("point") or "", "n": raw.get("cited_examples") or 0, "evidence": ev}


def _points(items):
    """point 항목 리스트 → PointItem 리스트, n 내림차순 정렬."""
    out = [_norm_point(it) for it in (items or []) if it]
    out.sort(key=lambda p: p["n"], reverse=True)
    return out
