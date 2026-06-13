# [Goal Description]
RAPTOR Classic(로컬 FFmpeg 기반) 서버의 부하를 방지하기 위해 2슬롯 렌더링 큐 제한(Semaphore)을 적용하고, 이를 사용자에게 직관적으로 알리기 위한 신호등(초록/주황/빨강) 상태 UI를 추가합니다. 더불어 사용자가 언제든(신호등 상태와 무관하게) 렌더링 에셋을 ZIP으로 다운받아 CapCut 등에서 수동 편집할 수 있는 폴백(Fallback) 기능을 스트리밍 API로 구현합니다.

## User Review Required

> [!WARNING]
> **신호등 카운트 기준:** 렌더링을 시도한 작업이 `pending` 상태에서 대기 중이거나 실제 `processing` 중인 개수를 모두 카운트하여 2개 이상일 때 '빨강(포화)'으로 표시합니다.
> **ZIP 에셋 수집 범위:** 프로젝트의 최초 분석 결과(`plan_snapshot`)에 저장된 `scenes` 데이터를 기반으로 배경 이미지/비디오 URL을 수집하고, 임의 생성된 대본 텍스트 등을 스트림 아카이브에 포함할 예정입니다. (음성 파일의 경우 URL이 보존되어 있지 않을 수 있어 TTS 프롬프트 텍스트를 위주로 담습니다). 동의하시나요?

## Open Questions

> [!IMPORTANT]
> 1. 신호등이 '빨강(2개 이상 대기/진행 중)'일 때 `[AI 영상 렌더링]` 버튼을 비활성화하고 "서버 포화 상태: 대기" 등의 안내 문구를 보여주려 합니다. 문구에 특별한 요구사항이 있으신가요?
> 2. ZIP 파일 다운로드 시 압축 파일의 이름을 `raptor_assets_{task_id}.zip`로 설정할 예정입니다. 괜찮으신가요?

## Proposed Changes

---

### Backend (FastAPI - 인프라 방어 및 신호등 API)

#### [MODIFY] `backend/services/ffmpeg_worker.py`
- `FFmpegWorker.__init__` 내부에 `self.render_semaphore = asyncio.Semaphore(2)` 추가.
- `render_video` 비동기 제너레이터 전체 블록을 `async with self.render_semaphore:` 로 감싸 동시 실행을 물리적으로 2개로 락킹.

#### [MODIFY] `main.py`
- **신호등 카운트 API 추가:** `/api/status/render` 엔드포인트를 신설하여 `supabase` DB의 `tasks` 테이블에서 `task_type="final_render"` 이면서 `status`가 `"pending"` 또는 `"processing"`인 레코드의 수를 카운트하여 반환.
- **ZIP 스트리밍 다운로드 API 추가:** `/api/tasks/{task_id}/download-assets` 신설. `zipstream` 패키지(또는 메모리 내 Generator)를 활용하여 프로젝트의 `plan_snapshot`에 명시된 이미지 URL들을 `httpx`로 즉시 다운로드하며 스트리밍 방식으로 ZIP 압축 반환 (서버 OOM 방어).

---

### Frontend (UI/UX - 신호등 및 ZIP 상시 다운로드)

#### [MODIFY] `src/components/RaptorWorkflow.tsx` (또는 해당 렌더링 뷰 UI)
- `setInterval`을 활용해 5초 주기로 `/api/status/render`를 폴링하는 로직 추가 (의존성 최소화).
- 반환된 Count 개수에 따라:
  - 0개: 🟢 **초록 (원활)**
  - 1개: 🟠 **주황 (보통)**
  - 2개 이상: 🔴 **빨강 (포화 - 렌더링 불가)**
- UI 상단 렌더링 버튼 옆에 직관적인 신호등 UI 렌더링 및 빨강 상태 시 렌더링 버튼 비활성화(`disabled`).
- 에셋 다운로드 버튼(`[원본 에셋 ZIP 다운로드]`) 추가 및 항상 활성화. (신호등 상태와 독립적 동작 보장).

## Verification Plan

### Automated Tests
- 없음. (프론트/백엔드 폴링 및 로컬 테스트로 직접 검증)

### Manual Verification
- 신호등 API가 현재 DB의 `pending/processing` 개수를 올바르게 반환하는지 테스트.
- 렌더링을 3번 연속으로 시도하여 2개는 병렬로 처리되고, 1개는 세마포어에 의해 대기 상태에 머무는지 `backend` 로그와 UI로 시각적 확인.
- 대기 중인 상태에서도 ZIP 다운로드가 즉각 반응하여 성공적으로 메모리 초과 없이 다운로드되는지 검증.
