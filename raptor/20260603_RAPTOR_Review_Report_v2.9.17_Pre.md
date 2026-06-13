# RAPTOR 아키텍처 사전 리뷰 보고서 (v2.9.17 Pre-Review)

*   **작성일:** 2026-06-03
*   **작성자:** Antigravity (Architect & Integrator)
*   **리뷰 대상:** HIL 테스트 피드백 6대 결함 전면 핫픽스 구현 계획서 (`implementation_plan.md`)

---

## 1. 🟢 [Resolved]: 계획서 반영으로 해결되는 결함 및 리스크

### 🛠️ NEW-002: 옵션 A(실사 이미지 업로드) 씬 할당 로직의 상태 충돌 및 토큰 낭비
*   **원인:** 사용자가 직접 올린 실사 이미지나 이전 생성 결과가 있어도 이미지 일괄 생성 버튼 클릭 시 덮어씌워지거나 중복 API 요청이 날아감.
*   **해결책:** `handleGenerateImages` 내부에 `scene.image_url`이 존재하는 경우(수동 업로드 및 기존 이미지 존재 씬) 루프를 타지 않고 무조건 스킵(Skip)하는 **하이브리드 자율 선택 로직**을 엄격히 구현하여 토큰 비용을 원천 차단함.

### 🛠️ NEW-003: `/api/refine-prompt` 및 `/api/generate-images` KIE 404 API 픽스
*   **원인:** KIE AI 플랫폼의 Base URL 규격은 `https://api.kie.ai/api/v1`이나, 이미지 API 호출 시 `/api/`가 누락된 `https://api.kie.ai/v1/images/generations` 로 잘못 합성되어 `nano-banana-2` 모델 등 이미지 생성 시 404 오류가 발생함.
*   **해결책:** 엔드포인트를 `https://api.kie.ai/api/v1/images/generations` 로 바르게 통일하고 WAF 보안 우회를 위해 `User-Agent` 헤더도 함께 보강함.

---

## 2. 🟡 [Pending]: 추후 보완 및 추적 관찰이 필요한 잔여 리스크

### 🛠️ RISK-003: 크로스 플랫폼 폰트 경로 하드코딩 결함
*   **현황:** 자막 합성을 위한 FFmpeg 폰트가 Windows 경로(`C:/Windows/Fonts/malgun.ttf`)로 하드코딩되어 배포 환경에 따른 분기 대책이 마련되어야 함.
*   **상태:** 이번 개편(V2.9.17) 범위 밖이므로 Linux/Docker 이식성 보완은 다음 스프린트로 이월(Pending)하고 지속 추적함.

### 🛠️ RISK-002: KIE 모델 단가 분기 및 Supabase Storage FIFO 쿼터 한계
*   **현황:** `check_and_enforce_user_limits` 함수가 하드코딩된 단일 테스터 `beta_tester`를 기준으로 파일 용량 및 개수 제어를 하고 있음.
*   **상태:** 다중 사용자 배포 환경 도입 시 세션 소유권을 기반으로 쿼터 한계를 조회하도록 다음 인프라 스프린트 단계에서 패치 예정(Pending).

---

## 3. 🔴 [New]: 이번 코드 분석을 통해 새로 식별된 리스크

### 🛠️ NEW-005: Zustand Rehydration 후 휘발성 에러 상태 누수 리스크
*   **리스크:** 사용자가 새로고침을 하거나 재수화(Rehydrate)할 때, Zustand 스토어의 `errorMessage`나 이전 `isRendering` 등 휘발성 상태들이 오버레이 뷰를 장악하여 "비디오 렌더링 실패" 등 과거의 실패 팝업에 갇히는 결함이 확인됨.
*   **대책:** `onRehydrateStorage` 콜백 및 `setUser` 바인딩 시점에 에러 메시지(`errorMessage`)와 렌더링 상태를 명시적으로 강제 리셋(null)하고, 렌더링 단계(Step 4) 도중 에러가 났다면 에셋을 살린 채 3단계로 복원시키는 예외 방어 처리를 적용함.

### 🛠️ NEW-006: Step 3에서 Step 4로의 에셋 미완성 진입 결함
*   **리스크:** 모든 씬에 대한 이미지(수동 업로드 또는 AI 생성) 매칭이 완성되지 않았는데도 Step 4(최종 비디오 생성) 이동 버튼이 항상 활성화되어 있어 오동작을 유도함.
*   **대책:** `finalAssets.script` 내 모든 씬에 `image_url`이 100% 매칭된 상태(`allImagesReady`)일 때만 단계 이동 버튼이 보이도록 렌더링 조건을 엄격화함.
