# Risk_Tracker.md (리스크 및 결함 추적기)

본 문서는 사전/사후 클로드 더블 리뷰(Double Review) 프로세스 및 개발 과정에서 발견된 아키텍처, 성능, 보안 리스크와 결함 항목을 추적하고 관리하기 위한 레코드이다. 모든 항목은 `[Resolved]`, `[Pending]`, `[New]` 3단계 상태로 분류 및 관리된다.

---

## 📊 리스크 현황 요약
*   **[New] 신규 리스크:** 5건
*   **[Pending] 진행 중/보류 리스크:** 4건 (RISK-002, NEW-005, PND-001, PND-002)
*   **[Resolved] 해결된 리스크:** 54건 (RISK-001, RISK-004, NEW-002, NEW-003, NEW-004, NEW-006, HOT-001, N-01, HIL-01, HIL-02, HIL-03, HIL-04, HIL-05, HIL-06, HIL-07, HIL-08, RISK-003, NEW-F, N-02, N-06, NEW-001, N-10, N-12, N-13, N-14, N-15, N-03, N-04, N-05, N-07, N-08, N-09, N-11, N-16, N-17, N-18, N-19, N-20, N-21, N-22, N-23, N-24, N-25, N-26, N-27, N-28, N-29, N-30, N-31, N-32, N-33, N-34, N-35, N-36)

---

## 1. 🔴 [New] 신규 리스크

### 🛠️ RISK-005: Koyeb CORS 설정 누락 및 ALLOWED_ORIGINS 미작동 결함
*   **관련 컴포넌트:** `main.py`
*   **영향도:** 높음 (High)
*   **상태:** `[New]`
*   **리스크 내용:** `origins` 배열에 새 Vercel 도메인인 `https://raptor-composer.vercel.app`이 누락되어 백엔드 환경변수 미작동 시 CORS 차단 발생 우려.
*   **대응 방안:** 소스 코드 레벨에서 기본 origins 리스트에 새 도메인을 직접 반영하여 CORS 이중 방어선 구축.

### 🛠️ RISK-006: Failed to fetch 및 네트워크 예외의 영어 노출 결함
*   **관련 컴포넌트:** `src/lib/api-client.ts`, `src/components/AuthDashboard.tsx`
*   **영향도:** 보통 (Medium)
*   **상태:** `[New]`
*   **리스크 내용:** API 서버 장애 혹은 CORS 차단으로 발생하는 `TypeError: Failed to fetch`가 가공되지 않고 노출되어 사용자 경험 저하.
*   **대응 방안:** 공통 `api-client` 및 `AuthDashboard` 내의 fetch catch 블록에 에러 번역 가드를 추가하여 친절한 한글 메시지로 변환.

### 🛠️ RISK-007: AuthDashboard 내 백엔드 URL 하드코딩 결함
*   **관련 컴포넌트:** `src/components/AuthDashboard.tsx`
*   **영향도:** 높음 (High)
*   **상태:** `[New]`
*   **리스크 내용:** 로그인, 회원가입, 대시보드 프로젝트 조회 등 3곳의 fetch 요청에 `http://localhost:8000` 주소가 하드코딩되어 실서버 통신 실패 유발.
*   **대응 방안:** `NEXT_PUBLIC_BACKEND_URL` 기반 `BACKEND_URL` 상수로 API 엔드포인트를 통일하여 환경변수를 올바르게 참조하도록 개선.

### 🛠️ RISK-008: 비밀번호 찾기 기능 미구현 및 회원가입 6자 정책 미가드 결함
*   **관련 컴포넌트:** `src/components/AuthDashboard.tsx`
*   **영향도:** 보통 (Medium)
*   **상태:** `[New]`
*   **리스크 내용:** 비밀번호 분실 시 재설정할 수 있는 UI 수단이 부재하고, 회원가입 시 6자 미만 비밀번호가 프론트에서 필터링되지 않고 Supabase API 호출 에러가 발생.
*   **대응 방안:** `isForgotPasswordMode` 상태와 재설정 이메일 발송(`supabase.auth.resetPasswordForEmail`) 흐름을 신설하고, 회원가입 시 6자 미만 가이드 문구 렌더링 및 프론트 가드를 탑재.

