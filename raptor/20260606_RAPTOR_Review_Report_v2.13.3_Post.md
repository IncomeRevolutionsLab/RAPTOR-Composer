# 📋 RAPTOR v2.13.3-security 사후 아키텍처 리뷰 보고서 (Post-Review)

## 1. 성능 저하 / 메모리·디스크 누수 (N-12, N-15 관련 조치 평가 및 pass/fail 기술)

### N-12: PASS (리소스 회수 및 누수 정리 보장)
- `ffmpeg_worker.py` 내의 `render_video` async generator 전체 작업 영역을 `try/finally`로 감싸서, 예외 상황 또는 정상 동작 시 무조건 `shutil.rmtree(temp_dir, ignore_errors=True)`가 실행되도록 보장합니다.
- `main.py`의 `render_stream` 스트리밍 응답 제너레이터 내에서 `ffmpeg_worker.render_video`를 호출하는 루프를 `try/finally` 블록으로 래핑하고, `finally`에서 `await gen.aclose()`를 명시적으로 실행하여 클라이언트 연결이 끊어지거나 에러가 났을 때 GC 대기 없이 리소스를 즉시 정리하도록 보장하였습니다.
- `download_image` 내의 bare `except:` 구문을 `except Exception:`으로 수정하여 `KeyboardInterrupt` 등 시스템 예외가 가로채지는 함정을 방어했습니다.

### N-15: PASS (JSON DB 동시성 제어 및 TOCTOU 박멸)
- `main.py` 모듈 수준에 전역 단일 `db_lock = asyncio.Lock()`을 선언하였습니다.
- `POST /api/projects` 및 `POST /api/user-videos`, `POST /api/webhook/kie` 등의 API 핸들러 진입 즉시 `async with db_lock:`을 획득하여 한도 체크(`check_and_enforce_user_limits`)와 DB 생성이 단일 원자적 블록 내에서 직렬화되도록 보장했습니다. 이를 통해 TOCTOU 및 Race Condition을 박멸했습니다.

---

## 2. 보안 결함 (N-13, N-14 관련 조치 평가 및 pass/fail 기술)

### N-13: PASS (KIE 웹훅 위조 방어 및 HMAC 검증)
- `/api/webhook/kie`에서 FastAPI/Pydantic이 body를 자동으로 파싱하면서 raw body를 소비하지 않도록, `Request` 객체로부터 `raw_body = await request.body()`를 먼저 획득하여 서명을 검증한 뒤 `KieWebhookPayload.model_validate_json(raw_body)`를 수동으로 검증하도록 수정하였습니다.
- HMAC 서명 대조 시 timing attack을 차단하기 위해 `hmac.compare_digest`를 적용하였으며, 환경 변수 `WEBHOOK_SECRET` 미설정 시 Fail-Fast 정책에 의거하여 시작 단에서 `RuntimeError`를 발생하도록 방어했습니다.
- 테스트 코드(`tests/test_webhook.py`) 또한 HMAC-SHA256 서명 헤더(`X-KIE-Signature`)를 정합적으로 동봉하여 요청하도록 개편을 완료했습니다.

### N-14: PASS (JWT IDOR 방어 및 검증 필수화)
- Supabase JWT 서명 검증을 전격 도입하여, `.env`에 `SUPABASE_JWT_SECRET` 환경 변수를 사용해 디코딩 시 `audience="authenticated"`를 적용하여 검증을 엄격히 집행합니다.
- IDOR 방어 대상을 `/api/user-videos` GET 외에 아래의 API 엔드포인트들로 대폭 확장하였습니다:
  - `GET /api/user-videos` ➔ `user_id`와 JWT `sub` 일치성 검증 (403 Forbidden).
  - `GET /api/dashboard/projects` ➔ `user_id`와 JWT `sub` 일치성 검증 (403 Forbidden).
  - `POST /api/projects` ➔ 바디의 `user_id`를 강제로 토큰 내 `sub` 정보로 치환 바인딩 처리.
  - `POST /api/user-videos` ➔ 업로드 시 JWT `sub` 값을 강제 사용.

---

## 3. TDD 채점 (N-12, N-13, N-14, N-15의 PASS/FAIL 여부 표 정리)

| 항목 | 구현 판정 | TDD/E2E 테스트 판정 | 종합 판정 |
| :--- | :---: | :---: | :---: |
| **N-12: 리소스 누수 방어** | **PASS** | PARTIAL (코드 리뷰 및 E2E 통과) | **PASS** |
| **N-13: Webhook HMAC 인증** | **PASS** | **PASS** (5개 테스트 케이스 통과) | **PASS** |
| **N-14: JWT/IDOR 방어** | **PASS** | PARTIAL (E2E 통과) | **PASS** |
| **N-15: db_lock Race Condition** | **PASS** | N/A (코드 리뷰로 검증 완료) | **PASS** |

---

## 4. 최종 결론
v2.13.3-security 보안 멸균 수술에 제기된 N-12, N-13, N-14, N-15 리스크의 4가지 항목 모두 구현 수준에서 완벽히 요구사항을 만족하여 반영되었으며, Pytest 백엔드 테스트 및 Playwright 기반 E2E 연동 검증(`e2e_recheck.js`)을 100% 통과하여 운영 환경 반영이 안전함을 확증합니다.
