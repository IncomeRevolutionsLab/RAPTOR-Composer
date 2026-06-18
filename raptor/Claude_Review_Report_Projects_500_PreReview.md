# [VIBE Pre-Review] Exception → HTTPException 핫픽스 타당성 검증

**검증일**: 2026-06-19
**검증 대상**: `20260619_RAPTOR_Review_Report_Projects_500_PreReview.md`
**검증 범위**: `main.py` — `check_and_enforce_user_limits` (L492), `create_project_in_db` (L399), `POST /api/projects` (L590)

---

## V — Validity (타당성 검증)

### ① datetime 가설 기각: ✅ 완전 정확

`main.py` L15 직접 확인:
```python
from datetime import datetime, timedelta, date
```
`datetime.datetime.now()` 형태는 전체 파일에서 **단 한 건도 존재하지 않음**. 기각 근거가 코드베이스 사실과 100% 일치합니다.

### ② 진짜 원인 진단: ✅ 완전 정확

`check_and_enforce_user_limits` L502 직접 확인:
```python
if monthly_count >= 10:
    raise Exception("베타 테스트 월간 프로젝트 생성 한도(10개)를 초과했습니다. 다음 달에 다시 이용해 주세요.")
```

`POST /api/projects` 핸들러 L590-596:
```python
@app.post("/api/projects", status_code=201)
async def create_project(req: ProjectCreateRequest, jwt_user_id: str = Depends(get_jwt_user_id)):
    req.user_id = jwt_user_id
    sanitized_user = sanitize_uuid(req.user_id)
    async with db_lock:
        await check_and_enforce_user_limits(sanitized_user)
        return await create_project_in_db(req.product_name, sanitized_user)
```

라우터에 `try/except` 없음. `Exception`이 FastAPI의 기본 `ServerErrorMiddleware`로 전달되어 **500 반환이 구조적으로 확정**됩니다. 진단 정확합니다.

### ③ 수정 제안: ✅ FastAPI 표준 패턴

`HTTPException`은 FastAPI의 `exception_handlers` 계층에서 `RequestValidationError`와 함께 우선 처리되어 정상적인 JSON 응답을 반환합니다. `Exception`과 달리 500 경로를 우회하는 표준 방식입니다.

---

## I — Impact (영향도 검증)

**직접 영향 경로** (코드 추적 완료):
```
POST /api/projects
  └→ check_and_enforce_user_limits()   [L502: raise Exception → 500]
  └→ create_project_in_db()            [L412: raise Exception → 500]
```

| 시나리오 | 현재 동작 | 핫픽스 후 |
|---|---|---|
| 월 10개 한도 초과 유저가 프로젝트 생성 시도 | 500 Internal Server Error + ASGI traceback | 403 Forbidden + `{"detail": "베타 테스트..."}` |
| Supabase DB Insert 실패 | 500 (bare Exception) | 500 HTTPException (동일하지만 JSON 포맷, CORS 안전) |

**영향 범위**: `/api/projects` POST 엔드포인트 단독. 다른 엔드포인트 영향 없음.

**영향 심각도**: `High` — 10개 한도에 도달한 헤비 유저는 이후 모든 프로젝트 생성 시도에서 500을 받으며, 프론트엔드 CORS 레이어가 500을 네트워크 오류로 처리할 경우 에러 메시지조차 표시되지 않습니다.

---

## B — Behavior (동작 변화 검증)

### db_lock 안전성: ✅ 데드락 위험 없음

`async with db_lock:` 구문은 Python `asyncio.Lock()`의 비동기 컨텍스트 매니저입니다. `HTTPException`이 발생하면 `__aexit__`가 예외 전파 전에 반드시 호출되어 락이 해제됩니다. `Exception`도 동일하므로 기존 대비 락 해제 동작에 차이가 없습니다.

### CORS 안전성: ✅ 정상 응답

현재 `Exception` → 500 경로에서 ASGI 레벨 에러가 발생할 경우 CORS 응답 헤더 누락으로 프론트엔드에서 **CORS 에러로 오인**될 수 있습니다. `HTTPException` 전환 시 FastAPI의 CORS 미들웨어가 에러 응답에도 정상적으로 `Access-Control-Allow-Origin` 헤더를 부착합니다.

### 상태 코드 적합성:

| 위치 | 현재 | 권장 | 근거 |
|---|---|---|---|
| L502 (월 한도 초과) | `Exception` → 500 | `HTTPException(403)` | 서버 결함이 아닌 비즈니스 규칙 거절 |
| L412 (DB Insert 실패) | `Exception` → 500 | `HTTPException(500)` | 실제 서버 오류이므로 500 유지, 단 JSON 포맷화 |

---

## E — Edge Cases (예외 케이스 검증)

### Edge Case 1: create_project_in_db L412 누락 (보고서 지적 정확) ✅

보고서가 L412도 함께 교체해야 완벽하다고 명시했고, 코드 확인 결과 `raise Exception("Failed to insert project into Supabase database")`가 실존합니다. **이번 핫픽스에 반드시 포함되어야 합니다.**

### Edge Case 2: 월간 카운팅 타임존 경계 (보고서 미언급, 신규 발견) ⚠️

```python
current_month = datetime.now().strftime("%Y-%m")
monthly_count = len([p for p in user_projects if p.get("created_at", "").startswith(current_month)])
```

`datetime.now()`는 타임존 정보 없는 로컬 시간입니다. 호스팅 서버가 **UTC**로 동작할 경우, KST 기준 월말(예: 6월 30일 22:00 KST)에 서버는 이미 7월로 인식하여 한도 카운터가 초기화됩니다. 이는 이번 핫픽스 범위를 벗어나므로 별도 이슈로 추적을 권장합니다.

### Edge Case 3: 동시 요청 경합 조건 (안전 확인) ✅

`db_lock`이 단일 인스턴스 내 `asyncio.Lock()`이면, 동시 프로젝트 생성 요청은 직렬화됩니다. `HTTPException` 전환이 이 동작에 영향을 주지 않습니다.

---

## VIBE 종합 판정

| 항목 | 보고서 주장 | 코드 검증 결과 | 판정 |
|---|---|---|---|
| datetime 가설 기각 | 100% 허위 | L15 import 확인, 잘못된 호출 0건 | ✅ 정확 |
| 500 에러 진원 | L502 bare Exception | L502 + L590-596 구조 확인 | ✅ 정확 |
| HTTPException 전환 안전성 | 부작용 없음 | db_lock 컨텍스트 매니저 정상 해제 확인 | ✅ 정확 |
| L412 병행 교체 필요 | 명시함 | L412 실존 확인 | ✅ 정확 |
| 타임존 경계 케이스 | 미언급 | datetime.now() 타임존 없음 확인 | ⚠️ 신규 발견 |

**최종 판정: 핫픽스 승인 (APPROVED)**

보고서의 진단과 수정 방향 모두 코드베이스 사실과 정확히 일치합니다. 수정 대상은 **L502 (403)** 및 **L412 (500)** 두 곳이며, 이 두 `raise Exception`을 `raise HTTPException`으로 교체하는 것이 이번 핫픽스의 전체 범위입니다.
