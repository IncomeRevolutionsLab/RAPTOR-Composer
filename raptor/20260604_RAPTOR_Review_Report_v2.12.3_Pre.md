# RAPTOR SHOPPING SHORTS GEM - PRE-REVIEW REPORT (V2.12.3)

*   **Author:** Claude Code
*   **Date:** 2026-06-04
*   **Target Plan:** [implementation_plan.md](file:///C:/Users/webke/.gemini/antigravity-ide/brain/51a7c32d-7194-4fe9-8adc-cf363c99135a/implementation_plan.md)
*   **Context:** RAPTOR P0/P1 버그 완벽 박멸 및 사후 리뷰 자동화 설계 사전 검증

---

## 1. 🟢 [Resolved]

이번 패치 계획서(`implementation_plan.md` v2.12.3)에 반영되어 근본적으로 해결될 예정인 리스크 및 기존 결함 항목입니다.

*   **NEW-005: 만료 세션 Ghost User 노출 및 하이드레이션 깜빡임 현상**
    *   *원인:* 세션 만료 후 새로고침 시 Zustand 로컬 스토리지에 남아있던 user 정보가 Supabase의 비동기 세션 검출 전 일시 노출되어 화면이 깜빡이거나 비로그인 사용자가 대시보드 진입을 우회할 수 있었음.
    *   *해결책:* `AuthProvider.tsx`에서 하이드레이션 상태인 `hasHydrated`가 `false` 이거나 `isAuthLoading` 상태일 때 화면 전체를 강제 로딩 처리하여, 세션 검출 전에 Zustand 정보가 일시 노출되는 현상을 완벽히 차단함.
*   **N-06: Mock 자동 인증 및 우회 보안 취약점**
    *   *원인:* `userId` 기본값이 `'beta_tester'`로 하드코딩되어 있고, 비로그인 상태일 때 가짜 세션을 생성하여 인증을 우회할 수 있는 보안 취약점이 존재했음.
    *   *해결책:* `useWorkflowStore.ts`의 `userId` 디폴트 값을 빈 문자열(`''`)로 변경하고, `setUser(null)` 호출 시 `userId` 역시 빈 문자열로 매핑되도록 철저하게 삭제하여 가짜 유저 세션을 완벽히 철거함.
*   **로그아웃 시 상태 누수 및 스토어 리셋 불일치**
    *   *원인:* 로그아웃을 해도 Zustand 스토어 내의 민감한 API Key 정보와 잔여 UI 상태가 메모리에 잔존하여 이전 작업이 노출되는 등의 상태 누수가 발생함.
    *   *해결책:* `handleLogout` 실행 시 Zustand의 `user`와 `userId` 뿐만 아니라 API Key 상태(`kieKey`, `isKeyConfigured`, `csrfToken`)를 전부 빈 값 및 `null`로 강제 초기화하고 브라우저 `localStorage`를 직접 완전 삭제한 뒤 `resetWorkflow`를 실행하도록 동기화함.
*   **로그인 모달 UI/Z-index 결함 및 CLOSE 버튼 노출 문제**
    *   *원인:* 헤더 버튼 wrapper의 z-index(`z-[100]`)가 대시보드 모달(`z-50`)보다 크게 설정되어 있어, 모달 뒤쪽의 요소들이 모달 위로 비정상 노출되는 레이아웃 겹침 발생.
    *   *해결책:* 헤더 프로필 wrapper의 z-index를 `z-[40]`으로, 글로벌 세팅 버튼을 `z-[45]`로 각각 하향 조정하고, 대시보드 모달 wrapper의 z-index를 `z-[1000]`으로 대폭 상향하여 명확하게 레이어 분리 및 격리함.

---

## 2. 🟡 [Pending]

이번 계획서의 범위를 벗어나며 차후 추가 핫픽스나 리팩토링 단계에서 추적/관찰해야 하는 진행 중인 리스크 항목입니다.

*   **N-02: 테스트 환경 `COOKIE_ENCRYPTION_KEY` 환경변수 암묵적 의존**
    *   *원인:* `main.py` 최상단에서 Fernet 암호화 검사로 인해 `COOKIE_ENCRYPTION_KEY`가 없으면 `import` 단에서 런타임 에러가 발생함.
    *   *잔여 리스크:* 본 수술 계획서에는 테스트 케이스 모듈의 Fernet 환경 변수 폴백 가드가 누락되어 있어, 로컬 `.env`가 없는 CI 파이프라인에서 테스트 실패 리스크가 그대로 남아있음.
*   **N-03: 아카이브 비디오 URL 상대경로 버그 (Next.js 3000 포트 404)**
    *   *원인:* DB에 저장되는 비디오 결과물 경로가 `/outputs/...` 와 같은 백엔드 상대경로로 저장되어 프론트엔드에서 참조 시 404가 발생할 우려가 있음.
    *   *잔여 리스크:* 본 계획서에서는 백엔드 측의 DB 저장 경로를 절대 URL로 교정하거나 프론트엔드단에서 백엔드 호스트(`http://localhost:8000`)를 접두사로 동적 매핑하는 프록시 세부 코드가 완전 명시되지 않음.
*   **RISK-002: KIE 모델 단가 분기 및 Supabase Storage FIFO 쿼터 한계**
    *   *리스크 내용:* `veo_fast` 모델의 예상 요금 연산 단가 누락 및 다중 사용자 격리 알고리즘 설계는 본 핫픽스 대상 범위에 포함되지 않아 여전히 보류 상태임.
*   **RISK-003: 크로스 플랫폼 폰트 경로 하드코딩 결함**
    *   *리스크 내용:* FFmpeg 자막 합성 시 Windows용 폰트 경로(`C:/Windows/Fonts/malgun.ttf`)가 하드코딩되어 Linux/Docker 기반 서버 마이그레이션 시의 실행 오류 잠재력 상존.

---

## 3. 🔴 [New]

이번 버그 핫픽스 패치 수술 계획의 상세 설계와 현재 코드 상태를 대조했을 때 새롭게 식별된 잠재적 위험성 및 권장 사항입니다.

*   **회원가입 중복 시도(User Already Exists) 에러 메시지의 가변성 위험**
    *   *내용:* Supabase Auth 모듈이나 테넌트 설정에 따라 에러 메시지 텍스트가 대소문자나 띄어쓰기가 미세하게 달라질 수 있음 (`User already registered` vs `user_already_exists` 등).
    *   *대응 권장:* 단순한 string 일치 검사 대신, `.toLowerCase().includes("already")` 나 Supabase Auth API 에러 코드(status) 검출 방식을 혼합하여 보다 견고하게 에러를 필터링해야 함.
*   **FastAPI `BackgroundTasks`를 통한 사후 리뷰 백그라운드 구동 시의 에러 전파 제어**
    *   *내용:* 스트리밍 연결이 클라이언트로부터 강제 종료(소켓 끊김)되더라도 `BackgroundTasks`에 등록된 `generate_post_review_report_task`는 백그라운드 스레드에서 무조건 기동하게 됨.
    *   *대응 권장:* 리뷰용 Claude API Key(BYOK)가 잘못 기재되어 있거나 API 호출이 실패할 때, 백그라운드 태스크 내부에서 발생하는 에러가 백엔드 프로세스 전체 안정성에 영향을 주지 않도록 내부 `try-except` 블록으로 철저히 격리해야 함.
*   **비밀번호 필드 강제 초기화 시의 UIUX 부작용**
    *   *내용:* `finally` 블록에서 `setPassword('')`를 강제 적용할 때, 사용자가 한창 로그인 모달을 다루며 재시도할 때 타이핑을 방해받거나 깜빡임 현상이 심하게 나타날 위험성.
    *   *대응 권장:* 폼 제출 처리가 완료된 순간이나 모달을 닫는 시점, 또는 API 응답 처리가 완전히 결정된 성공/실패 브랜치 내부에서만 비밀번호를 선별적으로 초기화하는 설계가 적합함.
