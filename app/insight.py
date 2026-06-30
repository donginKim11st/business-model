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


# 컨텍스트 dim 라벨 (한국어 표시용). 키 순서 = 화면 표시 순서.
_WHO = [("age", "나이"), ("gender", "성별"), ("occupation", "직업"), ("household", "가구"),
        ("body_type", "체형"), ("health", "건강"), ("taste_pref", "취향"), ("lifestyle", "라이프스타일")]
_WHEN = [("scene", "상황"), ("season", "계절"), ("event", "이벤트"), ("time_of_day", "시간대"), ("frequency", "빈도")]
_WHERE = [("place", "장소")]
_WHY = [("positive_goal", "목표"), ("negative_concern", "우려"), ("workload", "수고")]

# catalog identity passthrough 시 facts 에서 제외할 메타 키
_IDENTITY_META = {"gosi", "source", "fetched_at", "insight_uid", "ctlg_no", "brand"}


def _groups(ctx_dim, spec):
    """context 하위 dim(dict) → LabeledGroup 리스트. 빈 그룹도 points=[] 로 유지."""
    ctx_dim = ctx_dim or {}
    return [{"label": label, "points": _points(ctx_dim.get(key))} for key, label in spec]


def _facts(identity):
    """catalog identity dict → 표시용 facts (메타 키 제외, 값 있는 것만)."""
    identity = identity or {}
    return {k: str(v) for k, v in identity.items() if k not in _IDENTITY_META and v not in (None, "", {}, [])}


def _price(catalogs):
    """catalogs price_summary 중 min 최저 1건을 대표로. 없으면 None."""
    prs = [c.get("price_summary") for c in (catalogs or []) if (c.get("price_summary") or {}).get("min")]
    if not prs:
        return None
    best = min(prs, key=lambda p: p["min"])
    return {"min": best.get("min"), "median": best.get("median") or 0, "low_mall": best.get("low_mall"),
            "n_malls": best.get("n_malls") or 0, "spread_pct": best.get("spread_pct") or 0}


def build_view(doc):
    """product 도큐먼트 → 6블록 뷰모델 dict. 부분 데이터에도 안전."""
    doc = doc or {}
    tax = doc.get("taxonomy") or {}
    verdict = tax.get("verdict") or {}
    ctx = tax.get("context") or {}
    catalogs = doc.get("catalogs") or []
    specs = []
    for c in catalogs:
        facts = _facts(c.get("identity"))
        if facts:
            specs.append({"ctlg_no": str(c.get("ctlg_no") or ""), "disp": c.get("disp") or "", "facts": facts})
    return {
        "uid": doc.get("_id") or "",
        "keyword": doc.get("keyword") or "",
        "category_l1": doc.get("category_l1"),
        "type": doc.get("type") or "",
        "analyzed_count": doc.get("analyzed_count") or 0,
        "source_counts": doc.get("sources") or {},
        "ad_flagged": doc.get("ad_flagged") or 0,
        "strengths": _points(verdict.get("strengths")),
        "weaknesses": _points(verdict.get("weaknesses")),
        "targets": {
            "who": _groups(ctx.get("who"), _WHO),
            "when": _groups(ctx.get("when"), _WHEN),
            "where": _groups(ctx.get("where"), _WHERE),
            "why": _groups(ctx.get("why"), _WHY),
        },
        "gift": _points((ctx.get("gift") or {}).get("recipient")),
        "specs": specs,
        "identity_status": (doc.get("identity") or {}).get("status"),
        "price": _price(catalogs),
    }