### 🛠️ RISK-009: 로그인 헤더 버튼 absolute 배치 겹침 결함
*   **관련 컴포넌트:** `src/components/AuthDashboard.tsx`
*   **영향도:** 낮음 (Low)
*   **상태:** `[New]`
*   **리스크 내용:** 로그인 버튼의 `absolute top-12 right-24` 포지셔닝이 특정 스크롤 및 모바일 해상도에서 랩터 타이틀 이미지 또는 하단 조작 컴포넌트들과 물리적으로 겹쳐 작동 저해.
*   **대응 방안:** 포지셔닝을 `fixed top-6 right-6 z-[999]`로 교정하여 뷰포트 기준으로 최상단에 안전하게 고정.

---

## 2. 🟡 [Pending] 진행 중 / 보류 리스크

### 🛠️ RISK-002: KIE 모델 단가 분기 및 Supabase Storage FIFO 쿼터 한계
*   **관련 컴포넌트:** `main.py` 및 `src/config/kie_pricing.json`
*   **영향도:** 보통 (Medium)
*   **상태:** `[Pending]`
*   **리스크 내용:** `kie_pricing.json` 내 `veo_fast` 단가 누락 시 예상 요금 연산 시 기본 폴백 요금(0.10)으로 대체 연산되며, 스토리지 FIFO 쿼터가 단일 테스터 `beta_tester` 기준이라 다중 사용자 환경에서 예외 처리 한계가 있음.
*   **대응 방안:** 동적 요금 갱신 API 설계, veo_fast 단가 정식 추가 및 다중 사용자용 스토리지 쿼터 격리 알고리즘 설계 필요.

### 🛠️ NEW-005: user 로컬 스토리지 역직렬화에 따른 만료 세션 Ghost User 노출 현상
*   **관련 컴포넌트:** `src/store/useWorkflowStore.ts`
*   **영향도:** 낮음 (Low)
*   **상태:** `[Pending]`
*   **리스크 내용:** 세션 만료 후 새로고침 시 Zustand 로컬 스토리지 user 정보가 Supabase 비동기 검출 전 일시 노출.
*   **대응 방안:** 마운트 시 Supabase 세션 체크 즉시 user 값 동기화 클리어.

### 🛠️ PND-001: `Share2` 미사용 import (Dead Code)
*   **발생일:** 2026-06-04
*   **관련 컴포넌트:** `src/components/RaptorWorkflow.tsx` (L.4)
*   **영향도:** 낮음 (Low)
*   **상태:** `[Pending]`
*   **리스크 내용:** `lucide-react` import 문에는 정의되어 있으나 코드 내 사용처가 없음. ESLint 규칙 위반 가능성.
*   **대응 방안:** 차후 패치 시 import 구문에서 `Share2` 제거.

### 🛠️ PND-002: `RefreshCw` 미사용 import (Dead Code)
*   **발생일:** 2026-06-04
*   **관련 컴포넌트:** `src/components/RaptorWorkflow.tsx` (L.4)
*   **영향도:** 낮음 (Low)
*   **상태:** `[Pending]`
*   **리스크 내용:** `lucide-react` import 문에는 정의되어 있으나 코드 내 사용처가 없음. ESLint 규칙 위반 가능성.
*   **대응 방안:** 차후 패치 시 import 구문에서 `RefreshCw` 제거.

---

## 3. 🟢 [Resolved] 해결된 리스크

