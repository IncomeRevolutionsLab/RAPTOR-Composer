# RAPTOR SHOPPING SHORTS GEM - WALKTHROUGH (V2.12.3)

*   **Author:** Gemini Agent
*   **Date:** 2026-06-04
*   **Version:** v2.12.3 (Hotfix & Automation Patch)

본 문서에서는 브라우저 내 Forbidden 에러 박멸, Mock User 잔재 완벽 철거, 회원가입 중복 한글 경고, CSS z-index 레이아웃 겹침 해결 및 백엔드 사후 리뷰 보고서 자동화 구현 내역과 E2E 검증 결과를 기록합니다.

---

## 1. 주요 변경 및 구현 내역

### 1.1. [🔴 P0] 브라우저 내 Forbidden 에러 완벽 박멸
*   **원인:** `NEXT_PUBLIC_SUPABASE_ANON_KEY`가 비밀 키(`sb_secret_...`)로 오세팅되어 있어 브라우저(Edge Gateway)에서 차단되어 `Forbidden use of secret API key in browser` 에러가 발생함.
*   **해결:** `SUPABASE_JWT_SECRET`을 바탕으로 HS256 알고리즘을 사용해 유효한 public `anon` JWT 토큰 키를 직접 생성하였으며, 이를 `.env` 및 `supabaseClient.ts`에 동기화 매핑하여 에러를 원천 제거했습니다.

### 1.2. [🔴 P0] Mock User(베타 테스터) 잔재 제거 및 상태 누수 해결
*   **기본값 정리:** `useWorkflowStore.ts`의 `userId` 기본값 `'beta_tester'`를 빈 문자열(`''`)로 변경하고, `setUser(null)` 호출 시 `userId` 역시 빈 문자열로 매핑되게 정비했습니다.
*   **하이드레이션 가드 추가:** `AuthProvider.tsx`에서 하이드레이션 상태인 `hasHydrated`가 `false` 이거나 `isAuthLoading` 상태일 때 화면 전체를 강제 로더 차단하여 유령 세션 일시 노출을 방지했습니다.
*   **로그아웃 멸균:** `handleLogout` 실행 시 스토어 내 유저 정보(`user`, `userId`) 및 API Key 상태(`kieKey`, `isKeyConfigured`, `csrfToken`)를 전부 리셋하고 `localStorage`를 직접 완전 삭제함으로써 상태 누수를 완벽 해결했습니다.

### 1.3. [🔴 P0] 회원가입 중복 (User Already Exists) 한글 경고
*   **에러 핸들링:** Supabase Auth 회원가입 중 발생하는 `User already registered` 에러를 캐치하는 로직에 `.toLowerCase().includes("already") || .toLowerCase().includes("registered")` 방어 가드를 이식하여 사용자에게 **"이미 사용 중인 이메일입니다."**라는 명확한 한글 경고가 표출되도록 조치했습니다.

### 1.4. [🔴 P0] 로그인/설정 모달 z-index 레이어 교정
*   **z-index 계층 분리:** 헤더 프로필 wrapper의 z-index를 `z-[40]`으로, 글로벌 세팅 버튼을 `z-[45]`로 하향 조정하고, 대시보드 모달 wrapper의 z-index를 `z-[1000]`으로 대폭 상향하여 CLOSE 버튼 등이 겹치는 현상을 해결했습니다.
*   **비밀번호 폼 리셋:** 비밀번호 입력 필드는 회원가입/로그인 시도 성공/실패 시 및 모드 전환 시 즉시 비워지도록 선별 리셋 로직을 배치하여 사용자 타이핑 방해 요소를 제거하고 보안을 강화했습니다.

### 1.5. [🔴 P1] 사후 리뷰 보고서 자동 생성 복구 및 격리
*   **태스크 분리:** `main.py` 내의 사후 리뷰 로직을 비동기 백그라운드 태스크 `generate_post_review_report_task`로 완전히 분리하고, 내부를 `try-except`로 단단히 감싸 실패 시에도 백엔드가 죽지 않도록 격리했습니다.
*   **자동 트리거:** `/api/render-stream` 엔드포인트의 최종 비디오 렌더링 및 자산 기록이 끝나는 시점에 FastAPI `BackgroundTasks`를 통해 사후 리뷰 보고서가 자동 생성되도록 연동하고, 기존 UI 상의 땜빵 버튼은 철거했습니다.

---

## 2. 검증 결과

### 2.1. 백엔드 API 매핑 테스트 (pytest)
- `python -m pytest tests/test_project_task_mapping.py`
- 결과: **5 Passed** (100% 성공)

### 2.2. E2E 자동화 수동 검증 (Playwright)
Playwright 브라우저 E2E 검증(`temp_zip_check/e2e_test.js`)을 진행하여 다음과 같은 결과를 직접 캡처 및 로그로 확인했습니다.
1. **하이드레이션 가드 검증**: 새로고침 시 이메일 폼 및 Mock User의 잔재 유입 없이 로더 창이 단단하게 가드해 줍니다.
2. **z-index 및 UI 겹침 소멸 검증**: 대시보드 모달(`z-[1000]`)이 열렸을 때 프로필 버튼(`z-[40]`) 및 세팅 버튼(`z-[45]`)이 모달 뒤로 완벽히 격리되어 CLOSE 버튼 겹침 문제가 발생하지 않습니다.
3. **이메일 중복 한글 경고 검증**: 중복 이메일 회원가입 시도 시 **"이미 사용 중인 이메일입니다."**라는 한글 에러가 정상 도출됩니다.
4. **로그아웃 멸균 검증**: 로그아웃 버튼을 누른 즉시 Zustand Store의 `user`, `userId` 및 API Key 상태가 전부 초기화되고 `localStorage`가 완전히 지워집니다.
