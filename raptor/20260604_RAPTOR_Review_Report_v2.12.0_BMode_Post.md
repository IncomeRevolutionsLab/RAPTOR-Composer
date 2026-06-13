 # RAPTOR V2.12.0 사후 리뷰 (Post-Review) 보고서

**Author: Claude Code**
**작성일: 2026-06-04**
**대상 버전: RAPTOR V2.12.0 — 대시보드 대통합 및 Project-Task 매핑 아키텍처 개편**

---

## [Resolved] 해결 및 구현 완료 항목

### 1. N-01 / datetime AttributeError 치명적 크래시 완전 해소

`main.py` 최상단 임포트가 `from datetime import datetime, timedelta, date`로 완전히 정형화되어 있음을 코드에서 직접 확인했다. 이전에 `datetime.datetime.now()` 호출로 `AttributeError`를 유발하던 패턴은 전수 `datetime.now()`로 교체되었으며, `post_review` 함수 내부의 지역 `import datetime` 구문이 삭제되고 `date.today()`를 통한 호출로 일원화되었다. `/api/render-stream` 진입 시 즉시 크래시가 발생하던 치명적 결함은 근본적으로 제거되었다.

### 2. Project-Task 1:N 매핑 아키텍처 완성

`main.py`에 `ProjectModel`, `TaskModel`, `PROJECTS_DB_PATH`, `TASKS_DB_PATH`가 완전히 분리 구현되어 있다. `create_project_in_db`, `create_task_in_db`, `update_task_in_db` 등 CRUD 헬퍼 함수가 신설되었으며, `/api/projects`, `/api/projects/{project_id}/tasks`, `/api/tasks/{task_id}` RESTful 엔드포인트가 명세에 따라 구현되어 있다. `get_user_videos` 및 `get_dashboard_projects`는 O(1) 해시맵 조인으로 프로젝트-태스크 관계를 조인하여 렌더링하도록 최적화되어 있다.

### 3. RISK-B 상태 바인딩 방어 가드 구현

`/api/render-stream`의 `process_scene_inner` 함수 최상단에 DB 기반 RISK-B 가드가 삽입되어 있다. `project_id`가 있을 경우 `TASKS_DB_PATH`에서 해당 프로젝트의 동일 씬 번호에 대해 가장 최근 성공한 비디오 태스크를 조회하고, 존재하면 KIE API 호출을 즉시 스킵하여 과금 누수를 차단하는 로직이 확인된다. `render-stream-test` 엔드포인트에도 동일한 가드가 적용되어 있다.

### 4. `use_image_only` 하이브리드 스킵 처리 연결

백엔드 `/api/render-stream`의 `process_scene_inner` 내부에서 `scene.get('use_image_only', False)` 분기가 구현되어 있으며, `True`인 씬은 KIE 비디오 API 호출을 스킵하고 `video_url=None`으로 처리한다. 프론트엔드 `RaptorWorkflow.tsx`의 `handleRenderVideo`가 `requestBody.scenes`에 `use_image_only` 필드를 포함하여 전송하므로 프론트-백 연결이 완성되어 있다.

### 5. `handleFallbackToImage` 스틸컷 대체 UX 구현

`RaptorWorkflow.tsx`에 `handleFallbackToImage(index)` 함수가 신설되어, 호출 시 해당 씬의 상태를 `use_image_only: true`, `status: 'fallback'`, `error: null`, `video_url: null`로 정확히 전환하고 전역 에러를 클리어한다. Step 4 씬 모니터 카드에서 `scene.status === 'error'` 조건일 때 `[🖼️ 비디오 포기하고 스틸컷 대체]` 버튼이 노출되는 JSX 분기가 올바르게 구현되어 있다.

### 6. `handleRenderVideo`의 Fallback 씬 상태 보호 (PRE-003)

`handleRenderVideo` 시작 시 에러 클리어 로직이 `scene.status === 'error'`인 씬만 `waiting`으로 초기화하고, `status === 'fallback'`인 씬은 조건에 포함되지 않아 보호된다. 관련 코드를 직접 확인했다.

### 7. 엔진 변경 인터럽트 방지 (PRE-004)

