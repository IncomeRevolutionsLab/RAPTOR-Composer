# Claude Code Review — AuthDashboard.tsx v2.14.5
> **리뷰어**: Claude Code v2.1.118  
> **대상 파일**: `src/components/AuthDashboard.tsx`  
> **리뷰 일시**: 2026-06-11  
> **발견 이슈**: 총 13개 (높음 5 / 중간 7 / 낮음 2)

---

## A. 보안 취약점

### 🔴 [높음] 대시보드 API — IDOR 취약점 (인증 헤더 없음)
`fetchDashboardData`에서 `user_id`를 쿼리 파라미터로만 전달하고 Authorization 헤더가 없어, 공격자가 타인의 `user_id`를 추측해 데이터 조회 가능.

```tsx
// 수정 전 (취약)
const res = await fetch(`${BACKEND_URL}/api/dashboard/projects?user_id=${user.id}`);

// 수정 후 — Supabase 세션 토큰 헤더 추가
const { data: sessionData } = await supabase.auth.getSession();
const accessToken = sessionData?.session?.access_token;
const res = await fetch(`${BACKEND_URL}/api/dashboard/projects?user_id=${user.id}`, {
  headers: {
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  },
});
```

---

### 🔴 [높음] alert()가 내부 에러 메시지 원문을 그대로 노출
`handleAuthSubmit` 내 `resetPasswordForEmail` 실패 시 Supabase 내부 에러 메시지(서버 구조, 환경변수 힌트 등)가 `alert()`로 사용자에게 직접 노출됨.

```tsx
// 수정 후 — 내부 메시지 숨기고 안전한 분기 처리
if (error) {
  const isConfigError =
    error.message.toLowerCase().includes('invalid api key') ||
    error.message.toLowerCase().includes('api key') ||
    error.message.toLowerCase().includes('unauthorized') ||
    (error.status ?? 0) === 401;
  setAuthError(
    isConfigError
      ? '비밀번호 재설정을 처리할 수 없습니다. 관리자에게 문의해 주세요.'
      : '비밀번호 재설정 이메일 발송에 실패했습니다. 잠시 후 다시 시도해 주세요.'
  );
} else {
  setAuthSuccess("비밀번호 재설정 이메일이 발송되었습니다. 이메일을 확인해 주세요.");
}
```

---

### 🟢 [낮음] 미사용 import — `api`
`L7`: `api`가 import되지만 파일 전체에서 사용되지 않음. 제거 필요.

```tsx
// 제거 대상
import { api } from '@/lib/api-client';
```

---

## B. UX 엣지케이스

### 🔴 [높음] alert() 남용 — Toast 시스템과 불일치
`handleSaveKey`, `handleDownloadVideo` 3곳에서 `alert()` 사용. Toast 기반 UX와 혼용되어 일관성 파괴.

```tsx
// handleSaveKey 수정
const handleSaveKey = async () => {
  if (!kieKey.trim()) {
    setToast({
      message: isKeyConfigured
        ? '이미 API 키가 구성되어 있습니다. 변경하시려면 새 키를 입력해 주세요.'
        : 'KIE API Key를 입력해 주세요.',
      type: 'error',
    });
    return;
  }
  // ...
};

// handleDownloadVideo catch 수정
} catch (err: any) {
  setToast({ message: `다운로드 실패: ${err.message}`, type: 'error' });
}
```

---

### 🔴 [높음] Toast 타이머 리셋 버그 — 불안정한 onClose 참조
`onClose={() => setToast(null)}`가 매 렌더마다 새 함수 참조 생성. Toast 내부 `useEffect` deps에 `onClose`가 있어 부모가 재렌더(이메일 입력 중 등)될 때마다 4초 타이머가 초기화됨 → 토스트가 닫히지 않는 버그.

```tsx
// useCallback으로 안정적 참조 생성
const closeToast = useCallback(() => setToast(null), []);

// JSX 수정
{toast && (
  <Toast message={toast.message} type={toast.type} onClose={closeToast} />
)}
```

---

### 🟡 [중간] OTP 6자리 완성 시 자동 제출 없음
6번째 칸 입력 후 별도 버튼 클릭이 필요. 자동 제출 트리거 추가 권장.

```tsx
// OtpInput에 onComplete prop 추가
interface OtpInputProps {
  value: string;
  onChange: (val: string) => void;
  onComplete?: () => void;
}

// handleChange 내 마지막 셀 입력 시 자동 실행
} else if (digit && index === 5 && next.replace(/\D/g, '').length === 6) {
  onComplete?.();
}

// 사용처
<OtpInput value={otpValue} onChange={setOtpValue} onComplete={handleVerifyOtp} />
```

---

### 🟡 [중간] handleVerifyOtp — data.user가 null일 때 무음 실패
`error`도 없고 `data.user`도 없는 케이스에서 아무 피드백 없이 종료됨.

```tsx
if (data?.user) {
  // ... 기존 성공 로직
} else {
  setOtpError('인증 처리 중 오류가 발생했습니다. 다시 시도해 주세요.');
}
```

---

