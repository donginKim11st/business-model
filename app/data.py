"""Mongo insights_demo.products 읽기 전용 조회. business-model 비의존."""
import re
from pymongo import MongoClient
from config import settings

_client = None


def get_db():
    """런타임용 Mongo DB 핸들(싱글톤)."""
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri)
    return _client[settings.insights_db]


def _shape(doc):
    return {
        "uid": doc.get("_id"),
        "keyword": doc.get("keyword") or "",
        "category_l1": doc.get("category_l1"),
        "type": doc.get("type") or "",
        "analyzed_count": doc.get("analyzed_count") or 0,
        "source_counts": doc.get("sources") or {},
    }


def find_products(q, limit=30, db=None):
    """keyword 부분일치(대소문자 무시) 검색. q 비면 빈 리스트."""
    q = (q or "").strip()
    if not q:
        return []
    db = db if db is not None else get_db()
    rx = re.compile(re.escape(q), re.IGNORECASE)
    cur = db.products.find(
        {"keyword": rx},
        {"keyword": 1, "category_l1": 1, "type": 1, "analyzed_count": 1, "sources": 1},
    ).sort("analyzed_count", -1).limit(limit)
    return [_shape(d) for d in cur]


def get_product(uid, db=None):
    """_id=uid 단일 도큐먼트 원본 반환(없으면 None)."""
    db = db if db is not None else get_db()
    return db.products.find_one({"_id": uid})
