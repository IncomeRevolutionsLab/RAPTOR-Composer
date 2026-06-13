# 📋 RAPTOR v2.14.0 (M4-Cloud) 사전 아키텍처 리뷰 보고서 (Pre-Review)

- **리뷰 수행일:** 2026-06-06
- **검토 대상:** `main.py`, `backend/Dockerfile`, `vercel.json`, `backend/services/ffmpeg_worker.py`, `backend/services/kie_ai_client.py`
- **리뷰 기준 버전:** v2.14.0-M4 Cloud 배포

---

## 종합 평가 및 리스크 분석

| 결함 ID | 결함 영역 | 심각도 | 배포 차단 여부 |
| :--- | :--- | :---: | :---: |
| **P-001** | 성능/디스크 (NameError) | CRITICAL | **YES** |
| **S-001** | 보안/RLS (회원가입 불가) | CRITICAL | **YES** |
| **S-002** | 보안/RLS (격리 붕괴) | CRITICAL | **YES** |
| **S-003** | 보안/RLS (인증 우회) | CRITICAL | **YES** |
| **A-001** | 비동기 통신 (웹훅 단절) | CRITICAL | **YES** |
| **A-002** | 비동기 통신 (SSE 브릿지 부재) | CRITICAL | **YES** |
| **S-005** | 보안/RLS (CORS 오류) | HIGH | **YES** |

---

## 1. 성능 및 디스크 누수 (Performance / Disk Leak)

### 🛠️ [CRITICAL] P-001: `TASKS_DB_PATH` 미정의 변수 참조 — 런타임 `NameError`
- **위치:** `main.py:1750`, `main.py:1884`
- **리스크 내용:** `render-stream-test`와 `render-stream` 두 엔드포인트의 `process_scene_inner` 내부에서 `TASKS_DB_PATH`를 참조하지만, 이 변수는 `main.py` 어디에도 정의되어 있지 않습니다. Supabase 전환 이후 파일 기반 DB 경로 변수가 제거됐으나 참조 코드가 남아있는 레거시 잔재입니다. 프로덕션 배포 즉시 해당 씬을 처음 처리할 때 `NameError`가 발생하며 SSE 스트림이 종료됩니다.
- **수정 방향:** 해당 블록(lines 1749–1772, 1883–1906)을 Supabase 조회 로직으로 교체하거나, RISK-B 가드를 별도 함수로 리팩토링합니다.

### 🛠️ [HIGH] P-002: Supabase Storage `assets` 버킷 임시 이미지 누수
- **위치:** `main.py:1175`, `main.py:1958-1968`
- **리스크 내용:** `generate_videos`와 `render_stream` 양쪽에서 씬별로 `raptor_{timestamp}_{id(scene)}.png` 파일을 Supabase `assets` 버킷에 업로드하지만, KIE AI 영상 생성 완료 후 해당 임시 이미지를 삭제하는 코드가 없습니다. 사용자가 8-씬 영상을 생성할 때마다 버킷에 8개의 이미지가 영구 축적됩니다. FIFO 정리 로직도 Supabase Storage 오브젝트는 건드리지 않습니다.
- **수정 방향:** KIE 폴링 성공/실패 후 `supabase.storage.from_("assets").remove([file_name])` 호출을 추가하거나, Storage 버킷에 TTL 수명주기 정책을 적용합니다.

### 🛠️ [HIGH] P-003: `grok_debug.log` 무한 append — 디스크 소모
- **위치:** `main.py:1235-1236`
- **리스크 내용:** 매 비디오 생성 요청마다 로그가 누적됩니다. Koyeb 무료 플랜의 ephemeral disk 한도(수백 MB)에서 고빈도 사용 시 컨테이너가 SIGKILL될 수 있습니다. 로그 rotation이 전혀 없습니다.
- **수정 방향:** Python `logging.handlers.RotatingFileHandler`를 적용하거나, 해당 파일 로그를 `stdout`으로 전환합니다.

