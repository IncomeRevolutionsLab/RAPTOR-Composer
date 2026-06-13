이제 전체 검증 데이터가 확보됐습니다. 보고서를 작성합니다.

---

# 📋 RAPTOR v2.17.0 렌더링 파이프라인 완전 분리 사후 리뷰 보고서 (Post-Review)

**검토 기준일:** 2026-06-13  
**검토 대상:** `main.py` (L1873–L2287), `src/components/RaptorWorkflow.tsx` (L519–L1924)

---

## 1. 백엔드 아키텍처 분리 및 자원 관리 평가

### 1-1. KIE API 커넥션 정리 완결성 — **PASS**

`main.py:1958`에서 `client = httpx.AsyncClient()`를 수동 생성하고, `finally` 블록(`L2136–2138`)에서 `await client.aclose()`를 호출하는 구조가 확인됐다.

```python
# L1958–2138 요약
client = httpx.AsyncClient()
try:
    ...  # KIE API 요청 + 폴링
    try:
        while True:  # 폴링 루프
            ...
    finally:
        TASK_EVENTS.pop(task_id, None)   # inner finally
finally:
    await client.aclose()  # ← L2138, outer finally
```

**모든 종료 경로(성공 / 예외 / `CancelledError`)에서 `aclose()`가 반드시 호출된다.** Errno 11 자원 누수는 구조적으로 차단됨.

> 단, `client` 인스턴스는 씬 내부(`process_scene_inner`) 마다 생성되므로 N개 씬이 동시 실행되면 N개의 `httpx.AsyncClient`가 동시에 열린다. N이 10 미만인 정상 사용 범위에서는 문제없으나 씬 수 증가 시 리소스 압박은 존재함 (개선 권고 수준, 블로커 아님).

---

### 1-2. SSE 스트리밍 안정성 제어 — **PASS (중요 관찰 포함)**

**`/api/generate-video-clips`** 의 끊김 감지는 **두 계층**에서 중첩 보호된다.

| 위치 | 코드 | 설명 |
|---|---|---|
| L2046 | `if await raw_request.is_disconnected()` | 씬별 폴링 루프 내부 |
| L2181 | `if await raw_request.is_disconnected()` | `as_completed` 결과 수집 루프 |

연결 끊김 감지 → `asyncio.CancelledError` 발생 → `L2147–2151` `except asyncio.CancelledError` 핸들러에서 DB 작업 상태를 `"failed"`로 기록 후 re-raise. 완전한 연쇄 처리.

**`/api/render-final`** 도 `L2255`에서 동일 패턴을 사용하며, `gen.aclose()`가 `finally`(`L2273–2274`) 블록에 배치되어 FFmpeg 제너레이터의 자원을 보장 회수한다.

---

## 2. 프론트엔드 로직 및 UI/UX 분리 평가

### 2-1. 2단계 함수 분리 안정성 — **CONDITIONAL PASS (버그 1건 포함)**

`handleGenerateClips`(`L519`)와 `handleRenderFinal`(`L651`)은 각각 독립적인 `try/catch/finally` 블록을 보유하고, 호출 엔드포인트도 `/api/generate-video-clips`와 `/api/render-final`로 완전히 분리됐다.

상태 관리 분리도 확인됨:
- Step 4(`handleGenerateClips`): `setLoading(true, ...)` 사용
- Step 5(`handleRenderFinal`): `setRenderStatus(true, 50)` + `setLoading(true, ...)` 사용

**⚠️ 발견된 버그 (RISK-LOW):** `L1760` 스테이지 트래커 배열에서 Stage 5의 `action`이 `handleRenderFinal` 대신 `handleGenerateClips`로 잘못 연결되어 있다.

```tsx
// L1760 — 버그: action이 잘못된 함수를 참조
{ id: 5, name: '최종 렌더링', ..., action: handleGenerateClips, actionLabel: '최종 렌더링 재시도' }
// 올바른 코드:                      action: handleRenderFinal
```

스테이지 트래커의 "최종 렌더링 재시도" 버튼을 누르면 Step 5가 아닌 Step 4가 실행된다. 메인 Step 5 버튼(`L1905`)은 올바르게 `handleRenderFinal`을 호출하므로 일반 사용자 경로에서는 무영향이나, 오류 복구 흐름에서 혼란을 유발할 수 있다.

**⚠️ 추가 관찰 (RISK-LOW):** `handleRenderFinal`의 CSRF 처리(`L671–673`)는 토큰이 없을 경우 자동 재발급 로직 없이 그냥 스킵한다. `handleGenerateClips`는 서버에서 CSRF 토큰을 재발급(`L544–556`)하는 반면, `handleRenderFinal`에는 해당 방어 로직이 없어 세션 만료 후 Step 5가 403으로 실패할 수 있다.

---

### 2-2. UI 버튼 및 신호등 컴포넌트 격리 적절성 — **PASS (조건부)**

**Step 5 버튼 활성화 조건(`L1906`):**
```tsx
disabled={isRendering || loading || 
  !(finalAssets?.script && finalAssets.script.every((s: any) => s.video_url || s.use_image_only))}
```
모든 씬의 `video_url` 또는 `use_image_only` 충족 시에만 활성화된다는 명세와 정확히 일치. ✓

