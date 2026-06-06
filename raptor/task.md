# RAPTOR v2.12.0 대시보드 대통합 및 Project-Task 매핑 수술 작업 목록 (task.md)

- `[x]` **0단계: 준비 및 백업**
  - `[x]` `backup_v2.12.0_Dashboard_Project_Mapping.zip` 백업 아카이브 생성
  - `[x]` `_RAPTOR_APP_MD_v2.2.md` 설계서 작성 완료
  - `[x]` Claude Code BMode 사전 리뷰 (`20260604_RAPTOR_Review_Report_v2.12.0_BMode_Pre.md`) 완료
- `[x]` **1단계: [🔴 P0] NEW-A 과금 누수 버그 즉시 제거**
  - `[x]` `BYOKSettingsForm.tsx` 마운트 시 `/auth/post-review` 자동 호출부 삭제
- `[x]` **2단계: [🔴 P0] 백엔드 Project-Task 매핑 데이터베이스 구축**
  - `[x]` `main.py` 내 `ProjectModel`, `TaskModel` Pydantic 스키마 정의
  - `[x]` 프로젝트 생성 API (`POST /api/projects`) 구현
  - `[x]` 태스크 생성 API (`POST /api/projects/{project_id}/tasks`) 및 업데이트 API (`PATCH /api/tasks/{task_id}`) 구현
  - `[x]` 대시보드 출력용 병합 조회 API (`GET /api/dashboard/projects`) 구현
  - `[x]` Project-Task 단위 1:N 조인 해시 최적화 및 10개 프로젝트 제한 CASCADE FIFO 클린업 로직 구현
- `[x]` **3단계: [🔴 P0] 프론트엔드 메인 UI 청소 및 통합 대시보드 구현**
  - `[x]` `RaptorWorkflow.tsx` 하단 beta_tester 메일, 보관함 테이블, 로그아웃, 설정 버튼 완전 삭제
  - `[x]` 우측 상단 프로필 및 통합 대시보드 모달 신설
  - `[x]` 통합 대시보드 3개 탭 구성 ([설정], [프로젝트 관리] 게시판 테이블, [계정] 로그아웃)
  - `[x]` 크레딧 계산 로직 및 `kie_pricing.json` 의존 코드 전면 철거
- `[x]` **4단계: [🔴 P0] TDD 채점지 작성 및 E2E 검증**
  - `[x]` `tests/test_project_task_mapping.py` [NEW] 작성 및 pytest 구동
  - `[x]` 새로고침 과금 방어, 대시보드 모달 출력, Retry 시 히스토리 다중 라인 보존 상태 E2E 검증
- `[x]` **5단계: 사후 리뷰 제출**
  - `[x]` `/api/auth/post-review`를 호출하여 사후 리뷰 보고서 작성 및 리스크 트래커 동기화

## RAPTOR v2.12.1 HIL QA 핫픽스 작업 목록
- `[x]` **0단계: 준비 및 백업**
  - `[x]` `backup_v2.12.1_HIL_QA_Fix.zip` 백업 아카이브 생성
- `[x]` **1단계: [🔴 P0] Mock 자동 인증 우회 로직 완전 철거**
  - `[x]` `RaptorWorkflow.tsx` 및 `AuthDashboard.tsx` 등 모든 곳의 가짜 사용자(Mock User) 자동 발급 우회 로직 완전 제거
  - `[x]` Supabase Auth 진짜 세션 정보만 엄격하게 감시 및 Authorization Bearer 토큰 연동
- `[x]` **2단계: [🔴 P0] 로그아웃 상태 초기화 및 폼 보안 수정**
  - `[x]` 로그아웃 시 Zustand useWorkflowStore 내의 모든 데이터(상품 정보, 기획안, 씬 데이터) 완전 초기화 (`resetWorkflow()`)
  - `[x]` 로그인/회원가입 성공, 실패 시, 로그아웃 시, 그리고 모달 토글 시 패스워드 인풋 필드를 무조건 빈 값(`''`)으로 초기화
  - `[x]` 설정 탭의 API 키 빈값 업데이트 시 기존 키를 덮어쓰지 않도록 폼 유효성 검사 방어 코드 추가
  - `[x]` 설정 탭 내 KIE API 키 설정 시 마스킹된 플레이스홀더(`kie-***... (이미 설정됨)`) 표시
- `[x]` **3단계: [🔴 P0] UI 레이아웃 및 데드엔드 픽스**
  - `[x]` 우측 상단 '프로필(대시보드)' 버튼의 CSS를 `fixed top-12 right-24 z-[100]`으로 교정하여 최상단에 안정적으로 고정
  - `[x]` Step 3 완료 조건 (`canGoToStep4`)을 느슨하게 점검하여 다음 단계 이동 버튼 노출 보장 및 데드엔드 회피
