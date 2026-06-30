"""인사이트 뷰모델 → 상세페이지 초안 (OpenAI gpt-4o-mini). 뷰모델만 투입(원문 미투입)."""
import json
from config import settings


class GenerateError(Exception):
    pass


_SYSTEM = (
    "너는 한국 이커머스 상세페이지 카피라이터다. 주어진 '상품 인사이트'(실제 리뷰에서 검증·집계된 "
    "강점·약점·타깃·정형사실·가격)만 근거로 상세페이지 초안을 쓴다. "
    "인사이트에 없는 사실은 절대 지어내지 않는다. 각 셀링포인트에는 근거가 된 출처(naver/youtube/danawa)를 "
    "sources 필드에 단다. 약점은 숨기지 말고 '선제 대응 FAQ'로 전환한다. "
    "titles 필드에는 반드시 정확히 3개의 후보 제목을 포함해야 한다. "
    "반드시 지정된 JSON 스키마로만 응답한다."
)

DRAFT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "listing_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["titles", "selling_points", "target_copy", "faqs", "spec_highlights", "price_positioning"],
            "properties": {
                "titles": {"type": "array", "items": {"type": "string"}},
                "selling_points": {
                    "type": "array",
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["text", "sources"],
                        "properties": {"text": {"type": "string"},
                                       "sources": {"type": "array", "items": {"type": "string"}}},
                    },
                },
                "target_copy": {"type": "string"},
                "faqs": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": False,
                              "required": ["q", "a"],
                              "properties": {"q": {"type": "string"}, "a": {"type": "string"}}},
                },
                "spec_highlights": {"type": "array", "items": {"type": "string"}},
                "price_positioning": {"type": "string"},
            },
        },
    },
}


def _summarize(view):
    """뷰모델을 프롬프트용 간결 텍스트로. evidence 원문은 짧게만."""
    lines = [f"상품명: {view.get('keyword')}", f"카테고리: {view.get('category_l1')}", f"타입: {view.get('type')}"]
    if view.get("strengths"):
        lines.append("강점(빈도순):")
        for s in view["strengths"]:
            src = ",".join(sorted({e["source"] for e in s.get("evidence") or [] if e.get("source")})) or "리뷰"
            lines.append(f"  - {s['point']} (근거 {s['n']}건, 출처 {src})")
    if view.get("weaknesses"):
        lines.append("약점(빈도순, FAQ로 선제대응):")
        for w in view["weaknesses"]:
            lines.append(f"  - {w['point']} (근거 {w['n']}건)")
    tgt = []
    for dim in ("who", "when", "where", "why"):
        for g in view.get("targets", {}).get(dim, []):
            for p in g["points"]:
                tgt.append(f"{g['label']}:{p['point']}")
    if tgt:
        lines.append("타깃/사용맥락: " + "; ".join(tgt))
    if view.get("gift"):
        lines.append("선물수요: " + "; ".join(p["point"] for p in view["gift"]))
    if view.get("specs"):
        facts = []
        for sp in view["specs"]:
            facts += [f"{k}={v}" for k, v in sp["facts"].items()]
        lines.append("정형 사실: " + ", ".join(facts))
    pr = view.get("price")
    if pr:
        lines.append(f"가격: 최저 {pr['min']}원({pr.get('low_mall')}), 중앙 {pr.get('median')}원, "
                     f"{pr.get('n_malls')}개몰, 가격차 {pr.get('spread_pct')}%")
    return "\n".join(lines)


def build_prompt(view):
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "다음 인사이트로 상세페이지 초안을 작성하라.\n\n" + _summarize(view)},
    ]


def _get_client(client):
    if client is not None:
        return client
    from openai import OpenAI
    return OpenAI(api_key=settings.openai_api_key)


def draft(view, client=None):
    """뷰모델 → 초안 dict. 파싱 실패 시 1회 재시도, 그래도 실패면 GenerateError."""
    client = _get_client(client)
    messages = build_prompt(view)
    last = None
    for _ in range(2):
        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                response_format=DRAFT_SCHEMA,
                temperature=0.5,
            )
            content = resp.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            last = e
    raise GenerateError(f"초안 생성 실패: {last}")
