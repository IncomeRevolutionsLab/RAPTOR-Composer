이제 충분한 정보를 확보했습니다. 보고서를 작성하겠습니다.

---

# 📋 RAPTOR v2.14.3-ux-fix 회원가입 UX 보완 사후 리뷰 보고서 (Post-Review)

> 기준 파일: `src/components/AuthDashboard.tsx` (668줄), `main.py` (L629–L680)
> 리뷰 기준일: 2026-06-10

---

## 1. [P1-UX] 이메일 인증 흐름 정상화 평가

### ✅ PASS — 회원가입 후 미인증 대시보드 진입 차단

`AuthDashboard.tsx:177–198`의 회원가입 성공 분기를 확인한 결과, `setUser()` 및 `setIsModalOpen(true)` 호출이 완전히 제거되어 있다.

```tsx
// L194–197: 실제 코드 확인
setAuthSuccess("가입하신 이메일로 인증 메일이 발송되었습니다...");
setPassword('');
setEmail('');
// setUser(data.user) → 없음 ✅
// setIsModalOpen(true) → 없음 ✅
```

`isModalOpen`이 `false`인 상태이므로, `user` 객체도 `null`이고, Logged-In Workspace 뷰는 렌더링되지 않는다. **프론트엔드 레벨의 미인증 진입 차단은 완전히 작동한다.**

---

### ⚠️ CONDITIONAL PASS — 이메일 미확인 상태 로그인 시 사용자 경험

`main.py:656–680`의 `/api/auth/signin` 엔드포인트를 확인한 결과, **`email_confirmed_at` 검증 로직이 존재하지 않는다.**

```python
# main.py:L656–678: 실제 코드
@app.post("/api/auth/signin")
async def auth_signin(req: AuthRequest):
    url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
    # ... Supabase 직접 프록시, email_confirmed_at 체크 없음
    resp = await client.post(url, headers=headers, json=data, timeout=10.0)
    resp_data = resp.json()
    if resp.status_code != 200:
        raise HTTPException(...)
    return resp_data  # email_confirmed_at 검증 없이 토큰 반환
```

**현재 보호 수준은 Supabase 콘솔의 "Email confirmations required" 설정에 전적으로 의존한다.** Supabase에서 이 옵션이 켜져 있으면 `/auth/v1/token?grant_type=password` 자체가 `400 Email not confirmed` 에러를 반환하므로 우회가 차단된다. 그러나 이것은 인프라 설정값에 의존하는 묵시적 가드이며, 코드 레벨의 명시적 보호가 아니다.

**이메일 미확인 상태로 로그인 시도할 경우 사용자가 받는 에러 메시지는 `AuthDashboard.tsx:208`의 일반 `credentials` 분기에 매핑되어 "이메일 또는 비밀번호가 올바르지 않습니다."로 표시된다.** 실제 원인(이메일 미인증)을 설명하지 않으므로 사용자가 비밀번호를 반복 시도하는 혼란을 유발할 수 있다.

**권고:** `auth_signin` 백엔드에서 Supabase 응답의 `error_description`이 `"Email not confirmed"` 등을 포함할 때 전용 에러 메시지를 반환하거나, 프론트엔드 에러 매핑(`AuthDashboard.tsx:202–211`)에 `email not confirmed` 케이스를 추가할 것.

---

### ✅ PASS — 인증 안내 메시지 명확성

성공 메시지(`L195`)는 "인증 메일이 발송되었습니다. 메일함의 인증 링크를 클릭하여 가입을 완료해 주세요."로, 사용자가 취해야 할 다음 행동을 명확히 안내하고 있다. 이메일 필드도 클리어(`setEmail('')`)되어 성공 상태임을 시각적으로 확인시킨다.

---

## 2. [P1-법적] 약관 동의 고지 평가

### ⚠️ CONDITIONAL PASS — 고지 문구의 법적 충분성

`AuthDashboard.tsx:399–407` 구현을 확인했다.

```tsx
{!isLoginMode && !isForgotPasswordMode && (
  <p className="text-[10px] text-gray-500 ...">
    가입 시 랩터 숏폼 메이커의{' '}
    <span className="text-purple-400">이용약관</span> 및{' '}
    <span className="text-purple-400">개인정보 처리방침</span>에
    동의하는 것으로 간주됩니다.
  </p>
)}
```

조건부 렌더링 로직은 정확하다(회원가입 모드에서만 표시). 그러나 `<span>` 태그만 사용하고 있어 **실제 약관 페이지로 이동하는 `<a>` 링크가 없다.** 한국 개인정보보호법(제22조) 및 정보통신망법(제26조) 관점에서 다음 위험이 존재한다:

| 항목 | 현재 상태 | 리스크 |
|---|---|---|
| 약관 고지 문구 표시 | ✅ 있음 | — |
| 약관 전문 접근 경로 | ❌ 없음 | 중간: 이용자가 약관 내용을 확인할 방법 없음 |
| 개인정보처리방침 링크 | ❌ 없음 | 높음: 개인정보보호법 시행령 제30조 위반 소지 |
| 서비스 명칭 일치 | "랩터 숏폼 메이커" | 낮음: 공식 서비스명 확인 필요 |

**권고:** 최소한 이용약관과 개인정보처리방침 페이지(`/terms`, `/privacy`)를 생성하고, 해당 텍스트를 `<a href="/terms">` 링크로 변경해야 한다. 현재 `<span>` 상태는 법적 고지 의무의 절차적 요건만 최소 충족하는 수준이다.

---

## 3. [P1-UI] 에러/성공 메시지 반응형 UI 픽스 평가

### ✅ PASS — 텍스트 오버플로우 해소 여부

`AuthDashboard.tsx:348–360` 에러/성공 박스 모두 동일하게 수정되어 있다.

```tsx
// 에러 박스 L349
<div className="... flex items-start gap-2 w-full max-w-md"
     style={{zIndex: 10, wordBreak: 'break-word', overflowWrap: 'break-word'}}>
  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
  <div className="break-words min-w-0 flex-1">{authError}</div>
</div>
```

`min-w-0 flex-1` 조합으로 flex 자식의 width collapse 문제가 해결되었고, `w-full max-w-md` 로 컨테이너 너비가 제한되어 소형 화면에서 클리핑 문제가 해소되었다. 성공 박스(`L355–360`)에도 동일 패턴이 적용되어 일관성이 있다.

---

### ⚠️ MINOR — 스타일 중복 적용 적절성 평가

인라인 `style={{wordBreak: 'break-word', overflowWrap: 'break-word'}}`와 Tailwind `break-words` 클래스가 **동시에 적용**되어 있다.

- Tailwind `break-words`는 `overflow-wrap: break-word`를 생성한다.
- 인라인 스타일의 `overflowWrap: 'break-word'`는 동일한 CSS 속성이다.
- CSS 우선순위상 인라인 스타일이 Tailwind를 덮어쓰므로 최종 결과는 동일하다.

기능적 중복이므로 즉각적인 버그는 없으나, 유지보수 측면에서 인라인 스타일 또는 Tailwind 중 하나를 제거하는 것이 권장된다. `zIndex: 10`은 Tailwind `z-10` 클래스로 대체 가능하다.

---

### ⚠️ MINOR — 아이콘-텍스트 정렬 불일치 가능성

`items-start` 변경으로 아이콘에 `mt-0.5`가 추가되었으나, 한 줄짜리 짧은 에러 메시지(`"로그인에 실패했습니다."` 등) 시 아이콘이 텍스트 중앙 대신 상단에 고정되어 시각적 불일치가 발생할 수 있다. 긴 메시지(인증 안내 메시지처럼 두 줄 이상)에서는 `items-start`가 더 자연스럽다. 타협안으로 `items-baseline`을 검토할 수 있다.

---

## 4. 잠재적 신규 위험 요소

### ⚠️ RISK-1 — authSuccess 상태의 모달 재오픈 시 잔존

`handleAuthSubmit`(L94–95)에서 `setAuthSuccess(null)` 초기화가 수행되고, 모드 전환 버튼에서도 초기화된다. 그러나 **모달 닫기(`setIsModalOpen(false)`) 시 `authSuccess`를 초기화하는 로직이 없다.**

```tsx
// L311: 모달 백드롭 클릭 시 닫기
onClick={() => { setIsModalOpen(false); setPreviewVideoUrl(null); }}
// authSuccess 초기화 없음 → 재오픈 시 이전 성공 메시지 잔존
```

실제 시나리오: 사용자가 회원가입 후 성공 메시지를 보고 모달을 닫았다가 다시 열면, "가입하신 이메일로 인증 메일이 발송되었습니다" 메시지가 여전히 표시된다. 혼란스럽지만 크리티컬한 버그는 아니다.

**권고:** `setIsModalOpen(false)` 호출 위치 두 곳(L311, L323)에 `setAuthSuccess(null); setAuthError(null);` 추가.

---

### ⚠️ RISK-2 — 회원가입 블록 내 불필요한 resetWorkflow() 호출

`AuthDashboard.tsx:191–192`에서 회원가입 성공 시에도 `resetWorkflow()`가 호출된다.

```tsx
if (store.userId !== data.user.id || localUserId !== data.user.id) {
  store.resetWorkflow(); // 미인증 신규 유저에게도 실행됨
}
```