### 🛠️ N-19: `TASKS_DB_PATH` 미정의 변수 참조 런타임 `NameError` 결함 (P-001 / P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** `render-stream-test` 및 `render-stream` 내부 `process_scene_inner`에서 `TASKS_DB_PATH` 참조 레거시 블록을 제거하고, Supabase `tasks` 테이블을 직접 조회(`supabase.table("tasks").select(...)`)하여 가장 최근의 성공한 비디오 결과물을 가져오는 DB 쿼리로 완벽하게 교체 및 검증 완료하였습니다.

### 🛠️ N-20: Supabase Storage `assets` 버킷 임시 이미지 디스크 누수 (P-002 / P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** `generate_videos`와 `render_stream` 제너레이터 내의 비디오 생성 완료 시(성공/실패 상관없이 `finally` 블록에서) Supabase Storage에 임시 적재되었던 `raptor_*.png` 에셋 이미지를 `supabase.storage.from_("assets").remove()` API를 통해 즉시 삭제 및 청소하는 클린업 코드를 작성 완료했습니다.

### 🛠️ N-21: `grok_debug.log` 무한 append에 따른 디스크 소모 리스크 (P-003 / P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** `main.py` 내의 모든 파일 append 쓰기 코드를 걷어내고, Python `logging` 표준 출력을 활용해 표준 출력 스트림(`stdout`)으로 로그를 온전히 통합 출력하도록 수정하여 디스크 고갈 요인을 원천 제거했습니다.

### 🛠️ N-22: FFmpeg 동기 subprocess 호출에 따른 비동기 이벤트 루프 블로킹 결함 (P-004 / P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** `ffmpeg_worker.py` 내부의 FFmpeg 렌더링 subprocess 및 ffprobe 구동 시 메인 이벤트 루프 블로킹을 해소하기 위해 `asyncio.get_event_loop().run_in_executor(None, subprocess.run, ...)` 패턴을 도입하여 비동기 스레드 풀에서 비차단 백그라운드 구동되도록 리팩토링을 완료했습니다.

### 🛠️ N-23: `ffprobe` 실행 환경 의존에 따른 리눅스 컨테이너 크래시 결함 (P-005 / P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** 단순 `"ffprobe"` 문자열 대신 `shutil.which("ffprobe")`를 최우선으로 사용하여 시스템 환경에 맞는 바이너리 절대 경로를 동적으로 획득하는 안전 탐색 장치를 이식 완료했습니다.

### 🛠️ N-24: check_and_enforce_user_limits와 webhook_kie 간 FIFO 임계치 불일치 리스크 (P-006 / P2)
*   **상태:** `[Resolved]`
*   **해결 내역:** 프로젝트 생성 전 10개 한도 정리 로직과 완료 수신 시 50개 한도 정리 로직의 중복을 철거하고, 범용 FIFO 정리 함수 `enforce_user_fifo_limit(user_id, limit)` 공통 유틸리티를 추출 및 단일화했습니다.

### 🛠️ N-25: 회원가입 시 Admin API를 `anon` key로 잘못 호출하는 런타임 오류 (S-001 / P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** anon 권한으로 호출할 수 없는 Admin API 대신 Supabase Auth 표준 회원가입 API인 `/auth/v1/signup` (apikey 헤더 인증) 호출 규격으로 완전히 전환하고, RLS 바이패스 등 민감 권한은 서버 측 `SUPABASE_SERVICE_ROLE_KEY` 환경변수로 초기화한 인스턴스로 격리 통제하여 해결했습니다.

### 🛠️ N-26: `sanitize_uuid` 하드코드 fallback에 따른 다중 사용자 격리 완전 붕괴 취약점 (S-002 / P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** UUID가 아닌 임의 ID 문자열 유입 시 하드코드 fallback UUID로 오용되던 로직을 전면 소거하고, `sanitize_uuid`에서 정규식 매칭 실패 시 즉각 `HTTPException(status_code=400)`을 throw하도록 엄격한 검증 가드를 세워 데이터 오염을 예방했습니다.

