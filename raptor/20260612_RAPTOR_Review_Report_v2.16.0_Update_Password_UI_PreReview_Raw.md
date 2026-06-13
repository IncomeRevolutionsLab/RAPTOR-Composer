# Claude Code Raw Output — Pre-Review (v2, 계획서 전용 재실행)
> **저장 일시**: 2026-06-11T18:03:01Z
> **리뷰 실행 명령**: `echo "[계획서 전문 — 파일 없이]" | claude -p --output-format text`
> **원칙**: 제7원칙에 따라 단 한 글자도 편집하지 않은 Raw Output 원문
> **Task ID**: `c65b8cac-461a-4f35-8ece-ea43ea293d87/task-314`
> **리뷰 단계**: Step 2 Pre-Review (v2 재실행) — v2.16.0 새 비밀번호 설정 UI 구현

---

## ⚠️ 원문 무결성 고지

이 파일은 `claude -p` 터미널 실행 결과의 **무편집 원문**입니다.
Antigravity의 해석, 요약, 추가 설명이 일절 포함되지 않았습니다.

---

## Raw Output (원문)

```
현재 코드를 모두 파악했습니다. v2.16.0 사전 리뷰를 작성합니다.

---

## 📋 RAPTOR v2.16.0 사전 리뷰 (Pre-Review)
**리뷰 대상:** 비밀번호 재설정 UX 개선 및 Recovery 플로우 UI 픽스  
**날짜:** 2026-06-12  
**판정:** **FAIL** — P0 설계 결함 발견, 구현 전 수정 필요

---

### ⚠️ [P0] 치명적 렌더링 충돌 — `setUser` vs `updatePasswordMode` 공존 불가

**문제:**  
현재 `AuthDashboard` UI 구조는 `!user` 조건으로 Auth View 전체를 분기한다 (line 611):

```tsx
{!user ? (
  // Auth View — OTP 폼, 로그인 폼, updatePasswordMode UI가 여기 들어감
) : (
  // Logged In Workspace
)}
```

계획된 `handleVerifyOtp` 수정:
```
otpPurpose==='recovery' → setUser(data.user) + setOtpMode(false) + setUpdatePasswordMode(true)
```

`setUser(data.user)`를 호출하는 순간 `user !== null`이 되어 Auth View 전체가 언마운트됨.  
`updatePasswordMode`가 `true`여도 표시될 화면이 없어진다. **사용자는 비밀번호를 입력하지도 않고 즉시 로그인된 대시보드 화면이 열린다.**

**올바른 설계:**  
Recovery OTP 인증 성공 시 `setUser()` 호출을 비밀번호 변경 완료까지 지연시켜야 한다.

```ts
// handleVerifyOtp — recovery 분기
if (otpPurpose === 'recovery') {
  // ✅ setUser 호출 없이 일시 보류
  setRecoverySession(data.session ?? null);  // 세션 임시 보관 (또는 SDK 자동 보관)
  setOtpMode(false);
  setUpdatePasswordMode(true);
  return;
}
// 기존 signup 분기
setUser(data.user);
setOtpMode(false);
...
```

`handleUpdatePassword` 성공 후:
```ts
setUser(data.user ?? recoverySession?.user);
setUpdatePasswordMode(false);
setIsModalOpen(true);
```

---

### 🔴 [P1] Supabase Recovery OTP vs Magic Link 불확실성

**문제:**  
`resetPasswordForEmail(email, { redirectTo: window.location.origin })` 호출 시, Supabase 프로젝트 이메일 템플릿 설정에 따라 **6자리 OTP** 또는 **매직링크(URL 토큰)** 중 하나가 발송된다.

현재 코드는 6자리 OTP 입력 UI만 준비되어 있으므로, 만약 Supabase가 매직링크를 보내면 사용자는 코드를 입력할 방법이 없어 **Dead-end** 발생.

**확인 필요:**  
Supabase 대시보드 → Authentication → Email Templates → "Reset Password" 템플릿이 OTP 방식(`{{ .Token }}` 변수)으로 설정되어 있는지 검증 필요. 현재 프로덕션에서 실제 이메일 수신 후 확인 권장.

---

### 🔴 [P1] `verifyOtp(type:'recovery')` 후 세션 연속성 — `data.session` 처리

**문제:**  
`supabase.auth.verifyOtp()` 성공 시 `data = { user, session }` 반환. Supabase SDK는 내부적으로 세션을 자동 저장하지만, 현재 코드는 `data.user`만 참조한다.

`handleUpdatePassword`에서 `supabase.auth.updateUser({password})` 호출 시 현재 세션의 액세스 토큰이 필요하다. SDK 내부 세션이 올바르게 설정되지 않았다면 401 발생 가능.

**권고:**  
`verifyOtp` 성공 직후 `data.session`이 존재하는 경우 명시적으로 세션 설정:
```ts
if (data.session) {
  await supabase.auth.setSession({
    access_token: data.session.access_token,
    refresh_token: data.session.refresh_token,
  });
}
```

---

### 🟡 [P2] `updatePasswordMode` 취소 시 세션 정리 누락

Recovery OTP 인증 완료 후 (`setUpdatePasswordMode(true)` 상태에서) 사용자가 뒤로 가거나 취소하면, Supabase에는 Recovery 세션이 수립된 채로 남는다. 이 세션으로 언제든 `updateUser()`가 호출 가능해지는 문제.

**권고:**  
취소 버튼 핸들러에서 `supabase.auth.signOut()` 또는 세션 초기화 후 `updatePasswordMode(false)` + 로그인 화면 복귀.

---

### 🟡 [P2] `handleLogout` 상태 리셋 누락 (계획상)

7개의 신규 상태 변수가 추가될 예정인데, `handleLogout` (line 486-509)에 이들 리셋 코드가 누락될 경우, 로그아웃 후 재접속 시 `updatePasswordMode=true` 상태가 잔류할 수 있다.

**권고:** 로그아웃 핸들러에 반드시 포함:
```ts
setUpdatePasswordMode(false);
setNewPassword('');
setNewPasswordConfirm('');
setUpdatePasswordError(null);
```

---

### 🟡 [P2] 비밀번호 변경 후 다른 디바이스 세션 무효화

`supabase.auth.updateUser({password})` 호출은 현재 세션만 유효하고, 다른 디바이스의 기존 세션을 자동 무효화하지 않는다. 보안상 비밀번호 변경 후 모든 세션 강제 로그아웃이 권장됨.

**확인 필요:** Supabase 최신 버전에서 `signOut({ scope: 'others' })` 지원 여부 확인 후 `handleUpdatePassword` 성공 핸들러에 추가 검토.

---

### 🟢 [P3] 비밀번호 정책 (낮은 우선순위)

현재 6자 최소 제한만 적용. 비밀번호 재설정이라는 보안 민감 컨텍스트에서 특수문자/대소문자 혼합 정책 추가를 장기적으로 고려.

---

### 구현 권고 순서

```
1. [P0] handleVerifyOtp — recovery 분기에서 setUser 호출 제거
         + 임시 세션/user 상태 보관 방식 결정