신규 가입 유저는 `store.userId`가 존재하지 않으므로 이 조건은 항상 `true`가 되어 `resetWorkflow()`가 실행된다. 현재는 빈 store를 초기화하는 것이므로 무해하지만, 추후 가입 전 guest-mode 작업이 추가될 경우 데이터 유실 위험이 있다.

---

### ✅ PASS — 중복 가입 시도 에러 처리

`AuthDashboard.tsx:206–207`에 이미 처리되어 있다.

```tsx
} else if (errLower.includes("already") || errLower.includes("registered")) {
  displayError = "이미 사용 중인 이메일입니다.";
}
```

Supabase의 중복 가입 에러는 `"User already registered"` 형태로 반환되므로 `"registered"` 패턴에 매핑되어 정상 처리된다. 이메일/비밀번호 폼 클리어 후 사용자는 새 이메일을 입력하거나 로그인 모드로 전환 가능하다.

---

## 5. TDD 채점표

| # | 검증 항목 | 결과 | 비고 |
|---|---|---|---|
| T-01 | 회원가입 성공 시 `setUser()` 미호출 → 대시보드 진입 차단 | ✅ PASS | L177–198 확인 |
| T-02 | 회원가입 성공 시 `setIsModalOpen(true)` 미호출 | ✅ PASS | 제거 확인 |
| T-03 | 인증 안내 메시지 표시 명확성 | ✅ PASS | L195 확인 |
| T-04 | 회원가입 성공 후 이메일/비밀번호 필드 클리어 | ✅ PASS | L196–197 확인 |
| T-05 | 백엔드 `/api/auth/signin` email_confirmed_at 가드 | ⚠️ CONDITIONAL | Supabase 설정 의존 |
| T-06 | 이메일 미인증 로그인 시 명확한 에러 메시지 | ❌ FAIL | "비밀번호 오류"로 오인 유도 |
| T-07 | 약관 동의 문구 회원가입 모드에서만 표시 | ✅ PASS | L400 조건 정확 |
| T-08 | 약관 전문 접근 링크 제공 | ❌ FAIL | `<span>` 링크 없음 |
| T-09 | 에러 박스 텍스트 오버플로우 해소 | ✅ PASS | L349–352 확인 |
| T-10 | 성공 박스 텍스트 오버플로우 해소 | ✅ PASS | L355–360 확인 |
| T-11 | 에러/성공 박스 반응형 너비 제한 | ✅ PASS | `w-full max-w-md` 확인 |
| T-12 | 중복 가입 시도 에러 처리 | ✅ PASS | L206 매핑 확인 |
| T-13 | authSuccess 모달 재오픈 시 초기화 | ❌ FAIL | 닫기 이벤트에 초기화 없음 |
| T-14 | 스타일 중복 적용 적절성 | ⚠️ MINOR | 기능적 무해, 코드 품질 이슈 |

**합계: PASS 9 / FAIL 3 / CONDITIONAL 1 / MINOR 1**

---

## 6. 최종 결론 및 잔여 권고사항

### 결론

v2.14.3의 3개 P1 패치 중 **[P1-UX] 이메일 인증 흐름 정상화**와 **[P1-UI] 반응형 UI 픽스**는 목표를 달성했다. `[P1-법적] 약관 동의 고지`는 고지 문구 추가라는 최소 요건은 충족했으나, 실질적인 법적 보호 수준에는 미치지 못한다.

### 우선순위별 잔여 권고사항

**P1 (즉시 처리 권장):**

1. **이메일 미인증 로그인 에러 메시지 개선** — `main.py`의 `auth_signin`에서 Supabase 에러 응답의 `error_description`이 `"Email not confirmed"`일 때 명시적 메시지(`"이메일 인증이 완료되지 않았습니다. 가입 시 발송된 인증 메일을 확인해 주세요."`)를 반환하거나, 프론트엔드 에러 매핑에 해당 케이스를 추가할 것.

2. **약관 링크 추가** — `<span className="text-purple-400">이용약관</span>`을 `<a href="/terms" ...>이용약관</a>`으로 변경하고 최소한의 이용약관/개인정보처리방침 페이지를 생성할 것. 없을 경우 개인정보보호법 의무 고지 요건 미충족.

**P2 (다음 스프린트 처리):**

3. **모달 닫기 시 authSuccess/authError 초기화** — `setIsModalOpen(false)` 호출 2곳에 상태 초기화 추가.

4. **인라인 스타일 중복 제거** — `style={{zIndex: 10, wordBreak: 'break-word', overflowWrap: 'break-word'}}`를 Tailwind 클래스 `z-10 break-words`로 대체.

5. **회원가입 블록 내 `resetWorkflow()` 조건 재검토** — 현재는 무해하나, guest-mode 작업 추가 전에 정리 필요.
