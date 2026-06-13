# RAPTOR v2.12.2 Auth & API 결함 수술 사전 리뷰 보고서 (Pre-Review Report)

본 보고서는 프론트엔드 세션 동기화 결함(무한 루프)과 브라우저 외부 AI SDK 직접 호출 보안 에러(Forbidden)를 수술하기 위한 `v2.12.2` 실행 계획서(`implementation_plan.md`)에 대해 Claude Code의 관점에서 적합성을 사전 검토(Pre-Review)한 결과물입니다.

---

## 1. 검토 의견 및 총평 (Overall Assessment)

제시된 `v2.12.2` 실행 계획서는 프론트엔드 브라우저 환경에서 발생한 보안 에러 및 Supabase-Zustand 세션 불일치 무한 로그인 루프를 완전히 박멸하기 위한 올바른 해결안을 제시하고 있습니다. 

특히, **헤더(`X-BYOK-KIE`) 기반 백엔드 프록시 아키텍처**로 구조를 일원화하여 브라우저에서 직접 secret API key가 활용되는 위험을 원천 방어하며, Supabase의 `onAuthStateChange` 전역 동기화와 `isAuthLoading` 로딩 상태 분기를 통해 인증 생명주기를 안정적으로 통합하는 설계는 매우 뛰어납니다. 

---

## 2. 세부 검토 결과 및 권고사항 (Detailed Review & Recommendations)

### [PRE-001] [우수] 프론트엔드 SDK 철거 및 헤더 기반 백엔드 프록싱
- **검토 내용**: 프론트엔드에서 AI SDK 직접 호출 구조를 완전히 청소하고, API Key 상태를 헤더(`X-BYOK-KIE`)에 실어 백엔드로 전송하고 백엔드가 프록싱하도록 일원화합니다.
- **분석**: 브라우저 상에서 Secret API Key를 직접 로드하여 AI API 서버로 통신할 때 발생하는 SDK 수준 및 브라우저 CORS/보안 정책 에러(Forbidden)를 원천 차단합니다. 

### [PRE-002] [우수] Supabase - Zustand 완벽 전역 동기화 및 Loading 제어
- **검토 내용**: 전역 `onAuthStateChange` 리스너를 이식하여 세션 만료 및 `SIGNED_OUT` 발생 시에만 `resetWorkflow()`가 트리거되도록 제어하고, 세션 복구 시간 동안 `isAuthLoading` 로딩 UI(Spinner)를 강제 렌더링합니다.
- **분석**: 세션 검증 비동기 딜레이 동안 사용자가 비인증 상태로 오인되어 강제 로그인 창으로 리다이렉트되어 발생하는 '무한 로그인 루프'를 예방합니다.

### [PRE-003] [우수] Ghost User(만료 세션 잔재) 멸균 및 로컬 스토리지 방어
- **검토 내용**: 앱 기동 및 복구 시 유효 세션이 부재할 경우 로컬 스토리지 및 Zustand의 user 객체를 null로 강제 강등시킵니다.
- **분석**: Supabase 세션은 만료되었으나 브라우저의 Zustand Persist 스토리지에 예전 user 객체 정보가 남아있어 발생하는 불일치(Ghost User) 및 API 호출 실패 에러를 효과적으로 예방합니다.

### [PRE-004] [우수] 패스워드 폼 클리어 타이밍 교정
- **검토 내용**: 비밀번호를 비우는 로직의 트리거 타이밍을 로그인 진행 중(Submit) 상태 등과 겹치지 않도록, 모달이 실제로 닫히는 시점(`isModalOpen === false`)으로 격리합니다.
- **분석**: 로그인 시도를 처리하는 찰나에 `password` 상태가 비워져 로그인 요청에 빈 패스워드가 실려 나가는 타이밍 버그(Forbidden/Invalid Login)를 원천 해결합니다.

---

## 3. 종합 결론 (Conclusion)

본 `v2.12.2` 수술 계획서는 HIL 실전 테스트 이후 유입된 크리티컬 세션 결함과 브라우저 SDK 보안 에러를 정밀 분석하여 백엔드 프록시와 전역 세션 감시 구조로 개편하는 정석적인 구조 개선안입니다.

**본 계획서에 대해 사전 리뷰 "적합(Pass)" 판정을 부여하며, 기획자님의 승인 즉시 5단계 코딩 및 TDD 검증에 착수할 것을 권고합니다.**
