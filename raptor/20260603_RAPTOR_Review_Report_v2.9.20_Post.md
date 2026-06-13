# RAPTOR V2.9.20 — 2차 HIL 테스트 피드백 5대 결함 핫픽스 사후 리뷰(Post-Review) 보고서

| 항목 | 내용 |
|---|---|
| **Author** | Claude Code |
| **검토 대상** | 2차 HIL 테스트 기반 5대 결함 핫픽스 적용 코드베이스 |
| **참조 문서** | implementation_plan.md, Risk_Tracker.md |
| **작성일** | 2026-06-03 |
| **기준 버전** | RAPTOR V2.9.20 (post-patch) |

---

## 🟢 [Resolved] — 패치 작업을 통해 완결 및 해결된 결함 검증

### R-1. 자동 로그인 시 하드코딩 계정 덮어쓰기 복구
- **구현 내용:** `useWorkflowStore.ts`의 `persist` partialize 미들웨어에 `user: state.user`를 정상 복원 완료하여, 새로고침(수화) 시 실제 Supabase 사용자 로그인 정보가 유실되지 않고 정확하게 로컬 스토리지에 복원 및 로드되도록 조치했습니다.
- **검증:** `RaptorWorkflow.tsx` 마운트 `useEffect`에서 `isKeyConfigured` 조건 충족 시에도 `store.user`가 존재한다면 beta_tester 더미 세션으로 강제 덮어쓰지 않고, 복원된 사용자 세션을 그대로 안전하게 보존합니다.

### R-2. 프로젝트 비용 UI 노출 시점(Depth) 제어
- **구현 내용:** 메인 워크플로우 전반(Step 0 ~ Step 4)에서 예상 소모 비용 및 실제 누적 요금 카드 UI를 완전히 제거하였습니다.
- **검증:** 해당 비용 UI 카드를 우측 상단 `[내 보관함]` 아이콘 클릭 시 전개되는 슬라이드 드로어(`isDrawerOpen === true`)의 최상단 영역으로 이전 배치하여, 사용자가 상세 보기를 명시적으로 진입할 때에만 비용이 렌더링되도록 통제했습니다.

### R-3. 에러 잔재 캐시 초기화 (False Positive 방지)
- **구현 내용:** `useWorkflowStore.ts`의 `onRehydrateStorage` 콜백 함수 내에서 수화 직후 깨진 이미지 캐시를 정화하는 방어 설계를 교정했습니다.
- **검증:** 단순 문자열 `includes('404')`와 같은 오탐 위험이 높은 조건 대신, 프로토콜 검증(`startsWith('http://')` 등)과 fail/broken 문자열 유무를 포함하는 복합 URL 구조 유효성 검사를 통해 정상 CDN 리소스의 오탐(False Positive)을 차단하고, 깨진 자원만 깔끔하게 `null`로 복구합니다.

### R-4. 일괄 생성 버튼 비활성화 및 엣지 가드
- **구현 내용:** `RaptorWorkflow.tsx`에서 모든 씬에 이미 유효한 이미지가 생성/할당 완료되었는지를 판별하는 `allImagesReady` 상태를 고도화했습니다.
- **검증:** 임의의 씬이 렌더링 중(`status === 'rendering'`)이거나 실패(`status === 'error'`)한 엣지 케이스를 철저히 판별하여, 모든 생성이 성공적으로 완료되었을 때만 `[AI 이미지 일괄 생성 시작]` 버튼에 `disabled={allImagesReady}`가 적용되며 회색조 스타일로 비활성화되어 중복 생성을 원천 차단합니다.

### R-5. KIE 비디오 파싱 및 예외 처리 오류 해결
- **구현 내용:** 
  1. `main.py`의 비디오 작업 완료 감지 루프 내에서 기존 `is_veo` 조건문을 제거하여 Grok을 포함한 전체 비디오 생성 엔진에 대해 `resultJson` 파싱을 통일 및 일반화했습니다.
  2. 비디오 생성 폴링 실패(`state === 'fail'`) 시 KIE API 응답에서 `failMsg` 또는 `reason`을 상세히 추출해 `Exception(f"비디오 생성 실패: {fail_msg}")` 형태로 예외를 명확히 전파하도록 변경했습니다.
  3. REST 엔드포인트 `generate_videos`에서도 KIE 실패 발생 시 단순 Exception 대신 `raise HTTPException(status_code=500, detail=...)`을 발생시키고, SSE 스트리밍 루프에서도 이를 catch하여 프론트엔드로 상세 에러 내용을 온전히 전사하도록 예외 처리를 보강했습니다.

---

## 🟡 [Pending] — 미해결 상태로 지속 관찰/추적이 필요한 잔여 리스크

### P-1. `veo_fast` 모델 단가 누락에 따른 임시 폴백 요금 (RISK-002 하위)
- **리스크 내용:** `kie_pricing.json`에 `veo_fast` 단가가 여전히 누락되어 있어, 해당 엔진 사용 시 프론트엔드의 `calculateEstimatedCost` 계산 시 기본값 `0.10`으로 폴백 연산되는 사양이 지속됩니다. 실서비스 배포 전에 정확한 요금 갱신이 요망됩니다.

### P-2. KIE 단가 하드코딩 결합도 및 다중 사용자 쿼터 한계 (RISK-002 본체)
- **리스크 내용:** 동적 단가 맵핑 연동 및 Supabase Storage의 `beta_tester` 하드코딩 쿼터 제한 로직은 이번 패치 범위 밖으로, 멀티 테넌트 서비스 배포 시 저장소 병목 및 권한 예외를 방지하기 위해 추후 Storage 쿼터 로직 개편이 필요합니다.

### P-3. 크로스 플랫폼 폰트 경로 하드코딩 (RISK-003)
- **리스크 내용:** `ffmpeg_worker.py` 내부의 맑은 고딕 폰트 경로(`C:/Windows/Fonts/malgun.ttf`)가 Windows 환경 전용으로 하드코딩되어 있습니다. Linux 및 Docker 컨테이너 서비스 탑재 시 렌더링 에러를 유발하므로 배포 아키텍처 수립 시 선결 대응이 필수적입니다.

---

## 🔴 [New] — 소스 코드 사후 분석 중 새롭게 식별된 위험 및 권고사항

### N-1. `user` 로컬 스토리지 역직렬화에 따른 만료 세션 Ghost User 현상
- **위험성:** Zustand 스토어 partialize 복귀로 인해 사용자 정보가 로컬 스토리지에 유지되나, Supabase 세션 만료 후 새로고침 시 만료된 user 객체가 일시적으로 화면에 렌더링되는 플래시 현상이 발생할 수 있습니다.
- **권고사항:** App 마운트 시 Supabase 세션 유효성을 비동기 검증하고 만료 상태가 감지되면 스토어의 user 데이터를 즉시 `null`로 동기화하도록 보완 조치를 권장합니다.