**신호등 위치:** `L1919–1926`의 서버 상태 표시 블록은 두 버튼(Step 4, Step 5) 이후의 별도 `div`에 위치한다. 명세에서 "Step 5 버튼 영역에만 국한"을 요구했으나, 실제로는 두 버튼 아래 동일 컨테이너 내에 배치되어 있다. Step 4 버튼과 시각적으로 분리되지는 않지만, 의미상으로는 FFmpeg 렌더링 대기열 정보를 나타내므로 실용적 혼란은 최소화됐다. 엄밀한 UI 격리 기준으로는 부분 달성.

**Step 4 버튼 레이블 불일치 (UX 소결함, `L1897–1901`):**
```tsx
{isRendering ? (
  <><Loader2 .../> <span>클립 생성 중...</span></>  // isRendering은 Step 5의 상태
) : (
  <><Film .../> <span>비디오 클립 생성 (Step 4)</span></>
)}
```
`handleGenerateClips`는 `setLoading(true)`를 사용하지만 버튼 레이블은 `isRendering`(Step 5의 상태 변수)을 본다. 클립 생성 중 버튼이 `disabled`이지만 스피너 텍스트는 표시되지 않아 사용자가 진행 중임을 인지하기 어렵다.

---

## 3. 잔여 위험 요소

| # | 위험 요소 | 위치 | 심각도 |
|---|---|---|---|
| R-1 | Stage 5 트래커 `action`이 `handleGenerateClips`로 잘못 연결 | `RaptorWorkflow.tsx:1760` | **중간** (오류 복구 경로 오작동) |
| R-2 | `handleRenderFinal` CSRF 재발급 로직 누락 | `RaptorWorkflow.tsx:671–673` | **낮음** (세션 만료 시 Step 5 403 실패 가능) |
| R-3 | Step 4 버튼 레이블이 `isRendering`(Step 5 상태)를 참조 | `RaptorWorkflow.tsx:1897` | **낮음** (UX 피드백 소결함) |
| R-4 | N 씬 동시 실행 시 N개 `AsyncClient` 동시 개방 | `main.py:1958` | **낮음** (소규모 N에서 무해) |
| R-5 | `render-final` 오류 시 `task_id`가 `try` 외부에서 참조됨 | `main.py:2276–2277` | **낮음** (NameError 가능성 — `task_id`가 `create_task_in_db` 이전에 예외 발생 시) |

---

## 4. TDD 채점표

| 검증 항목 | 결과 |
|---|---|
| `render-stream` 엔드포인트 완전 제거 확인 | ✅ PASS |
| `generate-video-clips` 엔드포인트 신설 | ✅ PASS |
| `render-final` 엔드포인트 신설 | ✅ PASS |
| `client.aclose()` finally 블록 정위치 | ✅ PASS |
| 폴링 루프 내 `is_disconnected()` 감지 | ✅ PASS |
| `as_completed` 루프 내 `is_disconnected()` 감지 | ✅ PASS |
| FFmpeg gen `aclose()` finally 보장 | ✅ PASS |
| `handleGenerateClips` / `handleRenderFinal` 분리 | ✅ PASS |
| Step 5 버튼 비활성화 조건 (`every video_url || use_image_only`) | ✅ PASS |
| Step 5 버튼 클릭 → `handleRenderFinal` 호출 | ✅ PASS |
| 신호등 Step 5 영역 인접 배치 | ⚠️ PARTIAL |
| Stage 트래커 Stage 5 `action` 정확성 | ❌ FAIL |
| Step 4 버튼 레이블 `loading` 상태 반영 | ❌ FAIL |
| `handleRenderFinal` CSRF 재발급 방어 | ⚠️ PARTIAL |

**종합: 10 PASS / 2 FAIL / 2 PARTIAL**

---

## 5. 최종 결론 및 잔여 권고사항

**핵심 목표(Errno 11 차단, 엔드포인트 분리)는 완전히 달성됐다.** `client.aclose()`의 `finally` 배치와 이중 계층 연결 끊김 감지는 명세 의도를 충실히 구현한다.

**즉시 수정 권고 (R-1):**
```tsx
// RaptorWorkflow.tsx:1760
// 변경 전:
action: handleGenerateClips, actionLabel: '최종 렌더링 재시도'
// 변경 후:
action: handleRenderFinal, actionLabel: '최종 렌더링 재시도'
```

**단기 권고 (R-2, R-3):**
- `handleRenderFinal`에 CSRF 재발급 로직(`handleGenerateClips:L544–556`)을 동일하게 이식
- Step 4 버튼 레이블 조건을 `isRendering`에서 `loading && !isRendering`으로 수정

---

**결론: v2.17.0 분리 수술의 핵심 아키텍처는 안정적이다. R-1 버그(Stage 5 트래커의 잘못된 함수 참조)는 오류 복구 경로에서 사용자 혼란을 유발하므로 다음 핫픽스 대상으로 권고한다.**
