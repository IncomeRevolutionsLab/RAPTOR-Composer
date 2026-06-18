# [Pre-Review] /api/projects 500 에러 및 datetime 가설 검증

**작성일**: 2026-06-19
**대상 기능**: `POST /api/projects` 및 사용자 한도 체크 로직 (`check_and_enforce_user_limits`, `create_project_in_db`)

---

## 1. 팩트 체크 (Fact Check): datetime.datetime.now() 가설 검증

**결론: 해당 가설(과거 N-01 결함)은 100% 허위(False)이며, 현재 500 에러의 원인이 아닙니다.**

`main.py` 코드를 정밀 스캔한 결과:
- 파일 상단 14번 라인에서 `from datetime import datetime, timedelta, date`로 올바르게 임포트되어 있습니다.
- `check_and_enforce_user_limits` (494번 라인) 및 `record_user_asset` (516번 라인) 내부를 포함하여 파일의 모든 영역에서 `datetime.now().isoformat()` 또는 `datetime.now().strftime(...)`으로 정확한 문법이 사용되고 있습니다.
- `datetime.datetime.now()`라는 잘못된 호출은 **단 한 곳도 존재하지 않습니다.** 따라서 문법 오류(AttributeError)로 인한 ASGI 크래시는 발생할 수 없습니다.

---

## 2. 진범 추적: /api/projects 500 에러의 진짜 원인

`/api/projects` 진입 시 발생하는 1초 컷 500 에러의 진짜 원인은 **할당량 초과(Quota Limit) 시 발생하는 파이썬 일반 예외(Exception)의 처리 미흡**입니다.

`/api/projects` 라우터는 내부적으로 `check_and_enforce_user_limits()`를 호출합니다. 이 함수는 한 달 10개 프로젝트 한도를 초과했을 때 아래와 같이 동작합니다:
```python
if monthly_count >= 10:
    raise Exception("무료 베타 테스트 기간 한도(10개)를 초과했습니다. 다음 달에 다시 이용해 주세요.")
```
FastAPI에서 정상적인 에러 메시지(400 Bad Request 또는 403 Forbidden)를 프론트엔드로 보내려면 `raise HTTPException(status_code=403, detail="...")` 형태를 사용해야 합니다. 
하지만 일반 `Exception`을 던져버렸기 때문에, FastAPI가 이를 서버의 치명적 크래시(버그)로 인식하고 `500 Internal Server Error (Exception in ASGI application)`를 뱉어내며 파이프라인을 끊어버리는 것이 명백한 진범입니다. (이로 인해 프론트엔드에서는 500 에러 또는 CORS 차단 에러로 나타나게 됩니다.)

---

## 3. 핫픽스 안정성 및 부작용 평가 (Side-effect Evaluation)

### ❌ datetime 교체 핫픽스 (기각)
- 기존 코드가 이미 정상적인 `datetime.now()`를 사용 중이므로, 이를 수정하는 것은 무의미하며 부작용을 일으킬 이유조차 없습니다.

### ✅ 진짜 핫픽스 제안: HTTPException 전환
**수정안**: `main.py`의 `check_and_enforce_user_limits` 및 `create_project_in_db` 함수 내부에 존재하는 `raise Exception("...")` 구문들을 찾아 모두 `raise HTTPException(status_code=403, detail="...")` (또는 400/500)으로 교체해야 합니다.

**평가**:
- **안정성 (High)**: FastAPI 표준 에러 처리 방식으로 전환하는 것이므로 매우 안전합니다.
- **부작용 (None)**: `async with db_lock:` 스코프 내부에서 에러가 발생해도 컨텍스트 매니저가 락을 정상적으로 해제하므로 데드락(Deadlock) 위험이 없습니다. 프론트엔드는 정상적인 JSON 형태의 에러 응답(`{ "detail": "무료 베타..." }`)을 수신하여 유저에게 깔끔한 알림창을 띄울 수 있게 됩니다.

---

## VIBE 최종 요약
- **Validity (타당성)**: 사용자 가설(datetime 오류)은 현재 코드베이스와 불일치함 (기각). 진짜 원인은 비표준 Exception throw임.
- **Impact (영향도)**: 10개 한도를 채운 헤비 유저들이 프로젝트 생성 시도를 할 때마다 서버가 500 에러를 뱉어 UX가 심각하게 훼손됨.
- **Behavior (동작)**: `Exception`을 `HTTPException`으로 교체하면 정상적인 403 거절 메시지로 부드럽게 처리됨.
- **Edge Cases (예외 케이스)**: `create_project_in_db`에서도 DB Insert 실패 시 `raise Exception`을 사용하고 있으므로 이 부분도 500 `HTTPException`으로 함께 잡아주어야 완벽함.