### 🛠️ N-27: 핵심 API 엔드포인트 인증 및 JWT 검증 누락 취약점 (S-003 / P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** `/api/projects/{id}/tasks` (POST), `/api/tasks/{task_id}` (PATCH), `/api/render-task` (POST), `/api/archive` (GET) 에 `Depends(get_jwt_user_id)` 가드를 강제 장착하고, 소유권 조회 헬퍼(`verify_project_owner`, `verify_task_owner`)를 통합 연계하여 타인의 자원 위변조(IDOR)를 완전 차단했습니다.

### 🛠️ N-28: Supabase `anon` 키 직접 조작으로 인한 RLS 우회 및 연동 결함 (S-004 / P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** 백엔드 SDK 기동 시 사용되는 API Key에 anon key 대신 RLS 보안을 완벽히 우회하여 자원을 통제할 수 있는 서버 환경 전용 `SUPABASE_SERVICE_ROLE_KEY`를 연동해 DB SDK 인스턴스를 안전하게 초기화했습니다.

### 🛠️ N-29: CORS `allow_origins` 로컬 호스트 하드코딩으로 인한 통신 차단 결함 (S-005 / P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** CORS allow_origins 설정에 로컬 하드코딩 주소 외에도 `ALLOWED_ORIGINS` 환경변수를 파싱해 동적으로 오리진 도메인 목록을 extend 할 수 있도록 구현하여 클라우드 CORS 문제를 해소했습니다.

### 🛠️ N-30: Supabase Storage `assets` 버킷 퍼블릭 노출에 따른 콘텐츠 유출 리스크 (S-006 / P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** 스토리지 `assets` 버킷을 private으로 폐쇄 조치하였고, 이미지 업로드 후 프론트에는 단기 만료(30분 TTL) 제한이 적용된 서명된 보안 임시 URL(`create_signed_url`)을 동적으로 생성 및 반환하도록 리팩토링했습니다.

### 🛠️ N-31: 비동기 렌더링 `callback_url` 미사용에 따른 웹훅 연동 단절 결함 (A-001 / P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** 비동기 태스크 생성 시 `/api/render-task` 로 인입되는 `callback_url`을 프로젝트 `plan_snapshot` JSONB에 인라인 저장한 후, 렌더러가 호출될 때 `webhook_url` 매개변수에 바인딩하여 렌더 완료 웹훅이 정상 수신되도록 수립했습니다.

### 🛠️ N-32: 웹훅 수신과 SSE 스트림 간 비동기 브릿지 연동 부재 결함 (A-002 / P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** 글로벌 인메모리 이벤트 버스 `TASK_EVENTS` (task_id -> asyncio.Event)를 설계하여, 웹훅 수신(/api/webhook/kie)으로 DB 갱신 시 이벤트를 세팅하고 SSE 제너레이터는 5초 대기와 DB 조회를 병행하도록 고성능 하이브리드 비동기 동기화 브릿지를 구현 완료했습니다.

### 🛠️ N-33: KIE 웹훅 검증 시 `"sha256="` 프리픽스 처리 누락으로 인한 인증 실패 결함 (A-003 / P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** `/api/webhook/kie`의 서명 대조 시 수신된 `X-KIE-Signature` 헤더 값에 `"sha256="` 프리픽스가 존재하는지 확인하고, 존재할 경우 슬라이싱하여 순수한 hexdigest 만 추출한 뒤 HMAC-SHA256 비교를 정상 처리하도록 예외 보완 완료했습니다.

### 🛠️ N-34: `render_stream` KIE 폴링 연산이 Vercel Serverless Function 타임아웃을 초과하는 결함 (A-004 / P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** 프론트엔드 API 클라이언트(`api-client.ts` 및 `RaptorWorkflow.tsx`)에서 백엔드 직접 연결을 수행할 수 있게 환경 변수 `NEXT_PUBLIC_BACKEND_URL`을 동적으로 파싱 적용하여 Vercel 300초 프록싱 타임아웃을 완전 우회했습니다.

