import mongomock
from app import data


def _seed():
    db = mongomock.MongoClient().db
    db.products.insert_many([
        {"_id": "P1", "keyword": "쿡시 미역국", "category_l1": "식품", "type": "package",
         "analyzed_count": 100, "sources": {"naver": 20}},
        {"_id": "P2", "keyword": "신라면", "category_l1": "식품", "type": "single",
         "analyzed_count": 50, "sources": {"naver": 10}},
    ])
    return db


def test_find_products_partial_case_insensitive():
    db = _seed()
    out = data.find_products("미역", db=db)
    assert len(out) == 1
    assert out[0]["uid"] == "P1"
    assert out[0]["keyword"] == "쿡시 미역국"
    assert out[0]["source_counts"] == {"naver": 20}


def test_find_products_empty_query_returns_empty():
    db = _seed()
    assert data.find_products("", db=db) == []
    assert data.find_products("   ", db=db) == []


def test_find_products_no_keyword_match_returns_empty():
    db = _seed()
    # category_l1 에는 '식품' 이 있지만 keyword 매칭만 하므로 '식' 은 0건
    assert data.find_products("식", db=db) == []


def test_find_products_respects_limit():
    db = mongomock.MongoClient().db
    db.products.insert_many([
        {"_id": f"P{i}", "keyword": f"라면 {i}", "category_l1": "식품", "type": "single",
         "analyzed_count": i, "sources": {}} for i in range(5)
    ])
    out = data.find_products("라면", limit=2, db=db)
    assert len(out) == 2
    # analyzed_count 내림차순 → 가장 큰 두 개
    assert [p["uid"] for p in out] == ["P4", "P3"]


def test_get_product_returns_doc_or_none():
    db = _seed()
    assert data.get_product("P1", db=db)["keyword"] == "쿡시 미역국"
    assert data.get_product("nope", db=db) is None