### 🛠️ [MEDIUM] P-004: FFmpeg 동기 subprocess가 asyncio event loop 블로킹
- **위치:** `ffmpeg_worker.py:160-375`, `Dockerfile:33`
- **리스크 내용:** `Dockerfile`은 `--workers 1` 단일 uvicorn 프로세스를 강제합니다(TOCTOU Lock 보장 목적). 그러나 `render_stream` 내부에서 `asyncio.create_task`로 씬별 병렬 처리를 수행하고, 최종적으로 `ffmpeg_worker.render_video`에서 `subprocess.run(cmd_scene, ...)`를 호출합니다. `subprocess.run`은 동기 블로킹 호출이므로 단일 이벤트 루프를 점유합니다. 8-씬 렌더링 시 실질적으로 순차 실행이 되며, 다른 API 요청이 렌더링 완료까지 응답을 받지 못합니다.
- **수정 방향:** FFmpeg subprocess 호출을 `await asyncio.get_event_loop().run_in_executor(None, subprocess.run, ...)` 패턴으로 감싸거나, Koyeb 분리 Worker로 완전히 오프로딩합니다.

### 🛠️ [MEDIUM] P-005: `ffprobe` PATH 의존성 — Linux 컨테이너 크래시
- **위치:** `ffmpeg_worker.py:186-189`
- **리스크 내용:** `imageio_ffmpeg`은 `ffmpeg` 바이너리 경로만 관리하고 `ffprobe`는 별도 관리하지 않습니다. `Dockerfile`에 `ffmpeg` 패키지가 설치되어 있어 `ffprobe`가 PATH에 있긴 하지만, CWD에 `ffprobe.exe`가 없을 때 `"ffprobe"` 문자열에 의존하는 로직은 불명확합니다. Windows 개발 환경과 Linux 컨테이너 간 동작 불일치 리스크가 있습니다.
- **수정 방향:** `imageio_ffmpeg.get_ffmpeg_exe()`처럼 `ffprobe` 경로도 명시적으로 확인하거나, `self.ffprobe_path = shutil.which("ffprobe")`로 안전하게 초기화합니다.

### 🛠️ [MEDIUM] P-006: FIFO 한도 불일치 — `check_and_enforce_user_limits` vs. `webhook_kie`
- **위치:** `main.py:379-413` (한도 10), `main.py:1618` (한도 50)
- **리스크 내용:** `check_and_enforce_user_limits`는 사용자당 프로젝트 최대 10개를 강제하고, `webhook_kie`는 50개 초과 시 정리합니다. 동일한 FIFO 정책이 두 곳에 다른 임계값으로 구현되어 있어 실제 저장 한도가 어디서 적용되는지 불명확하며, 향후 값 변경 시 양쪽을 동기화해야 하는 유지보수 리스크가 있습니다.

---

## 2. Supabase 연동 보안 및 RLS 설계 결함

### 🛠️ [CRITICAL] S-001: 회원가입이 Admin API(`/auth/v1/admin/users`)를 `anon` key로 호출
- **위치:** `main.py:540-566`
- **리스크 내용:** `/auth/v1/admin/users`는 Supabase `service_role` key가 필요한 관리자 전용 엔드포인트입니다. `anon` key로는 401 Unauthorized가 반환되므로 현재 회원가입 기능은 **실제로 작동하지 않습니다.** `service_role` key를 사용해야 한다면 해당 key가 클라이언트에 절대 노출되어서는 안 되며, 백엔드 서버에만 환경변수로 격리 보관이 필수적입니다.
- **수정 방향:** 일반 회원가입의 경우 `/auth/v1/signup` (anon key OK), 관리자 계정 생성의 경우 `service_role` key를 별도 환경변수(`SUPABASE_SERVICE_ROLE_KEY`)로 격리하여 사용합니다.

### 🛠️ [CRITICAL] S-002: `sanitize_uuid` fallback 하드코드 — 데이터 격리 완전 붕괴
- **위치:** `main.py:183-187`
- **리스크 내용:** UUID 형식이 아닌 모든 `user_id` (예: `"beta_tester"`, 공백, 임의 문자열 등)가 단일 하드코드 UUID로 매핑됩니다. 이 fallback UUID로 생성된 모든 프로젝트/태스크가 같은 사용자의 데이터로 집계되어 FIFO 삭제가 다른 사용자 데이터를 지울 수 있습니다. 프로덕션 멀티 유저 환경에서 사용자 간 데이터 오염이 발생합니다.
- **수정 방향:** 비정규 UUID 입력 시 fallback 반환 대신 `HTTPException(400)` 또는 `ValueError`를 발생시켜 호출 스택에서 명시적으로 처리하도록 변경합니다.