### 🛠️ N-35: 이미지의 Supabase 스토리지 업로드 로직의 중복 구현 리스크 (A-005 / P2)
*   **상태:** `[Resolved]`
*   **해결 내역:** `main.py` 내에 `upload_image_to_supabase` 공통 유틸리티 헬퍼를 추출하여, HTTP get 다운로드와 storage.upload, 그리고 create_signed_url 서명된 URL 반환 로직을 일원화하여 중복을 해소했습니다.

### 🛠️ N-36: RenderStreamRequest user_id 기본값 "beta_tester" 하드코딩에 따른 데이터 오염 리스크 (A-006 / P2)
*   **상태:** `[Resolved]`
*   **해결 내역:** `RenderStreamRequest` DTO의 user_id 기본값을 제거하고, 라우트에서 Depends를 통해 실제 JWT 검증을 거친 사용자 UUID를 강제로 결합하도록 하여 데이터 오염을 예방했습니다.

### 🛠️ N-03: 아카이브 비디오 URL 상대경로 버그 (보관함 재생/다운로드 404)
*   **상태:** `[Resolved]`
*   **해결 내역:** 프론트엔드 재생/다운로드 시 `BACKEND_URL` 환경 변수를 바인딩하여 absolute URL(`http://localhost:8000/outputs/...`)로 정확하게 재생되도록 연동 완료했습니다.

### 🛠️ N-04: `calculateEstimatedCost` 및 `calculateActualCost` 계산 로직 중복 구현
*   **상태:** `[Resolved]`
*   **해결 내역:** `src/lib/costCalculator.ts` 공통 모듈로 공통 요금 계산 로직을 추출하고, 다중 컴포넌트(`RaptorWorkflow.tsx`, `AuthDashboard.tsx`)에 동시 바인딩하여 계산 정합성을 통합했습니다.

### 🛠️ N-05: FIFO 스토리지 정리 임계값 불일치 (49 vs 50)
*   **상태:** `[Resolved]`
*   **해결 내역:** N-24 해결 내역과 마찬가지로, `enforce_user_fifo_limit(user_id, limit)` 공통 유틸 함수로 일원화하고 생성(9개 유지 -> 추가 후 10개) 및 수신(50개 한도)에 알맞은 임계치를 주입하여 비즈니스 규칙을 정리했습니다.

### 🛠️ N-07: `test_schemas.py` 주 렌더링 파이프라인`/api/render-stream` 누락
*   **상태:** `[Resolved]`
*   **해결 내역:** Pydantic strict check를 Request 명세에 이식하였고, tests 테스트 스위트에 data schema validation 테스트 커버리지를 보완 완료했습니다.

### 🛠️ N-08: `handleRenderVideoFromScratch`의 50ms setTimeout 레이스 컨디션 위험
*   **상태:** `[Resolved]`
*   **해결 내역:** React 이펙트 체인(`useEffect`) 및 렌더 가드 상태 변수 처리를 적용하여 50ms 강제 대기 없이도 완벽한 초기화-재랜더 체인 흐름이 보장되도록 수정했습니다.

### 🛠️ N-09: Claude Opus 모델 표기 버전 불일치
*   **상태:** `[Resolved]`
*   **해결 내역:** UI 텍스트 및 Option value의 Opus 지정을 최신 Claude API 규격인 `"claude-opus-4-7"`로 동기화 완료했습니다.

### 🛠️ N-11: Supabase 프로젝트 전용 도메인 하드코딩
*   **상태:** `[Resolved]`
*   **해결 내역:** `ALLOWED_PROXY_DOMAINS`에 하드코딩되었던 Supabase 프로젝트 도메인 주소를 `SUPABASE_URL` 환경변수에서 동적으로 도메인을 파싱해 proxy-image SSRF 허용 목록에 추가되도록 개선했습니다.

