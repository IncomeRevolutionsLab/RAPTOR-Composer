# 📋 RAPTOR v2.13.3-security 사전 아키텍처 리뷰 보고서 (Pre-Review)

- **리뷰 수행일:** 2026-06-06
- **대상 계획서:** `implementation_plan.md` (v2.13.3-security)
- **리뷰 툴:** Claude CLI (B모드 아키텍처/보안 사전 감사)

---

## 종합 평가 및 리스크 분석

| 결함 ID | 계획 타당성 | 사전 차단 필요 함정 | 우선도 |
|---------|------------|-------------------|--------|
| **N-12** | 방향 정확 | async generator `finally` 실행 보장 조건 누락 | 🔴 P0 |
| **N-13** | 방향 정확 | raw body 소비 순서, 헤더명 미확인, 시크릿 정책 미정의 | 🔴 P0 |
| **N-14** | 방향 정확 | `SUPABASE_JWT_SECRET` 환경변수 전략 누락, 동일 IDOR 3곳 미포함 | 🔴 P0 |
| **N-15** | 방향 정확 | TOCTOU 간극 미해소 (check + create 원자성 부재) | 🟡 P1 |

---

## 1. 🔴 N-12 — `ffmpeg_worker.py` temp_dir 누수 방어 설계

- **함정 1 — async generator에서 `finally` 즉시 실행 보장 조건:**  
  `render_video`는 `yield`를 사용하는 **async generator**입니다. 호출 측(`main.py`의 `render_stream`)에서 `async for` 루프 중 예외가 발생하거나 연결이 끊어질 때, generator가 `.aclose()` 없이 방치되어 `finally` 실행이 GC에 의존하지 않도록 `main.py` 내 호출 측에 명시적인 `aclose()` 처리를 보장해야 합니다.
  
  ```python
  # main.py render_stream 호출 측 대응 패턴
  gen = ffmpeg_worker.render_video(task_id, ...)
  try:
      async for chunk in gen:
          yield chunk
  finally:
      await gen.aclose()
  ```
- **함정 2 — `shutil` 및 `platform` import 최상단 이동:**  
  `ffmpeg_worker.py` 내부의 지역 import(`shutil`, `platform`)를 최상단 글로벌 영역으로 이동하여 `finally` 내 호출 크래시를 방지합니다.
- **추가 발견 — bare except 수정:**  
  `download_image` 함수(Line 84)의 `except:` 구문을 `except Exception:`으로 교체하여 `KeyboardInterrupt` 등 시스템 예외가 삼켜지지 않도록 합니다.

---

## 2. 🔴 N-13 — `/api/webhook/kie` HMAC-SHA256 서명 검증 설계

- **함정 1 — raw body 소비 경합 방지:**  
  FastAPI/Pydantic이 body를 자동 파싱(소비)하지 않도록, `Request` 객체로부터 raw bytes를 먼저 획득한 후 HMAC 서명을 검증하고, 수동으로 Pydantic 모델을 검증합니다.
  
  ```python
  @app.post("/api/webhook/kie")
  async def webhook_kie(request: Request):
      raw_body = await request.body()
      _verify_kie_hmac(request.headers, raw_body)
      payload = KieWebhookPayload.model_validate_json(raw_body)
  ```
- **함정 2 — `WEBHOOK_SECRET` 미설정 시 Fail-Fast:**  
  환경변수가 누락된 경우 서버 기동 단계 혹은 웹훅 수신 시 즉시 예외를 발생(Fail-Fast)시켜 보안 구멍을 사전에 차단합니다.
- **함정 3 — Timing Attack 방지:**  
  서명 비교 시 hmac 보안 강화를 위해 `hmac.compare_digest()` 함수를 필수 사용합니다.
- **테스트 코드 보완:**  
  `tests/test_webhook.py`의 테스트 코드들도 HMAC 서명을 생성하여 발송하도록 함께 개편해야 테스트 실패(401)를 방지할 수 있습니다.

---

## 3. 🔴 N-14 — `/api/user-videos` GET IDOR 방어 및 범위 확장

- **함정 1 — `SUPABASE_JWT_SECRET` 환경변수 적용:**  
  Supabase JWT 서명 검증을 위해 대시보드의 JWT Secret을 `.env`에 `SUPABASE_JWT_SECRET`로 설정하고 연동합니다.
- **함정 2 — IDOR 방어 범위 확장:**  
  `/api/user-videos` GET 외에, 동일한 취약점을 가진 다른 엔드포인트들도 함께 보완합니다:
  - `GET /api/dashboard/projects?user_id=...` ➔ JWT 토큰 `sub`와 user_id 일치성 확인.
  - `POST /api/projects` ➔ body의 `req.user_id`를 토큰의 `sub`로 오버라이드.
- **함정 3 — JWT `aud` 클레임 대응:**  
  Supabase JWT 규격에 맞게 `audience="authenticated"`를 PyJWT 디코더에 명시적으로 추가합니다.

---

## 4. 🟡 N-15 — `asyncio.Lock` JSON DB 동시성 제어 및 TOCTOU 박멸

- **함정 1 — TOCTOU 해결을 위한 락 범위 원자화:**  
  `check_and_enforce_user_limits`와 `create_project_in_db`가 연달아 실행되는 API 핸들러 레벨에서 단일 `async with db_lock:` 구조로 묶어 두 연산 사이의 경쟁 조건(TOCTOU) 간극을 차단합니다.
- **함정 2 — 단일 워커 전제 제약 명시:**  
  `asyncio.Lock`은 단일 프로세스 내에서만 유효하므로, 이 배포가 단일 워커(`--workers 1`) 환경 하에 있음을 배포 명세서 및 인프라 제약 사항에 명기합니다.