### 🛠️ [CRITICAL] S-003: 핵심 엔드포인트 인증 누락
- **위치:** `main.py:487-496`, `main.py:1536-1566`, `main.py:1636`
- **리스크 내용:** 아래 세 엔드포인트는 JWT 검증이나 CSRF 검증 없이 외부에서 임의 호출이 가능합니다:
  - `POST /api/projects/{id}/tasks`: JWT 없음. 임의 project_id에 태스크 삽입 가능.
  - `PATCH /api/tasks/{task_id}`: JWT 없음. 임의 task 상태를 `success`로 위변조 가능.
  - `POST /api/render-task`: JWT/CSRF 없음. `user_id = sanitize_uuid("beta_tester")` 하드코드.
  - `GET /api/archive`: JWT 없음. `user_id` 쿼리 파라미터만으로 타인 데이터 열람 가능.
- **수정 방향:** 모든 쓰기/조회 엔드포인트에 `jwt_user_id: str = Depends(get_jwt_user_id)` 의존성을 필수로 적용합니다.

### 🛠️ [HIGH] S-004: `anon` key로 Supabase DB 직접 조작 — RLS 우회 가능성
- **위치:** `main.py:178-180`, `main.py:344-377`
- **리스크 내용:** 백엔드 서비스가 `anon` key로 Supabase Python SDK를 통해 `projects`, `tasks`, `user_video_assets` 테이블을 직접 조작합니다. Supabase RLS가 활성화되어 있지 않으면 anon key로 모든 행을 읽고 쓸 수 있습니다. RLS가 활성화되어 있다면 백엔드의 SDK 쿼리는 `auth.uid()` 컨텍스트 없이 실행되므로 모든 RLS 정책이 실패(데이터 반환 없음)합니다.
- **수정 방향:** 
  - DB 서비스 오퍼레이션 전용으로 `SUPABASE_SERVICE_ROLE_KEY` 환경변수를 추가하고, 해당 키로 SDK 클라이언트를 초기화합니다.
  - 또는 JWT를 SDK에 주입하여 RLS를 올바르게 통과하도록 설계합니다: `supabase.postgrest.auth(jwt_token)`.

### 🛠️ [HIGH] S-005: CORS `allow_origins`가 `localhost`만 허용 — 클라우드 배포 즉시 기능 불능
- **위치:** `main.py:116-122`
- **리스크 내용:** `vercel.json`의 rewrite로 Vercel 프론트엔드가 Koyeb 백엔드로 API 요청을 프록시하더라도, 브라우저에서 직접 백엔드를 호출하는 경우(예: SSE 스트리밍) CORS 오류가 발생합니다. Vercel 배포 도메인(`*.vercel.app`)이 허용 목록에 없습니다.
- **수정 방향:** 환경변수 `ALLOWED_ORIGINS`로 허용 도메인을 동적으로 주입하고, `IS_PROD` 분기로 적용합니다.

### 🛠️ [MEDIUM] S-006: Supabase Storage `assets` 버킷 퍼블릭 접근 — 미생성 콘텐츠 유출
- **위치:** `main.py:1181`, `main.py:1968`
- **리스크 내용:** 생성된 상품 이미지가 `public/assets/` URL로 전 세계에 공개됩니다. 사용자가 의도하지 않은 상품 이미지가 크롤러나 제3자에게 노출될 수 있으며, 서버 측에서 URL을 알면 다른 사용자의 이미지도 접근 가능합니다.
- **수정 방향:** `assets` 버킷을 private으로 전환하고, 서명된 URL(`create_signed_url`)을 TTL 제한 하에 발급하거나, Supabase RLS Storage Policy로 업로더만 접근 가능하도록 설정합니다.

---

## 3. 렌더링 서버 분리에 따른 비동기 통신 규격

### 🛠️ [CRITICAL] A-001: `callback_url`이 `RenderTaskRequest`에 존재하지만 실제로 미사용
- **위치:** `main.py:229-234`, `main.py:1536-1566`
- **리스크 내용:** 비동기 렌더링 아키텍처의 핵심인 `callback_url`이 수신만 되고 실제로 사용되지 않습니다. 렌더링 Worker가 완료 후 콜백을 보낼 대상을 모르기 때문에 `/api/webhook/kie`가 실제로는 절대 호출되지 않고, 비동기 파이프라인이 사실상 단절된 상태입니다.
- **수정 방향:** `render_task` 엔드포인트에서 KIE AI `createTask` 호출 시 `callback_url`을 페이로드에 포함(`"webhook_url": request.callback_url` 또는 동등한 필드)하거나, 내부 Worker 큐에 `callback_url`과 함께 작업을 등록하는 브릿지 로직을 구현합니다.