### 🛠️ N-16: `RaptorWorkflow.tsx` SSE 폴링 C3/C4 회복력(Resilience) 결함 (P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** SSE 연결이 끊기거나 Timeout이 일어날 경우, 백그라운드 데이터베이스 Task의 완료 여부를 검사하는 Short polling 폴백 함수를 장착하여 Resilience를 보강 완료했습니다.

### 🛠️ N-17: `main.py` 로컬 개발 환경 절대 경로 노출 및 OS Walk 위험 (P2)
*   **상태:** `[Resolved]`
*   **해결 내역:** `C:\Users\webke\...` 하드코딩된 절대 경로를 `os.path.expanduser("~")` 및 환경 변수 `BRAIN_DIR` 감지 방식으로 개선하여 OS 이식성을 확보하고 crash 위험을 해소했습니다.

### 🛠️ N-18: `e2e_recheck.js` SSE 스트림 완료 미검증으로 인한 E2E 커버리지 부족 (P2)
*   **상태:** `[Resolved]`
*   **해결 내역:** E2E 테스트 스크립트가 SSE response stream을 구독(Wait for stream output)하여 완료 상태 및 `output_url` 획득 검증을 온전히 거치도록 보강했습니다.

### 🛠️ RISK-001: 에이전트 간 리뷰 프로세스 누락 및 리스크 추적 부재
*   **상태:** `[Resolved]`
*   **해결 내역:** 규칙 문서화 및 `Risk_Tracker.md`를 통한 주기적 리스크 트래킹 체계 적용.

### 🛠️ RISK-004: 4대 핵심 결함 및 refine-prompt DALL-E 3 하드코딩 결함 완결
*   **상태:** `[Resolved]`
*   **해결 내역:** WAF 우회 토큰 주입, tpad 동기화 필터, kie_pricing.json 연동, DALL-E 3 KIE 비동기 프록시 교체 완료.

### 🛠️ NEW-002: 옵션 A(실사 이미지 업로드) 씬 할당 로직의 상태 충돌 가능성
*   **상태:** `[Resolved]`
*   **해결 내역:** `image_source: 'manual'` 도입을 통한 AI 재생성 시 수동 업로드 씬 스킵 구현.

### 🛠️ NEW-003: `/api/refine-prompt` 모델 파라미터 기본값 폴백 미정의
*   **상태:** `[Resolved]`
*   **해결 내역:** `request.model` or "gpt-image-2" 기본값 설정 완료.

### 🛠️ NEW-004: `AuthDashboard.tsx` 보관함 테이블의 빈 상태(Empty State) 미정의
*   **상태:** `[Resolved]`
*   **해결 내역:** 데이터가 없을 경우 표시할 전용 Empty State UI를 세련되게 구현 완료.

### 🛠️ NEW-006: 프론트엔드 비디오 렌더링 예외 처리(Catch) 미흡으로 인한 UI 무한 대기 결함
*   **상태:** `[Resolved]`
*   **해결 내역:** handleRenderVideo catch 블록 에러 throw 및 씬 status 롤백 해제 완료.

### 🛠️ HOT-001: `Film` import 누락으로 인한 JSX 렌더링 오류 (UI 크래시)
*   **상태:** `[Resolved]`
*   **해결 내역:** `Film` 컴포넌트를 import 선언부에 올바르게 추가하여 렌더링 크래시 완전 해결.

### 🛠️ N-01: datetime.datetime.now() AttributeError 렌더링 크래시 결함
*   **상태:** `[Resolved]`
*   **해결 내역:** 모듈 최상단 임포트를 `from datetime import datetime, timedelta, date`로 통일하고 `datetime.datetime.now()`를 `datetime.now()`로 전수 수정하였으며, `/api/auth/post-review` 내부 지역 임포트를 정리하여 네임스페이스 충돌을 근본적으로 방지함.

