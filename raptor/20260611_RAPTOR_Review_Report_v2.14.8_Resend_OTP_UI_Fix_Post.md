# Claude Code Review — AuthDashboard.tsx v2.14.8
> **리뷰어**: Claude Code v2.1.118  
> **대상 파일**: `src/components/AuthDashboard.tsx`  
> **리뷰 일시**: 2026-06-11  
> **패치 버전**: v2.14.8 (P1 - 인증번호 재발송 후 OTP 입력 폼 미전환 버그 픽스)

---

## 🟡 리뷰 결과 및 엣지 케이스 추가 발견

**수정 내용 요약:**

**루트 원인**: `handleResendFromLogin` (로그인 폼 → OTP 폼 전환 경로) 에서 `setOtpError(null)` 호출이 누락됨.

**버그 재현 시나리오**:
1. 회원가입 시도 → OTP 입력 → 인증번호 오류 (`otpError` 설정됨)
2. 모달 닫기 또는 뒤로가기
3. 로그인 시도 → "이메일 미인증" 에러
4. "인증번호 재발송" 클릭 → `handleResendFromLogin` 실행
5. OTP 폼으로 전환되지만 **1단계의 에러 메시지가 그대로 표시됨**

**수정 방향 제안**: 
`setOtpMode(true)` 이전에 `setOtpError(null)` 추가 필요 (L328 위치).

`handleResendOtp`(OTP 폼 내 재발송)에는 이미 `setOtpError(null)`이 있어 정상 — 로그인→OTP 전환 경로만 누락된 상태였습니다.