Step 4 엔진 선택 `<select>` 요소에 `disabled={isRendering}` 속성이 적용되어 있으며, `handleVideoEngineChange` 함수가 신설되어 엔진 변경 시 기존 `error` 상태 씬을 `waiting`으로 복구하고 전역 에러를 클리어한다.

### 8. TDD 테스트 케이스 — `test_project_task_mapping.py` 검증

`tests/test_project_task_mapping.py`에 4개의 테스트가 구현되어 있으며, 각각 `project_id` 빈 값 유효성 검사, 정상 프로젝트 생성, `task_type` Literal 제한 검증, `status` Literal 제한 검증을 커버한다. `test_task_retry_relation`은 동일 `project_id` 하위에 복수 태스크가 공존 가능함을 관계적으로 검증하고 있어 1:N 매핑 설계 명세를 정확히 반영한다. `ProjectModel`과 `TaskModel` 양쪽 모두 `from main import` 방식으로 직접 임포트되어 있어, 모델 정의와 테스트가 동일 소스를 참조한다.

### 9. HOT-001 `Film` import 누락 JSX 크래시 해결

`RaptorWorkflow.tsx` 상단 import 구문에 `Film`이 올바르게 선언되어 있으며, JSX 내에서 `<Film />` 컴포넌트가 사용되고 있음을 확인했다.

### 10. NEW-002 `image_source: 'manual'` 수동 업로드 보호

`handleGenerateImages`에서 `scene.image_source === 'manual'` 조건으로 수동 업로드 씬을 AI 재생성 대상에서 제외하는 로직이 유지되어 있다.

---

## [Pending] 잔여 리스크 및 추적 관찰 항목

### RISK-002 — 과금 단가 동적화 미완성

`kie_pricing.json` 기반의 동적 요금 갱신 체계가 아직 구현되지 않았다. `veo_fast` 단가 정식 추가 및 다중 사용자 스토리지 쿼터 격리 알고리즘은 현재 코드에 없으며 베타 단일 사용자 기준으로만 운용된다.

### RISK-003 — FFmpeg 폰트 경로 크로스플랫폼 결함

`ffmpeg_worker.py` 내에 `font_path = "C:/Windows/Fonts/malgun.ttf"` 하드코딩이 그대로 유지되고 있다. Linux 또는 Docker 배포 환경에서는 자막 합성이 실패한다. 이번 패치에서 개선이 이루어지지 않았다.

### NEW-001 — SSR 환경 `hasHydrated` 레이스 컨디션

`useWorkflowStore.ts`에서 `createJSONStorage(() => (typeof window !== 'undefined' ? localStorage : sessionStorage))` 분기로 SSR 안전성을 부분 처리하고 있으나, `onRehydrateStorage` 내에서 직접 상태를 뮤테이션하는 패턴이 SSR 빌드 환경에서 사이드 이펙트를 일으킬 가능성이 잔존한다.

### NEW-005 — Ghost User 로컬 스토리지 노출

Zustand persist 스토어에 `user` 객체가 직렬화되어 저장되는 구조가 유지되고 있으며, 세션 만료 후 새로고침 시 Supabase 비동기 세션 체크 전 일시적으로 만료된 사용자 정보가 노출될 가능성이 잔존한다.

### N-02 — CI/CD 테스트 환경 `COOKIE_ENCRYPTION_KEY` 의존

`test_project_task_mapping.py`가 `from main import`를 직접 수행하므로, CI 환경에서 `.env`가 없을 경우 `main.py` 최상단의 `COOKIE_ENCRYPTION_KEY` Fail-Fast 검증이 `RuntimeError`를 던지며 모든 테스트가 import 단에서 즉시 실패한다. 현재 테스트 파일에 `os.environ.setdefault("COOKIE_ENCRYPTION_KEY", ...)` 같은 방어 코드가 없다.

### N-05 — FIFO 임계값 이중 기준

`check_and_enforce_user_limits`(프로젝트 기준 10개, 9개 보존)와 `webhook_kie`(레거시 DB 기준 50개 보존)의 이중 정제 기준이 아키텍처 개편 이후에도 여전히 공존하고 있다. 신구 아키텍처가 혼재하므로 단일 정제 함수 통합이 필요하다.