### 🛠️ HIL-01: TTS 음성 생성 KIE 프록시 401 Unauthorized 에러
*   **상태:** `[Resolved]`
*   **해결 내역:** OpenAI TTS API 호출 endpoint를 KIE AI Proxy 경로인 `https://api.kie.ai/v1/audio/speech`로 우회 오버라이딩하고, Authorization과 X-BYOK-KIE 두 헤더에 KIE API 키를 정상 주입하여 401 인증 거부 에러를 해결 완료했습니다.

### 🛠️ HIL-02: KIE 이미지 모델명 매핑 규격 불일치 (422 에러)
*   **상태:** `[Resolved]`
*   **해결 내역:** KIE 전용 이미지 모델명 매핑 헬퍼 함수(`map_image_model`)를 신설하여 OpenAI 선택 시 `"gpt-image-2"`, Grok 선택 시 `"grok-imagine/text-to-image"`, Nano Banana 2 선택 시 `"nano-banana-2"` 로 매핑하였으며, 이미지 일괄 생성(`/api/generate-images`) 및 이미지 재생성(`/api/refine-prompt`) 엔드포인트 양쪽 모두에 연동 완료했습니다.

### 🛠️ HIL-03: 빈 이미지/비디오 에셋 상태에서의 Step 4 진입 결함
*   **상태:** `[Resolved]`
*   **해결 내역:** 각 씬의 이미지나 동영상 에셋이 누락되었거나 렌더링/에러 상태일 때 Step 4 진입 이동 버튼이 disabled 되어 클릭을 완벽하게 차단하도록 `allImagesReady` 가드 상태 변수와 UI 스타일 매핑을 적용 완료했습니다.

### 🛠️ HIL-04: 대시보드 헤더 프로필 버튼 스크롤 겹침 결함
*   **상태:** `[Resolved]`
*   **해결 내역:** 대시보드 헤더의 이메일/프로필 버튼 래퍼 div의 fixed 클래스를 absolute로 변경하여, 스크롤을 내릴 때 상단에 붙어 대시보드 메인 캔버스 및 다른 UI들과 겹치는 레이아웃 결함을 성공적으로 해소했습니다.

### 🛠️ HIL-05: StreamingResponse generate_stream() 연결 단절 감지 부재 결함 (P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** 스트리밍 응답 도중 클라이언트 연결 끊김을 감지할 수 있도록 `raw_request: Request` 객체를 주입받고, KIE Polling loop, task completion loop, FFmpeg render loop 내부에 `await raw_request.is_disconnected()` 검사를 추가하여 자원을 즉시 회수할 수 있도록 수정하였습니다.

### 🛠️ HIL-06: Step 4 렌더링 취소 버튼 및 크레딧 방어 UX 구현 결함 (P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** Step 4 진행 중 사용자가 언제든 작업을 중단할 수 있는 `[🛑 렌더링 취소]` 버튼을 구현하고, SSE 연결을 `abort()` 처리하도록 연동했습니다. 씬의 KIE `taskId` 발급 전(⚪ 무채색/크레딧 미소모)과 발급 후(🔵 활성색/다음 씬 크레딧 절약) 상태에 따라 버튼의 색상과 안내 문구를 동적으로 시각화했습니다.

### 🛠️ HIL-07: scene_update SSE 이벤트 수신 시 상태 유실 결함 (P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** SSE 핸들러 내부에서 클로저 스테일(Stale) 상태로 인해 씬 상태가 덮어씌워져 병렬 업데이트가 유실되는 현상을 방지하기 위해, `setFinalAssets((prev) => ...)` 형태의 함수형 업데이트 패턴으로 완전히 리팩토링했습니다.

### 🛠️ HIL-08: ZIP 패키지 다운로드 도중 Blob 메모리 조기 해제 결함 (P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** `handleDownloadPackage` 실행 시 브라우저가 Blob 데이터를 다 읽기도 전에 메모리가 해제되는 현상을 막고자, `URL.revokeObjectURL(blobUrl)`의 호출 시점을 `setTimeout`으로 감싸 최소 150ms 지연시킨 후 안전하게 해제하도록 조치했습니다.

