# 상품 사진 추천 → 클릭 반영 (네이버 이미지 검색)

## 목적
셀러가 슬롯별로 상품 사진을 직접 업로드하는 대신, 상품명으로 네이버 이미지 검색 결과를
추천받아 썸네일을 클릭하면 해당 슬롯에 반영한다.

## 결정 사항
- **출처**: 웹 이미지 검색 (네이버 이미지 검색 API).
- **추천 단위**: 슬롯별 [추천] 버튼 (히어로/디테일/사용씬/보조 각각).
- **쿼리**: v1은 슬롯 공통으로 상품명(`view.keyword`) 검색.
- **저작권**: 추천 그리드에 "타인 저작권/상업이용 주의 — 책임은 셀러" 고지.

## 흐름
```
슬롯 [추천] 클릭
 → GET /product/{uid}/photo-suggest?slot=hero    상품명으로 네이버 이미지검색
 → 썸네일 6~9장 그리드 (네이버 thumbnail 직접 <img>)
 → 썸네일 클릭
 → POST /product/{uid}/photo-fetch {url}          원본 fetch·검증 → data URI
 → 슬롯에 '선택됨' 미리보기 반영 (JS 상태 chosen[slot]=dataURI)
 → 기존 "이미지로 내보내기"가 그대로 전송 (dataURI→Blob 으로 슬롯 FormData 에 부착)
```

## 구성요소
| 파일 | 역할 |
|---|---|
| `app/photo_search.py` (신규) | `search(query, n)→[{thumbnail, link}]`; `fetch_as_data_uri(url)`(SSRF 방어·image 검증·8MB 제한) |
| `config.py` | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| `app/main.py` | `GET .../photo-suggest?slot=`, `POST .../photo-fetch` |
| `app/templates/_draft.html`, `app/static/app.js`, `app/static/app.css` | 슬롯별 [추천]·썸네일 그리드·클릭 반영·미리보기 |

## 핵심 설계
- **기존 `/detail-image` 무변경**: 클릭 시 받은 data URI 를 Blob 으로 만들어 슬롯 FormData 에 부착 → 업로드 파일과 동일 경로.
- **키 미설정**: `PhotoSearchError("네이버 API 키가 설정되지 않았습니다...")` → 라우트가 명확 메시지 반환(OpenAI 패턴 동일).
- **SSRF 방어** (`fetch_as_data_uri`): https 스킴만, 호스트 DNS 해석 후 사설/루프백/링크로컬 IP 차단, content-type `image/*` 강제, 8MB 상한, 리다이렉트 최소·타임아웃.

## 에러 처리
| 상황 | 응답 |
|---|---|
| 네이버 키 없음 | 400/500 + "네이버 API 키가 설정되지 않았습니다" |
| 네이버 호출 실패 | 502 + 사유 |
| fetch 대상이 이미지 아님/과대/사설IP | 400 + 사유, 반영 안 함 |
| 상품 없음 | 404 |

## 테스트 (TDD, 네이버 API·httpx 모킹)
- `photo_search.search`: 네이버 응답 파싱 → thumbnail/link 리스트, display 파라미터.
- 키 미설정 → `PhotoSearchError` 명확 메시지.
- `fetch_as_data_uri`: 정상 이미지→data URI; 비이미지/8MB 초과/사설IP·loopback URL → 거부.
- 라우트: `photo-suggest` JSON 반환; `photo-fetch` data URI; 상품없음 404; 키없음 에러.

## 비목표 (YAGNI)
- 슬롯별 쿼리 튜닝, 이미지 캐싱/저장, 결과 페이징, 라이선스 자동판별.
