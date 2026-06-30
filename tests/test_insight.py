from app.insight import _norm_point, _points


def test_norm_point_trims_evidence_and_quote():
    raw = {
        "point": "간편하게 조리할 수 있다.",
        "cited_examples": 2,
        "evidence": [
            {"source": "naver", "date": "20260604", "url": "http://a", "quote": "x" * 200},
            {"source": "danawa", "date": "20251229", "url": "http://b", "quote": "ok"},
            {"source": "naver", "date": "20260101", "url": None, "quote": "no url"},
        ],
    }
    p = _norm_point(raw)
    assert p["point"] == "간편하게 조리할 수 있다."
    assert p["n"] == 2
    assert len(p["evidence"]) == 2                      # url 없는 항목 제외 + 상위 2개
    assert len(p["evidence"][0]["quote"]) == 120        # 절단
    assert p["evidence"][0]["url"] == "http://a"


def test_norm_point_handles_missing_fields():
    p = _norm_point({"point": "x"})
    assert p == {"point": "x", "n": 0, "evidence": []}


def test_points_sorts_desc_by_n_and_handles_none():
    items = [{"point": "a", "cited_examples": 1}, {"point": "b", "cited_examples": 5}]
    out = _points(items)
    assert [p["point"] for p in out] == ["b", "a"]
    assert _points(None) == []
    assert _points([]) == []
