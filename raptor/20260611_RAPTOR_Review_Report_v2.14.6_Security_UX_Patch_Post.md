# Claude Code Review — AuthDashboard.tsx v2.14.6
> **리뷰어**: Claude Code v2.1.118  
> **대상 파일**: `src/components/AuthDashboard.tsx`  
> **리뷰 일시**: 2026-06-11  
> **패치 버전**: v2.14.6 (보안/UX/코드품질 일괄 패치 사후 검증)

---

## A. 종합 판정: 전원 적용 확인 ✅

v2.14.5 리뷰에서 지적된 12개 항목 **전부** 코드에서 확인됨.

---

## B. 항목별 검증 결과

| # | 항목 | 카테고리 | 우선순위 | 판정 | 비고 |
|---|------|----------|----------|------|------|
| 1 | IDOR — Authorization Bearer 헤더 추가 | 보안 | 🔴 심각 | ✅ 확인 | `accessToken` 조건부 스프레드, `isModalOpen` deps 추가 |
| 2 | alert() → setToast()+setAuthError() (비밀번호 재설정) | 보안 | 🔴 중요 | ✅ 확인 | 민감 정보 브라우저 다이얼로그 노출 차단 |
| 3 | handleSaveKey/handleDownloadVideo alert() → setToast() | UX | 🟡 경미 | ✅ 확인 | 두 곳 모두 교체 완료 |
| 4 | Toast onClose useCallback 래핑 | UX | 🟡 경미 | ✅ 확인 | `closeToast = useCallback(() => setToast(null), [])` + `useEffect([onClose])` 의존성 올바름 |
| 5 | localStorage → getLocalStoredUserId() 유틸 추출 | 보안 | 🔴 중요 | ✅ 확인 | SSR-safe, try/catch 포함, 2곳 모두 사용 |
| 6 | OTP 6자리 완성 시 onComplete 자동 실행 | 기능 | 🔴 중요 | ✅ 확인 | 직접 입력 + 붙여넣기 양쪽 모두 처리 |
| 7 | 미사용 import 제거 | 기능 | 🟢 경미 | ✅ 확인 | api / Key / Calendar / Play 제거 완료 |
| 8 | handleResendOtp isResendLoading 중복 방지 | 기능 | 🔴 중요 | ✅ 확인 | `if (resendCooldown > 0 \|\| isResendLoading) return` |
| 9 | finally에서 setPassword('') 통합 | 보안 | 🔴 중요 | ✅ 확인 | 예외 발생 시에도 비밀번호 메모리 정리 보장 |
| 10 | rows any[] → ProjectRow 인터페이스 | 기능 | 🟢 경미 | ✅ 확인 | 인터페이스 정의 + 상태 타입 모두 교체 |
| 11 | useEffect isModalOpen=false 시 fetch 방지 | 기능 | 🔴 중요 | ✅ 확인 | deps에 `isModalOpen` 추가 + 가드 `if (!isModalOpen) return` |
| 12 | URL.revokeObjectURL finally 보장 | 기능 | 🟢 경미 | ✅ 확인 | `objectUrl[]` 배열 패턴으로 finally에서 안전하게 해제 |

---

## C. 신규 발견 이슈 (3개)

### 🟡 [권고] URL.revokeObjectURL revoke 타이밍 리스크
일부 구형 브라우저에서 `a.click()` 직후 `finally`에서 즉시 revoke 시 다운로드 끊길 수 있음.

```ts
// 현재 코드
if (objectUrl[0]) window.URL.revokeObjectURL(objectUrl[0]);

// 권장 수정
if (objectUrl[0]) setTimeout(() => window.URL.revokeObjectURL(objectUrl[0]), 100);
```

---

### 🟡 [경고] fetchDashboardData 에러 시 사용자 피드백 없음
fetch 실패 시 `console.warn`만 있고 Toast 없어, 사용자는 목록이 왜 비었는지 알 수 없음.

```ts
// 현재 코드
} catch (err) {
  console.warn("Failed to fetch dashboard rows:", err);
}

// 권장 수정
} catch (err) {
  console.warn("Failed to fetch dashboard rows:", err);
  setToast({ message: '프로젝트 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.', type: 'error' });
}
```

---

### 🟢 [권고] handleVerifyOtp `type: 'signup'` 하드코딩
이메일 변경 등 다른 OTP 흐름 추가 시 확장 불가. 현재 요구사항 범위에서는 허용 수준이나, 향후 `OtpInputProps`에 `otpType` prop 분리 고려.

---

## 📊 종합 평가

| 항목 | 결과 |
|------|------|
| **패치 적용률** | 12 / 12 (100%) |
| **신규 발견 이슈** | 3개 (치명 0 / 경고 1 / 권고 2) |
| **코드 품질 점수** | **8.2 / 10** |

**감점 요인**: revoke 타이밍(-0.5) / fetchDashboardData 에러 피드백(-0.8) / OTP type 하드코딩(-0.5)

---

## 💬 Claude Code 총평

> 보안 수정(IDOR, 비밀번호 메모리, localStorage 추상화)이 모두 올바르게 적용되었고,  
> UX 일관성(Toast 통합)도 깔끔하게 정리됨.  
> `fetchDashboardData` 에러 피드백만 추가하면 **즉시 프로덕션 수준** 도달.  
> 치명적 결함 없음 — **배포 적합 판정**.