### 🛠️ RISK-003: 크로스 플랫폼 폰트 경로 하드코딩 결함 (P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** Windows 하드코딩 경로를 분리하고 `os.name` 및 `platform` 감지를 통해 Windows 환경에서는 기존 경로, Linux/Mac 및 클라우드 배포 환경에서는 리눅스 표준 CJK 폰트 후보 경로들(NanumGothic, NotoSansCJK-Regular, UnDotum)을 최우선으로 자동 탐색하여 한국어 자막 깨짐을 방지하고 예비 수단으로서만 DejaVu Sans, Liberation Sans로 폴백하도록 재구성하였습니다.

### 🛠️ NEW-F: 취소/단절 시 DB 내 태스크 상태 롤백(Failed) 누수 (P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** 백엔드 `main.py` 제너레이터 내 비동기 씬 처리기 `process_scene_inner` 내부 전체를 `try-except asyncio.CancelledError` 및 `finally` 블록으로 래핑하였으며, 특히 SSE 스트림 완료 루프 및 FFmpeg 렌더링 루프에서 클라이언트 연결 단절(is_disconnected)을 감지했을 때 단순 break 하지 않고 `raise asyncio.CancelledError()`를 명시적으로 던져 failed 상태 복구 로직이 누락 없이 100% 실행되도록 보장함으로써 화면 무한 대기 현상을 차단했습니다.

### 🛠️ N-12: `ffmpeg_worker.py` `temp_dir` 미정리 디스크 누수 (P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** `render_video` 함수의 본문 전체를 `try/finally`로 감싸 `shutil.rmtree(temp_dir, ignore_errors=True)`를 강제 호출하게 하였고, `main.py`의 `render_stream` 제너레이터 내에서 `ffmpeg_worker.render_video`를 호출한 뒤 `finally` 절에서 `await gen.aclose()`를 보증하여 리소스 및 찌꺼기를 즉각 회수하도록 하였습니다. `download_image` 내의 bare except도 `except Exception:`으로 수정하여 가드를 강화했습니다.

### 🛠️ N-13: `main.py` `/api/webhook/kie` 웹웹훅 수신 무인증 (P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** `WEBHOOK_SECRET` 환경 변수를 도입하고, FastAPI `Request` 객체에서 raw body를 직접 가로채 `hmac.compare_digest` 방식으로 HMAC-SHA256 서명을 정밀하게 대조한 후 `KieWebhookPayload` 역직렬화를 수동 검증하는 방식으로 보안 우회를 완전 차단했습니다. 또한 `tests/test_webhook.py` 모의 호출 테스트도 HMAC 서명 적재를 통해 100% 정상 작동하도록 업데이트했습니다.

### 🛠️ N-14: `main.py` `/api/user-videos` GET IDOR 취약점 (P0)
*   **상태:** `[Resolved]`
*   **해결 내역:** Bearer 토큰 검증 헬퍼인 `get_jwt_user_id`를 통해 Supabase JWT 서명 및 `audience="authenticated"`를 대조하였고, `get_user_videos`(GET), `get_dashboard_projects`(GET), `create_project`(POST), `upload_user_video`(POST)의 4대 API에 `Depends(get_jwt_user_id)`를 적용하여 IDOR 우회 시도를 차단했습니다.

### 🛠️ N-15: `main.py` JSON DB 파일 락 부재로 인한 Race Condition (P1)
*   **상태:** `[Resolved]`
*   **해결 내역:** 모듈 수준의 `db_lock = asyncio.Lock()` 싱글턴을 선언하여, 파일 쓰기가 동반되는 `create_project`, `upload_user_video`, `webhook_kie` 등의 API 엔드포인트 핸들러 진입로에서 `async with db_lock:` 블록을 실행함으로써 TOCTOU 및 Race Condition을 직렬화하여 박멸했습니다.
