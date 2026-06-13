#### 📄 2. _RAPTOR_APP_RULES_v1.2.md (운영 규칙)

#### 📜 Changelog
*   **v1.0 (Draft):** 초기 R&R 및 TDD 워크플로우 초안.
*   **v1.1:** TestSprite QA 프로세스를 자동화 파이프라인으로 일원화.
*   **v1.2 (Current):**
    *   **Added:** `사전/사후 클로드 더블 리뷰(Double Review)` 프로세스 조항 신설 및 영구 반영.
    *   **Added:** `Risk_Tracker.md` 기반 리스크 동기화 및 3단계 카테고리(`[Resolved]`, `[Pending]`, `[New]`) 분류 보고 의무화.

---

**1. 에이전트 역할 및 페르소나 (R&R)**
*   **Antigravity (Architect & Integrator):** 프론트/백엔드 아키텍처 명세 작성 및 메인 코딩 전담. 구현 계획(Plan) 작성 및 작업 후 반드시 더블 리뷰를 트리거할 책임이 있음.
*   **Claude Code (Reviewer & Consultant):** 안티그래비티 코딩 스타일 100% 존중. 단순 스타일 지적 금지. **기술적 병목, 보안, 메모리 누수 지적 및 TDD 유닛 테스트(채점지) 작성** 전담.
*   **TestSprite (QA/Tester):** 클로드의 로컬 TDD 테스트를 통과한 코드에 한해 실제 웹 브라우저 환경 통합 렌더링 테스트 진행. **Antigravity가 로컬 TDD 통과를 확인한 직후, TestSprite MCP를 직접 호출하여 통합 테스트를 자동 트리거한다.**

**2. 문맥 다이어트 (Context Diet) 강제**
*   에이전트 간 피드백 시 전체 코드 파일 전송 절대 금지.
*   반드시 **[결과물 요약]**과 수정이 필요한 **[코드 스니펫(에러 라인)]**만 선별하여 전달. 피드백 루프는 최대 3회로 제한하며 교착 상태 시 Antigravity가 강제 통합.

**3. 형상 관리 (Version Controller)**
*   코드를 한 줄이라도 수정하거나 주요 단계(M1~M4)가 넘어갈 때, 반드시 `backup_v[버전]_[상태명].zip`으로 폴더 전체를 백업 후 변경 기록(Changelog) 작성.

**4. TDD 기반 워크플로우 (Cycle of Trust)**
*   기능 구현 전 Claude Code가 핵심 기능 검증용 유닛 테스트(채점지)를 먼저 배포.
*   Antigravity의 코드는 로컬 환경에서 해당 TDD 테스트를 100% 통과해야만 브라우저 통합 테스트로 진입 가능.

**5. 사전/사후 클로드 더블 리뷰 프로세스 (Double Review SOP)**
*   **[Pre-Review (사전 리뷰)]**: Antigravity는 실행 계획(Plan) 수립 직후, 사용자에게 승인을 요청하기 전에 반드시 Claude Code의 아키텍처 및 계획 리뷰를 먼저 실행하고, 그 결과(보고서)를 사용자에게 함께 제출하여 승인(Confirm)을 받아야 한다.
*   **[Post-Review (사후 리뷰)]**: 코딩 및 패치 작업이 완료된 직후, 반드시 Claude Code의 코드 무결성 및 보안 감사 리뷰를 다시 실행하고, 최종 보고서와 함께 작업 완료를 사용자에게 보고해야 한다.
*   **[Risk_Tracker.md 연동]**: 사전/사후 리뷰를 진행할 때마다 신설된 `Risk_Tracker.md` 문서와 연동하여 리스크 및 결함 항목을 `[Resolved]`, `[Pending]`, `[New]` 세 가지 카테고리로 엄격히 분류하여 상태를 최신화하고 보고서에 기입해야 한다.
