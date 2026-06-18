# RAPTOR P0-P2 실행 계획서 (Draft)

## 1. 개요
클로드 코드의 아키텍처 감사 보고서(2026-06-14)에 기반하여 치명적인 Vercel 빌드 오류(P0) 및 파이프라인 폭주 원인(스코프 버그 및 자동 연쇄 실행)을 수정하기 위한 실행 계획입니다.

## 2. 작업 상세

### 🔴 P0 이슈 (즉시 수정)
1. **[미정의 컴포넌트 오류 제거]**
   - 대상: `src/components/RaptorWorkflow.tsx`
   - 작업: `import` 되지 않은 `<TrafficLightUX />` 태그(1289 라인) 삭제. 이로 인한 `TS2304` Vercel 빌드 에러 해결.

2. **[IIFE 스코프 호이스팅 및 버튼 복구]**
   - 대상: `src/components/RaptorWorkflow.tsx`
   - 작업: IIFE 내부에서만 선언되었던 상태 변수(`completedImages`, `completedVideos`, `totalScenes`, `allVideosReady`)를 `useWorkflowStore` 훅 호출 직후 등 컴포넌트의 최상위 스코프로 호이스팅.
   - 작업: 이를 통해 Step 4 / Step 5 버튼의 렌더링 조건문이 변수를 정상 참조하게 하여 UI에 나타나지 않는 현상(영구 미표시) 해결.

3. **[파이프라인 100% 수동 제어 확립]**
   - 대상: `src/components/RaptorWorkflow.tsx`
   - 작업: 이미지 생성 종료 후 `setLoading(false)` 이후의 어떠한 자동 함수 호출(예: `handleGenerateClips`)도 없음을 확인.
   - 작업: `handleGenerateClips` 처리 과정 내에서 `data.clips_ready` 이벤트 수신 시, 절대로 `handleRenderFinal()`이 자동 호출되지 않도록 방어 코드(또는 자동 실행 코드 제거) 적용.

4. **[환경변수 누락 대응 가이드]**
   - 대상: Vercel 대시보드 환경변수 가이드라인 제공
   - 작업: 사용자가 Vercel 대시보드에 접속하여 `NEXT_PUBLIC_BACKEND_URL`을 명시적으로 빈 문자열(`""`)로 설정하도록 안내.

### 🟡 P1 / 🟢 P2 이슈 (순차 적용)
1. **[스틸컷 배지 렌더링 조건 수정]**
   - 대상: `src/components/RaptorWorkflow.tsx`
   - 작업: 스틸컷 배지 표시 조건을 `use_image_only && !!image_url` 로 명확히 수정.

2. **[MVP 단계 안내 배너 추가]**
   - 대상: `src/components/AuthDashboard.tsx`
   - 작업: 로그인 후 대시보드 진입 시 "현재 내부 테스트 단계"임을 명시하는 안내 배너 UI 추가.

3. **[디렉토리 및 Git 정합성 정리 가이드]**
   - 대상: 사용자 가이드라인
   - 작업: 로컬 `main` 브랜치와 원격 `master` 브랜치 불일치 해소 및 미추적 디렉토리(`RAPTOR-Composer/`) 정리 안내.

## 3. 예상 효과
- Vercel 프로덕션 빌드 성공 및 프록시 API 연동 정상화.
- 사용자의 클릭(onClick) 없이는 비디오 생성이나 최종 렌더링이 절대로 동작하지 않는 수동 파이프라인 통제 확보.