2. [P1] verifyOtp 성공 후 data.session 명시적 setSession 호출
3. [P1] Supabase 이메일 템플릿 OTP 방식 확인 (환경 검증)
4. [P2] handleUpdatePassword 성공 후 setUser 호출
5. [P2] 취소 핸들러 + 세션 정리
6. [P2] handleLogout 신규 상태 7개 리셋
```

---

### 판정 요약

| 항목 | 등급 | 결론 |
|---|---|---|
| setUser+updatePasswordMode 렌더링 충돌 | P0 | 계획 수정 필수 |
| Supabase OTP/매직링크 불확실성 | P1 | 환경 검증 필수 |
| data.session 명시적 처리 | P1 | 구현 시 포함 |
| 취소 시 세션 정리 | P2 | 구현 시 포함 |
| 로그아웃 상태 리셋 | P2 | 구현 시 포함 |
| 다중 세션 무효화 | P2 | 장기 검토 |

**최종 판정: `FAIL`**  
P0 설계 결함(`setUser` 호출 시점)으로 인해 계획대로 구현하면 비밀번호 입력 UI가 렌더링되지 않는다. `handleVerifyOtp` recovery 분기에서 `setUser` 호출을 `handleUpdatePassword` 성공 시점으로 이동하는 설계 수정 후 재검토 필요.
```

---

## 실행 컨텍스트

| 항목 | 내용 |
|------|------|
| 실행 시각 | 2026-06-11T18:00:43Z |
| 명령 | `echo "[계획서 전용 — 파일 없이]" \| claude -p --output-format text` |
| 리뷰 단계 | Step 2 Pre-Review (v2 재실행) |
| Task ID | `c65b8cac-461a-4f35-8ece-ea43ea293d87/task-314` |
