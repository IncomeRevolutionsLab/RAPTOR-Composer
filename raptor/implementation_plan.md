# [Goal Description]
Koyeb 백엔드의 결제 락(Billing Lock)으로 인한 인프라 중단 사태를 즉각 수습하기 위해, 랩터 백엔드 호스팅 서비스를 Render.com으로 긴급 이관하고 Vercel의 백엔드 연결 엔드포인트를 갱신합니다.

## User Review Required
> [!IMPORTANT]
> **Render.com 이관 및 배포 필수 체크 사항:**
> 1. **포트 동적 바인딩:** Render.com은 기본 10000 포트 혹은 동적 `$PORT` 환경변수로 포트를 할당하므로, 실행 명령어(Start Command)에 반드시 `--port $PORT` 매핑을 적용해야 합니다.
> 2. **단일 워커 프로세스 유지:** TOCTOU 경쟁 조건 방지를 위한 `db_lock asyncio.Lock()`이 싱글 인스턴스 내에서 올바르게 동기화되도록 `--workers 1` 옵션을 강제 고수합니다.
> 3. **필수 환경변수 7종 수동 주입:** Supabase DB 연결용 키 및 JWT 검증용 비밀키, ALLOWED_ORIGINS 새 도메인이 정확히 기입되어야 합니다.

## Open Questions
- Render.com의 무료 플랜(Free Instance)은 약 15분간 요청이 없을 시 인스턴스가 잠들고(Spin-down), 첫 요청 시 콜드 스타트(약 50초 지연)가 발생할 수 있습니다. 런칭 환경의 상용성을 높이기 위해 최소 Web/Starter 플랜($7/mo)으로 생성할 것을 권장합니다.

---

## Proposed Changes

### 백엔드 인프라 (Render.com)
- **배포 방식:** Dockerfile을 사용한 Web Service 빌드 (또는 Python native 빌드)
- **Build Command:** `pip install -r requirements.txt` (Python native 배포 시)
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`

### 프론트엔드 (Vercel)
- **NEXT_PUBLIC_BACKEND_URL 갱신:** 기획자가 Render 배포 완료 후 제공하는 `https://raptor-backend.onrender.com` 주소로 프론트엔드 환경변수를 갱신합니다.
- **[MODIFY] [vercel.json](file:///c:/Antigravity%20Work/RAPTOR/vercel.json)**
  - 프록시 destination 주소를 `https://raptor-backend.koyeb.app` ➔ `https://raptor-backend.onrender.com` (혹은 지정된 Render 주소)로 수정합니다.

---

## Verification Plan

### Manual Verification
1. **Render.com 배포 완료 확인:**
   - 기획자가 Render에 배포한 인스턴스의 헬스체크 주소 `/api/auth/csrf-token` 로 직접 GET 통신을 시도하여 `200 OK`가 잘 떨어지는지 검증합니다.
2. **CORS 응답 검증:**
   - `Origin` 헤더에 `https://raptor-composer.vercel.app`을 실어 헬스체크를 보낸 뒤, `Access-Control-Allow-Origin`이 허용되는지 확인합니다.
3. **Vercel 재배포 및 회원가입 E2E 연동 테스트:**
   - 수동 배포 완료된 Vercel 도메인으로 들어가 실제 회원가입 및 로그인이 정상적으로 처리되는지 눈으로 최종 확증합니다.