### 🟡 [중간] handleResendOtp — 로딩 상태 없음, 중복 요청 가능
쿨다운은 성공 후에만 적용되므로 응답 대기 중 버튼을 여러 번 클릭 가능.

```tsx
const [isResendLoading, setIsResendLoading] = useState(false);

const handleResendOtp = async () => {
  if (resendCooldown > 0 || isResendLoading) return;
  setIsResendLoading(true);
  try {
    // ...
    setResendCooldown(60);
  } catch (err: any) { /* ... */ }
  finally { setIsResendLoading(false); }
};

// 버튼
<RefreshCw className={`w-3.5 h-3.5 ${isResendLoading ? 'animate-spin' : ''}`} />
{isResendLoading ? '발송 중...' : resendCooldown > 0 ? `재발송 가능 (${resendCooldown}초 후)` : '인증번호 재발송'}
```

---

## C. 코드 품질

### 🔴 [높음] localStorage 파싱 로직 중복 — 두 곳에 동일 코드 복사
로그인(L377~386)과 회원가입(L411~421) 양쪽에 동일한 localStorage 파싱 블록 존재.

```tsx
// 컴포넌트 외부로 추출
const getLocalStoredUserId = (): string => {
  if (typeof window === 'undefined') return '';
  try {
    const raw = localStorage.getItem('raptor-workflow-storage');
    if (!raw) return '';
    return JSON.parse(raw)?.state?.userId || '';
  } catch {
    return '';
  }
};

// 사용 (두 곳 모두 대체)
const localUserId = getLocalStoredUserId();
```

---

### 🟡 [중간] password 이중 클리어 — finally 중복
`catch`, `finally`, 성공 경로 각각에서 `setPassword('')` 반복 호출.

```tsx
// finally에서만 처리
} catch (err: any) {
  setAuthError(displayError);
  // setPassword('') 제거
} finally {
  setAuthLoading(false);
  setPassword(''); // 한 곳에서만
}
```

---

### 🟡 [중간] useEffect 불필요한 deps — `setUser`
`L182`: `setUser`가 deps에 있지만 해당 effect에서 사용되지 않음.

```tsx
// 수정 전
}, [setUser, setIsKeyConfigured, hasHydrated]);

// 수정 후
}, [setIsKeyConfigured, hasHydrated]);
```

---

### 🟢 [낮음] rows 타입 `any[]` — 명시적 타입 필요

```tsx
interface ProjectRow {
  task_id: string;
  project_id: string;
  product_name: string;
  description: string;
  status: 'success' | 'failed' | 'pending';
  result_url?: string;
}

const [rows, setRows] = useState<ProjectRow[]>([]);
```

---

## D. 성능

### 🟡 [중간] fetchDashboardData — 모달 닫힐 때도 불필요한 fetch 실행
`isModalOpen`이 deps에 있어 모달이 닫힐 때도 API 호출됨.

```tsx
useEffect(() => {
  if (!isModalOpen) return; // 닫힐 때 조기 반환 추가
  const fetchDashboardData = async () => { /* ... */ };
  fetchDashboardData();
}, [user, lastRenderTimestamp, isModalOpen]);
```

---

## 📊 종합 요약표

| # | 이슈 | 카테고리 | 우선순위 |
|---|------|----------|----------|
| 1 | 대시보드 API IDOR (인증 헤더 없음) | 보안 | 🔴 높음 |
| 2 | alert()가 내부 에러 메시지 원문 노출 | 보안 | 🔴 높음 |
| 3 | alert() 남용 3곳 — Toast와 불일치 | UX | 🔴 높음 |
| 4 | Toast 타이머 리셋 버그 (onClose 불안정) | UX | 🔴 높음 |
| 5 | localStorage 파싱 중복 코드 | 코드 품질 | 🔴 높음 |
| 6 | OTP 6자리 자동 제출 없음 | UX | 🟡 중간 |
| 7 | data.user null 무음 실패 | UX | 🟡 중간 |
| 8 | handleResendOtp 로딩 상태 없음 | UX | 🟡 중간 |
| 9 | password 이중 클리어 | 코드 품질 | 🟡 중간 |
| 10 | fetchDashboardData 모달 닫을 때 실행 | 성능 | 🟡 중간 |
| 11 | useEffect 불필요한 deps | 코드 품질 | 🟡 중간 |
| 12 | 미사용 `api` import | 코드 품질 | 🟢 낮음 |
| 13 | rows 타입 `any[]` | 코드 품질 | 🟢 낮음 |

---

## 💬 Claude Code 총평

> **즉시 적용 권장 순서**:  
> 1️⃣ IDOR 보안 패치 (Authorization 헤더 추가)  
> 2️⃣ alert() 전면 제거 → setToast() 통일  
> 3️⃣ Toast 타이머 리셋 버그 (useCallback 적용)  
> 
> OTP 아키텍처 전환 자체는 올바른 방향이며 Supabase verifyOtp / resend API 사용도 정확합니다.  
> 핵심 기능 구현 완성도는 높으나, 보안과 UX 일관성 측면에서 후속 패치가 필요합니다.
