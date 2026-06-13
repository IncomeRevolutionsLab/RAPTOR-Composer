# Claude Code Raw Output — Pre-Review (Loop 1)
> **저장 일시**: 2026-06-11T18:15:20Z
> **리뷰 실행 명령**: `echo "[수정된 설계 계획 v2]" | claude -p --output-format text`
> **원칙**: 제7원칙에 따라 단 한 글자도 편집하지 않은 Raw Output 원문
> **Task ID**: `c65b8cac-461a-4f35-8ece-ea43ea293d87/task-326`
> **리뷰 단계**: Step 2 Pre-Review (루프 1회차) — v2.16.0 새 비밀번호 설정 UI (P0 Fix 반영)

---

## ⚠️ 원문 무결성 고지

이 파일은 `claude -p` 터미널 실행 결과의 **무편집 원문**입니다.

---

## Raw Output (원문)

```
리뷰 보고서 파일 접근 권한이 없어서, 현재 코드 분석과 스펙을 기반으로 Loop1 사전 리뷰를 직접 수행하겠습니다.

---

# RAPTOR v2.16.0 Loop1 사전 리뷰 보고서 (Pre-Review)

**날짜:** 2026-06-12  
**버전:** v2.16.0 — Password Update Mode (Recovery Flow P0 Fix)  
**리뷰어:** Claude Code  

---

## 1. P0 Fix 타당성: `setUser` 지연 → Auth View 라우팅 오류 방지

**현행 코드 문제점 (현재 `handleVerifyOtp`, line 276):**
```ts
// otpPurpose === 'recovery' 분기 없이 무조건 실행됨
setUser(data.user);           // → user가 truthy됨
setOtpMode(false);            // → Auth View 조건: !user === false → Workspace로 전환
setTimeout(() => setIsModalOpen(true), 400);
```

Auth View의 조건 분기 (`line 611`):
```tsx
{!user ? (
  /* LOGGED OUT VIEW — 여기서 비밀번호 업데이트 폼이 있어야 함 */
) : (
  /* LOGGED IN WORKSPACE */
)}
```

`setUser(data.user)` 호출 즉시 `user`가 truthy가 되어 Auth View(`!user` 브랜치)가 사라지고, Workspace로 전환됨 → **비밀번호 업데이트 폼을 렌더할 기회 없음.** P0 근본 원인 확인.

**제안 Fix 타당성:**
- `recovery`일 때 `setRecoveryUser(data.user)` (별도 state) + `setUpdatePasswordMode(true)` 후 `setUser()` 호출 안 함
- `user === null` 유지 → Auth View (`!user`) 브랜치 계속 렌더됨
- `updatePasswordMode === true`로 분기해 비밀번호 입력 폼 표시

> **평가: ✅ PASS** — 근본 원인 정확히 진단됨. `user` state를 분리함으로써 라우팅 충돌 없이 비밀번호 업데이트 UI를 Auth View 내에서 표시 가능.

---

## 2. `setSession()` → `updateUser()` 타이밍 안전성

**흐름:**
1. `handleVerifyOtp`: `verifyOtp({type:'recovery'})` → `data.session` 존재 시 `await supabase.auth.setSession({access_token, refresh_token})`
2. 이후 사용자가 새 비밀번호 입력 → `handleUpdatePassword` 호출
3. `handleUpdatePassword`: `supabase.auth.updateUser({password: newPassword})`

**검토 포인트:**

| 케이스 | 결과 |
|--------|------|
| `data.session` 있음 + `setSession` await 완료 | Supabase 클라이언트에 세션 세팅됨 → `updateUser()` 인증 성공 ✅ |
| `data.session` 없음 (null) | `setSession` 미호출 → `updateUser()` 401 실패 ❗ |
| `setSession` 미완료(await 누락) 상태에서 `updateUser` | Race condition으로 401 실패 ❗ |

**리스크:**  
- `data.session`이 null인 경우에 대한 처리 필요. `verifyOtp('recovery')`는 Supabase에서 세션을 반환하지만, 이메일 설정에 따라 null이 올 수 있음.
- `handleVerifyOtp`에서 `setSession`은 반드시 `await`으로 호출해야 함.

> **평가: ⚠️ CONDITIONAL_PASS** — `await setSession()` 이후 `setUpdatePasswordMode(true)` 순서가 코드에서 보장되어야 함. `data.session === null` 케이스에 대한 에러 처리 필요 (사용자에게 에러 표시 후 재시도 유도).

---

## 3. `handleCancelUpdatePassword` — `signOut()` 타이밍

**제안 로직:**
```ts
await supabase.auth.signOut();  // Recovery 세션 정리
// state 초기화 (updatePasswordMode, newPassword, etc.)
// 로그인 화면으로 복귀
```

**검토 포인트:**
- `setSession()` 호출로 Supabase 클라이언트에 세션이 이미 세팅되어 있음 → `signOut()` 없이 취소하면 Recovery 세션이 남아서 의도치 않은 인증 상태 지속 가능
- `signOut()` 실패 케이스(네트워크 에러 등): `try-catch`로 감싸되 **실패해도 state 초기화는 반드시 수행**해야 함 (finally 블록 사용 권고)
- `signOut()` 후 state 초기화 순서는 문제 없음 (signOut은 서버 호출이므로 결과에 무관하게 클라이언트 state는 정리해야 함)

> **평가: ✅ PASS** — 설계 방향 정확. 구현 시 `try-finally` 패턴 적용하여 `signOut()` 실패에도 state 클리어 보장 필요.

---

## 4. `recoveryUser`를 React state에 저장하는 것의 안전성

**저장 대상:** `supabase.auth.verifyOtp()` 반환 `data.user` (Supabase `User` 객체)

**포함 정보:**
- `id`, `email`, `created_at`, `app_metadata`, `user_metadata` 등
- **패스워드 미포함** (Supabase는 비밀번호를 클라이언트에 반환하지 않음)
- Access/Refresh Token은 `data.session`에 있으며 별도 state 저장 불필요 (Supabase 클라이언트가 관리)

**보안 평가:**
- React state는 메모리에만 존재, localStorage/sessionStorage 미저장 → 탭 닫기/새로고침 시 자동 소멸
- `handleLogout`에서 `setRecoveryUser(null)` 포함 필요 (스펙에 명시됨) → P2 상태 클리어
- 별도 state 없이 `data.user`를 `handleUpdatePassword` 클로저에 포함하는 방법도 있지만, state 사용이 React 패턴상 더 명확함

> **평가: ✅ PASS** — 적절한 방식. 단, `handleLogout` 및 `handleCancelUpdatePassword`에서 반드시 `setRecoveryUser(null)` 포함 확인 필요.

---

## 5. 추가 보안 우려사항

### 5-1. 비밀번호 검증 (handleUpdatePassword)
스펙에서 "6자 이상 + 확인 일치" 언급. 추가 권고:
- `newPassword !== newPasswordConfirm` 조건을 **서버 전송 전** 클라이언트 검증으로 처리 (✅ 스펙 포함)
- 빈 문자열 비밀번호 제출 방어 (trim() 주의 — 비밀번호에 trim 금지)
- `updatePasswordLoading === true` 중 중복 제출 방지 (disabled 처리 필요)

### 5-2. `handleUpdatePassword` 성공 후 세션 상태
`supabase.auth.updateUser()` 성공 → Supabase가 새 세션 발급 → `setUser(recoveryUser)` 호출.  
**주의:** `updateUser()` 이후 Supabase 클라이언트가 세션을 갱신하므로, `recoveryUser` 대신 `supabase.auth.getUser()` 결과를 사용하는 것이 더 정확할 수 있음. (`recoveryUser`는 비밀번호 변경 전 시점의 user 객체)

### 5-3. OTP 재사용 방지
Supabase `verifyOtp`는 단일 사용 OTP이므로 Supabase 서버에서 이미 처리됨. 별도 클라이언트 처리 불필요.

### 5-4. `updatePasswordMode` 중 뒤로가기 처리
`updatePasswordMode === true`인 상태에서 사용자가 모달을 닫으면 (`onClick={() => setIsModalOpen(false)}`), Recovery 세션이 정리되지 않음.  
→ 모달 close 핸들러에서도 `updatePasswordMode` 확인 후 `signOut()` + 상태 초기화 처리 권고.

> **평가: ⚠️ CONDITIONAL_PASS** — 모달 강제 닫기 시 Recovery 세션 누수 방지 로직 추가 필요.

---

## 6. 종합 평가 요약

| # | 리뷰 항목 | 평가 | 비고 |
|---|-----------|------|------|
| 1 | P0 Fix: `setUser` 지연 → Auth View 라우팅 방지 | ✅ **PASS** | 근본 원인 정확히 해결 |
| 2 | `setSession()` → `updateUser()` 타이밍 안전성 | ⚠️ **CONDITIONAL_PASS** | `data.session === null` 에러 처리 + `await` 보장 필요 |
| 3 | `handleCancelUpdatePassword` `signOut()` 타이밍 | ✅ **PASS** | `try-finally` 패턴 적용 시 안전 |
| 4 | `recoveryUser` state 저장 안전성 | ✅ **PASS** | 모든 exit path에서 null 클리어 확인 필요 |
| 5 | 추가 보안 우려 | ⚠️ **CONDITIONAL_PASS** | 모달 강제 닫기 시 세션 누수 방지 처리 추가 권고 |

**전체 판정: ⚠️ CONDITIONAL_PASS → 구현 진행 가능 (조건부 승인)**

구현 시 반드시 반영할 조건:
1. `handleVerifyOtp` recovery 분기에서 `data.session === null` 에러 핸들링 추가
2. `setSession()` 반드시 `await` 처리
3. 모달 close 핸들러에서 `updatePasswordMode === true` 시 Recovery 세션 정리 로직 추가
4. `handleUpdatePassword` 성공 후 `setUser(recoveryUser)` 대신 `supabase.auth.getUser()` 재호출 검토

---

구현 진행할까요? 위 조건을 반영하여 `AuthDashboard.tsx`를 수정하겠습니다.
```

---

## 실행 컨텍스트

| 항목 | 내용 |
|------|------|
| 실행 시각 | 2026-06-11T18:12:43Z |
| 명령 | `echo "[수정 계획 v2 전문]" \| claude -p --output-format text` |
| 리뷰 단계 | Step 2 Pre-Review (루프 1회차) |
| Task ID | `c65b8cac-461a-4f35-8ece-ea43ea293d87/task-326` |