### 🛠️ [CRITICAL] A-002: 웹훅 수신(`/api/webhook/kie`)과 SSE 스트림 간 브릿지 미존재
- **위치:** `main.py:1568-1634`, `main.py:1851-2150`
- **리스크 내용:** `render_stream` 엔드포인트는 KIE AI에 영상 생성 요청 후 5초 간격으로 직접 폴링합니다. 반면 `/api/webhook/kie`는 KIE AI로부터 완료 콜백을 받아 Supabase만 업데이트합니다. 이 두 흐름이 연결되어 있지 않아, 폴링 방식은 SSE 클라이언트가 연결된 동안에만 동작하여 연결 끊김 시 상태가 유실되며, 웹훅 방식은 DB는 업데이트되나 SSE 클라이언트로 상태가 전달되지 않는 불일치가 존재합니다.
- **수정 방향:** `asyncio.Queue` 또는 Redis pub/sub 기반으로 웹훅 수신 → SSE 브로드캐스트 파이프라인을 구성합니다. (폴링과 웹훅 중 하나로 통일).

### 🛠️ [HIGH] A-003: 웹훅 서명 검증 — `"sha256="` 프리픽스 미처리
- **위치:** `main.py:1582-1589`
- **리스크 내용:** KIE AI가 GitHub/Stripe 관례를 따라 `X-KIE-Signature: sha256=<hexdigest>` 형식으로 서명을 전송할 경우, `signature`에 `"sha256="` 프리픽스가 포함되어 비교가 항상 실패합니다. 실제 KIE AI 웹훅 서명 포맷을 확인하고 프리픽스 처리 코드를 추가해야 합니다.
- **수정 방향:**
  ```python
  if signature.startswith("sha256="):
      signature = signature[7:]
  ```

### 🛠️ [HIGH] A-004: `render_stream` 내 KIE 폴링이 Vercel 함수 타임아웃을 초과
- **위치:** `vercel.json`, `main.py:1256-1268`
- **리스크 내용:** 현재 `vercel.json`에서 `/api/*`를 Koyeb으로 rewrite하므로 `render_stream` 호출은 Vercel 엣지를 통과합니다. Vercel의 SSE/streaming 최대 허용 시간은 Pro 플랜 기준 300초(5분)입니다. Grok 폴링 타임아웃 720초는 이를 크게 초과하므로 클라이언트가 Vercel 레이어에서 연결이 끊길 수 있습니다.
- **수정 방향:** 프론트엔드에서 백엔드 Koyeb URL로 SSE 직접 연결하거나, `vercel.json`에서 `render-stream` 경로를 rewrite 제외 목록에서 관리하도록 하거나, Koyeb 도메인에 직접 SSE 요청을 보냅니다.

### 🛠️ [MEDIUM] A-005: 이미지 → Supabase 업로드 로직이 두 엔드포인트에 중복 구현
- **위치:** `main.py:1156-1184` (`generate_videos`), `main.py:1949-1968` (`render_stream`)
- **리스크 내용:** KIE AI 영상 생성을 위해 이미지를 Supabase에 업로드하는 동일한 로직이 두 군데에 중복되어 있습니다. 에러 처리 방식도 미묘하게 다르며(`HTTPException` 직접 raise vs. `Exception` raise), 렌더링 서버 분리 시 이 로직이 세 번째 사본이 될 가능성이 있습니다.
- **수정 방향:** `upload_image_to_supabase(image_url: str, supabase_url: str, supabase_key: str) -> str` 유틸리티 함수로 추출하여 일원화합니다.

### 🛠️ [MEDIUM] A-006: `RenderStreamRequest.user_id` 기본값 `"beta_tester"` — 운영 환경 데이터 오염
- **위치:** `main.py:306`
- **리스크 내용:** 프론트엔드가 `user_id`를 누락하거나 공백으로 전송하면 `"beta_tester"`가 사용됩니다. `sanitize_uuid("beta_tester")`는 하드코드 fallback UUID로 변환되어 운영 중 모든 미인증 렌더링이 동일 사용자 데이터로 집계되는 오염 현상이 발생합니다.
- **수정 방향:** 기본값을 제거한 뒤 JWT에서 직접 추출하도록 하거나, `user_id`를 `jwt_user_id: str = Depends(get_jwt_user_id)`로 완전히 대체합니다.
