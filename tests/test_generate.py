import json
import os
import pytest
from app import generate


SAMPLE_VIEW = {
    "keyword": "쿡시 미역국", "category_l1": "식품", "type": "package",
    "strengths": [{"point": "간편 조리", "n": 5, "evidence": [{"source": "naver", "url": "http://a", "quote": "쉽다"}]}],
    "weaknesses": [{"point": "면이 분다", "n": 3, "evidence": []}],
    "targets": {"who": [{"label": "가구", "points": [{"point": "부모님과", "n": 2, "evidence": []}]}], "when": [], "where": [], "why": []},
    "gift": [], "specs": [{"ctlg_no": "1", "disp": "12개", "facts": {"origin": "대한민국"}}],
    "price": {"min": 9900, "low_mall": "쿠팡", "n_malls": 4, "spread_pct": 12, "median": 11000},
}

VALID_DRAFT = {
    "titles": ["t1", "t2", "t3"],
    "selling_points": [{"text": "간편하게 조리", "sources": ["naver"]}],
    "target_copy": "부모님과 함께 드세요",
    "faqs": [{"q": "면이 붇나요?", "a": "조리 시간을 지키세요"}],
    "spec_highlights": ["원산지 대한민국"],
    "price_positioning": "쿠팡 최저 9900원",
}


class _FakeResp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


class _FakeClient:
    """chat.completions.create 모킹. 미리 준 content 들을 순서대로 반환."""
    def __init__(self, contents):
        self._contents = list(contents)
        self.calls = []
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResp(self._contents.pop(0))


def test_build_prompt_includes_rule_and_view():
    msgs = generate.build_prompt(SAMPLE_VIEW)
    assert msgs[0]["role"] == "system"
    assert "없는 사실" in msgs[0]["content"]            # 환각 금지 규칙
    assert "간편 조리" in msgs[1]["content"]            # 뷰모델 강점 투입


def test_draft_parses_valid_json():
    client = _FakeClient([json.dumps(VALID_DRAFT, ensure_ascii=False)])
    out = generate.draft(SAMPLE_VIEW, client=client)
    assert out["titles"] == ["t1", "t2", "t3"]
    assert out["selling_points"][0]["sources"] == ["naver"]
    assert client.calls[0]["model"] == "gpt-4o-mini"


def test_draft_retries_once_on_bad_json_then_succeeds():
    client = _FakeClient(["not json{", json.dumps(VALID_DRAFT, ensure_ascii=False)])
    out = generate.draft(SAMPLE_VIEW, client=client)
    assert out["target_copy"] == "부모님과 함께 드세요"
    assert len(client.calls) == 2                        # 재시도 발생


def test_draft_raises_after_two_failures():
    client = _FakeClient(["bad1", "bad2"])
    with pytest.raises(generate.GenerateError):
        generate.draft(SAMPLE_VIEW, client=client)


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY 없음")
def test_draft_live_smoke():
    out = generate.draft(SAMPLE_VIEW)
    assert len(out["titles"]) == 3
    assert isinstance(out["selling_points"], list)