### PND-001 / PND-002 — 미사용 Import Dead Code

`RaptorWorkflow.tsx` L.4의 `Share2`, `RefreshCw` import가 이번 패치에서도 제거되지 않았다. ESLint 경고 및 번들 사이즈 오염이 지속된다.

---

## [New] 신규 식별 리스크 및 개선 권장 사항

### NEW-A — `handleRenderVideo`의 `scene_update` 처리 시 불변성 오류 잠재 위험

`handleRenderVideo` 내 SSE 스트림 파싱 중 `data.scene_update`를 수신하면 `const updatedScript = [...finalAssets.script]`로 스프레드하여 업데이트한다. 그런데 이 시점의 `finalAssets`는 클로저 캡처 값으로, 렌더링이 긴 경우 중간에 다른 상태 업데이트가 발생하면 구버전 스냅샷으로 덮어쓰는 stale closure 문제가 생길 수 있다. `setFinalAssets`에 함수형 업데이트 패턴(`prev => ...`)을 적용해야 한다.

### NEW-B — `handleRenderVideoFromScratch`의 50ms setTimeout 레이스 컨디션 (N-08 지속)

```typescript
setTimeout(() => handleRenderVideo(), 50);
```
이 패턴은 React 상태 플러시 타이밍에 대한 보장이 없어 저사양 기기에서 구버전 씬 데이터로 렌더링이 시작될 수 있다. `useEffect` + 렌더 트리거 플래그(`useRef`) 방식으로 교체가 필요하다.

### NEW-C — N-09 Claude Opus 모델 레이블/Value 불일치 지속

`RaptorWorkflow.tsx` Step 1 Claude 모델 선택 셀렉트 박스에서 option value는 `"claude-opus-4-7"`이나 UI 레이블은 `"Claude Opus 4.8"`로 표기되어 있다. 실제 API 호출 모델과 사용자에게 보이는 이름이 불일치한다.

### NEW-D — `record_user_asset` 함수의 구/신 아키텍처 이중 기록 위험

`/api/render-stream` 완료 후 `record_user_asset` 함수가 `proj_{task_id}` 형태의 가상 `project_id`를 생성하여 `PROJECTS_DB_PATH`에 독립 기록한다. 이 경로는 `create_project_in_db`를 통해 프론트엔드에서 발급한 공식 `project_id`와 별도로 중복 프로젝트 레코드를 생성하므로, `get_dashboard_projects` 조회 시 동일 작업이 두 개의 프로젝트로 표시될 수 있다.

### NEW-E — `check_and_enforce_user_limits` 내 Cascade 삭제 시 태스크 DB 로드 비효율

프로젝트 FIFO 정제 로직에서 물리 파일 삭제를 위해 `tasks.json` 전체를 메모리에 로드하는데, 이 함수는 모든 렌더 요청 시작마다 호출된다. 태스크 수가 증가할수록 I/O 성능이 선형 저하된다. 인덱스 기반 조회 또는 경량 DB로의 마이그레이션을 권장한다.

### NEW-F — N-06 Mock 자동 인증 우회 로직 프로덕션 차단 미완성

`RaptorWorkflow.tsx` `useEffect` 내에서 `isKeyConfigured`가 true이면 Mock user를 즉시 발급하여 step을 1로 전환하는 로직이 그대로 유지되어 있다. 현재 `ENV` 분기 없이 항상 활성화된 상태로 실서비스 배포 시 인증 체계 무력화 위험이 지속된다.

### NEW-G — `useWorkflowStore`의 `csrfToken` localStorage 직렬화 보안 이슈

`partialize`에 `csrfToken`이 포함되어 있지 않아 localStorage에 저장되지 않는 것은 올바르나, `isKeyConfigured` 플래그는 localStorage에 퍼시스트된다. 이 플래그가 `true`이면 Mock 자동 로그인이 활성화되므로, 공용 기기에서 다른 사용자가 세션을 이어받는 취약점이 존재한다.