import json
import pathlib
from app.insight import _norm_point, _points, build_view

FIX = pathlib.Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


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


def test_build_view_full_assembles_six_blocks():
    v = build_view(_load("product_full.json"))
    assert v["uid"] == "P7863"
    assert v["keyword"] == "쿡시 사골 미역국 쌀국수"
    assert v["type"] == "package"
    assert v["source_counts"]["youtube"] == 184
    # 강점/약점 빈도 정렬
    assert [s["point"] for s in v["strengths"]] == ["간편하게 조리할 수 있다.", "국물이 깊다."]
    assert v["weaknesses"][0]["point"] == "면이 쉽게 분다."
    # 타깃: who 그룹 라벨, 빈 그룹은 points=[] 로 유지
    who_labels = {g["label"]: g["points"] for g in v["targets"]["who"]}
    assert "가구" in who_labels and who_labels["가구"][0]["point"] == "부모님과 함께"
    assert who_labels["나이"] == []
    # 선물
    assert v["gift"][0]["point"] == "부모님댁 선물"
    # 정형 사실: identity 비어있지 않은 catalog만
    assert len(v["specs"]) == 1
    assert v["specs"][0]["facts"]["origin"] == "대한민국"
    assert "gosi" not in v["specs"][0]["facts"]      # gosi/source/fetched_at 메타 제외
    assert v["identity_status"] == "done"
    # 가격: catalog price_summary 집계(median 최저 기준 대표 1건)
    assert v["price"]["min"] == 9900
    assert v["price"]["low_mall"] == "쿠팡"


def test_build_view_degraded_hides_missing_blocks_without_crash():
    v = build_view(_load("product_degraded.json"))
    assert v["strengths"] == []
    assert v["weaknesses"] == []
    assert v["specs"] == []                           # identity 빈 dict → 제외
    assert v["identity_status"] == "pending"
    assert v["price"] is None                         # price_summary 없음
    # 모든 타깃 그룹 존재하되 points 빈 리스트
    assert all(g["points"] == [] for g in v["targets"]["who"])