- `[x]` **4단계: 테스트 및 수동 검증**
  - `[x]` `pytest`를 통한 데이터 정합성 검증 확인
  - `[x]` 폼 보안, 마스킹 플레이스홀더, UI 레이아웃 정상 동작 확인

## RAPTOR v2.12.2 초긴급 Auth & API 결함 핫픽스 작업 목록
- `[x]` **0단계: 준비 및 백업**
  - `[x]` `backup_v2.12.2_Critical_Auth_API_Hotfix.zip` 백업 아카이브 생성
- `[x]` **1단계: [🔴 P0] 프론트엔드 AI SDK 직접 호출 철거 및 백엔드 프록싱**
  - `[x]` 프론트엔드 파일 내 외부 AI SDK 직접 초기화/호출 의존성 완전 철거
  - `[x]` KIE API Key를 헤더(`X-BYOK-KIE`)에 담아 전송하도록 `api-client.ts` 개편
  - `[x]` 백엔드가 헤더를 읽어 프록시 호출하게 하여 Forbidden 에러 원천 차단
- `[x]` **2단계: [🔴 P0] Supabase - Zustand 완벽 동기화 및 Auth 로딩 상태 도입**
  - `[x]` Zustand `isAuthLoading` 상태 신설 및 세션 검증 도중 로딩 스피너 강제 분기
  - `[x]` `onAuthStateChange` 리스너를 전역 등록하고, `SIGNED_OUT` 시에만 `resetWorkflow()`가 일어나도록 하드 맵핑
- `[x]` **3단계: [🔴 P0] 로컬 스토리지 Ghost User(만료 세션) 완전 멸균**
  - `[x]` Supabase 세션 유효성 검증 실패 시, 로컬 스토리지 user 상태를 강제 null로 초기화하여 캐시 불일치 박멸
- `[x]` **4단계: [🔴 P0] 모달 토글 비밀번호 초기화 타이밍 가드 적용**
  - `[x]` `isModalOpen === false`이고 로그인 진행 중이 아닐 때만 비밀번호를 비우도록 가드 적용
- `[x]` **5단계: 테스트 및 수동 검증**
  - `[x]` `pytest`를 통한 데이터 정합성 검증 확인
  - `[x]` 브라우저 스토리지 클리어 후 로그인 루프 복구 확인 및 AI API 정상 호출 검증

## RAPTOR v2.13.3-security 보안 및 인프라 누수 멸균 수술 작업 목록 (task.md)
- `[x]` **0단계: 준비 및 사전 리뷰**
  - `[x]` `backup_v2.13.3_Pre_Security_Fix.zip` 백업 아카이브 생성 및 용량 확인
  - `[x]` `implementation_plan.md` (v2.13.3-security) 초안 작성 및 동기화
  - `[x]` Claude CLI B모드 사전 리뷰 수행 및 `20260606_RAPTOR_Review_Report_v2.13.3_Pre.md` 작성
- `[x]` **1단계: [🔴 P0] N-12: ffmpeg_worker.py temp_dir try/finally 누수 정리**
  - `[x]` `render_video` 함수의 모든 작업 영역을 `try/finally`로 감싸서 예외 상황이나 성공 시 무조건 `shutil.rmtree` 실행 구현
- `[x]` **2단계: [🔴 P0] N-13: /api/webhook/kie HMAC-SHA256 암호 검증 구현 (웹혹 위조 방어)**
  - `[x]` `.env`에 `WEBHOOK_SECRET` 정의 및 `main.py` 웹훅 엔드포인트에 HMAC 서명 인증 가드 구현
- `[x]` **3단계: [🔴 P0] N-14: /api/user-videos GET JWT 인증 강제화 (IDOR 방어)**
  - `[x]` `/api/user-videos` GET 요청 시 `Authorization` 헤더에서 Bearer 토큰(JWT) 추출 및 Supabase Signature 검증
  - `[x]` 토큰 내부의 `sub` 사용자 ID와 요청의 `user_id` 동일 여부 판별 로직 적용
- `[x]` **4단계: [🟡 P1] N-15: main.py JSON DB asyncio.Lock 싱글턴 제어**
  - `[x]` `main.py` 모듈 수준의 `db_lock = asyncio.Lock()` 선언 및 모든 JSON 읽기/쓰기 구문에 `async with db_lock:` 가드 이식
- `[x]` **5단계: TDD/E2E 검증 및 사후 리뷰**
  - `[x]` Next.js 프로덕션 빌드 (`npm run build`) 구동
  - `[x]` `node e2e_recheck.js` E2E 자동 테스트 수행 및 결과 확인
  - `[x]` `claude -p` 사후 리뷰 수행 및 `20260606_RAPTOR_Review_Report_v2.13.3_Post.md` 작성
  - `[x]` `Risk_Tracker.md` 내 리스크 상태 동기화 및 완료 보고
