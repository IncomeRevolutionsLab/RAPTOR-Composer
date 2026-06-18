파일 저장 권한이 막혀있습니다. 리포트 내용은 아래에 직접 제시드립니다.

---

# Post-Review Report — v2.19.8 KIE Payload Sync & callBackUrl

**커밋:** `046d828` | **작성일:** 2026-06-16 | **프레임워크:** VIBE

---

## 전체 판정: 🟡 조건부 PASS

| 영역 | 판정 | 근거 |
|------|------|------|
| KIE 스펙 규격 부합 | ✅ PASS | 모델명 매핑, 레거시 파라미터 소거 유효 |
| 안정성 (generate-images) | ✅ PASS | 자체 폴링 루프로 callBackUrl 실패 시 fallback |
| callBackUrl 대칭성 | ⚠️ RISK P1 | `/api/refine-prompt` 누락 |
| callBackUrl 라우팅 | 🔴 RISK P1 | 웹훅 수신 서버 불일치 가능성 |
| 이월 Dead Code | 🟡 INFO | v2.19.7 지적 3건 미수정 |

---

## ✅ 정상 확인

**1. `map_image_model()` 정확성 (line 172–182)**  
`gpt-image-2-text-to-image` / `grok-imagine/text-to-image` / `nano-banana-2` 3종 모두 KIE 공식 스펙 정확 매핑. `None` 입력 시 `gpt-image-2-text-to-image` 기본값 반환 안전.

**2. 레거시 파라미터 완전 소거 (df7b2f3 반영)**  
`"aspect_ratio": "3:2"` (grok 하드코딩), `"aspect_ratio": "auto"` (gpt/banana 하드코딩) 두 건 모두 제거 확인. 422 원인 파라미터 소거 완료.

**3. `callBackUrl` 페이로드 구조 적합성 (line 1211–1215)**  
`model` / `callBackUrl` / `input` 최상위 키로 배치 → KIE `/jobs/createTask` 규격 부합.

**4. 폴링 루프 Fallback 안전망 (line 1234–1280)**  
`callBackUrl`이 실패하더라도 `while True: asyncio.sleep(3)` + `recordInfo` 폴링이 최대 180초 독립 작동. 이미지 생성은 callBackUrl 의존성 없음 ✅

**5. `nano-banana-2` 전용 파라미터 분기 (line 1198–1203)**  
`image_input: []`, `resolution: "1K"`, `output_format: "png"` 정확히 banana-2에만 적용.

---

## 🚨 신규 리스크

### [P1] callBackUrl 라우팅 불일치

**핵심 불일치:**
```
callBackUrl 송신 → https://raptor-composer.onrender.com/api/webhook/kie  (RAPTOR-Composer, Render)
웹훅 핸들러 위치 → /api/webhook/kie @ raptor/main.py                     (RAPTOR 백엔드, Koyeb)
```

`main.py` line 1756에 `/api/webhook/kie` 핸들러가 구현되어 있고, 이 핸들러가 `TASK_EVENTS.set()` (SSE 트리거, line 1804)와 Supabase `tasks` 테이블 업데이트(line 1794–1800)를 담당함. `callBackUrl`이 다른 서버(Render)를 가리키면 KIE 이벤트가 Koyeb의 핸들러에 도달하지 못해 이 두 동작이 무력화됨.

**기능 중단 여부:** 이미지 생성 자체는 폴링으로 완료 → 서비스 중단 없음. SSE 실시간 알림만 영향.

**확인 필요:** RAPTOR-Composer에 `/api/webhook/kie` 라우트 존재 여부 확인.  
없으면 → line 1213을 `os.getenv("KIE_CALLBACK_URL", "https://raptor-backend.koyeb.app/api/webhook/kie")` 로 수정.

---

### [P1] `/api/refine-prompt` callBackUrl 누락 (line 1619–1627)

이번 커밋은 `generate-images`에만 `callBackUrl`을 추가, `refine-prompt`는 동일하게 `createTask`를 호출하지만 누락:

```python
# generate-images (line 1211) — callBackUrl ✅
json={"model": model_val, "callBackUrl": "https://...", "input": input_payload}

# refine-prompt (line 1624) — callBackUrl ❌
json={"model": model_val, "input": input_payload}
```

기능 중단은 없으나 설계 비대칭. line 1624에 `callBackUrl` 동일하게 추가 필요.

---

### [P2] callBackUrl 하드코딩

`"https://raptor-composer.onrender.com/api/webhook/kie"` 문자열 직접 삽입. `generate_videos`(line 2010–2017)는 DB에서 동적 조회하는 패턴인데 이미지 생성만 하드코딩이어서 환경 분리 불가. → `os.getenv("KIE_WEBHOOK_CALLBACK_URL", "")` 로 환경변수화 권장.

---

## ⚠️ 이월 리스크 (v2.19.7 미수정)

| ID | 위치 | 내용 | 위험도 |
|----|------|------|--------|
| R-01 | line 1198 | `nano-banana-2` `"9:16"` 지원 미검증 → 422 재발 가능 | P2 |
| R-02 | line 1195, 1608 | `hasattr` 항상 True + `"auto"` fallback 절대 불달성 dead code | P3 |
| R-03 | line 1166, 1585 | `img_size` 변수 미사용 잔재 | P3 |

---

## 수정 우선순위

| 순위 | ID | 항목 |
|------|-----|------|
| 🔴 즉시 | NEW-01 | RAPTOR-Composer 웹훅 라우트 존재 여부 확인 후 callBackUrl URL 결정 |
| 🔴 즉시 | NEW-02 | `/api/refine-prompt` line 1624에 `callBackUrl` 추가 |
| 🟡 단기 | NEW-03 | callBackUrl 환경변수화 |
| 🟡 단기 | R-01 | banana-2 `"9:16"` 실서버 검증 |
| ⚪ 여유 | R-02, R-03 | Dead code 정리 |

---

**결론:** KIE 스펙 규격 부합과 이미지 생성 안정성은 확보됨. 가장 중요한 액션은 **RAPTOR-Composer에 `/api/webhook/kie` 라우트가 있는지 먼저 확인**하는 것이며, 없다면 `callBackUrl`을 Koyeb 백엔드 URL로 수정해야 SSE 파이프라인이 정상 작동합니다.
