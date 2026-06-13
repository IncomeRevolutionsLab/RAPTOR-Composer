모든 핵심 패치 포인트 확인 완료. 보고서를 작성합니다.

---

# 📋 RAPTOR v2.17.1 핫픽스 사후 리뷰 보고서 (Post-Review)

**리뷰 일시:** 2026-06-13
**검토 파일:** `main.py`, `src/components/RaptorWorkflow.tsx`

---

## 1. [R-5] 백엔드 예외 처리 가드 조건 검증

### 판정: ✅ PASS

**검증 내용:**

| 항목 | 위치 | 코드 | 결과 |
|------|------|------|------|
| `task_id = None` 초기화 | `main.py:2235` | `task_id = None` (try 블록 진입 전) | ✅ 정상 |
| 가드 조건 강화 | `main.py:2277` | `if request.project_id and task_id:` | ✅ 정상 |

**분석:**
- `task_id = None`이 `generate_stream()` 내부, `try` 블록 **진입 전** (라인 2235)에 정확하게 초기화되어 있다. `task_id = f"task_{int(time.time())}"` 할당이 `try` 블록 **내부** (라인 2237)에 위치하므로, 해당 할당 이전에 예외 발생 시 `task_id`가 `None`으로 유지되는 방어 경로가 완전히 확보되었다.
- `except Exception as e:` 블록에서 `if request.project_id and task_id:` 이중 조건이 라인 2277에 적용되어 있다. `task_id`가 `None`인 경우(즉, `create_task_in_db` 호출 전 예외 발생 시) `update_task_in_db` 호출이 원천 차단된다. **Pre-Review에서 지적된 DB 오염 가능성이 완벽하게 제거되었다.**

---

## 2. [R-1, R-2, R-3] 프론트엔드 핫픽스 검증

### [R-1] Stage 5 트래커 버튼 action 교정

### 판정: ❌ FAIL

**검증 결과:**

```tsx
// RaptorWorkflow.tsx:1772 — 현재 코드 (버그 잔존)
{ id: 5, name: '최종 렌더링', ..., action: handleGenerateClips, actionLabel: '최종 렌더링 재시도' },
```

**문제:** Stage 5 트래커 카드의 `action`이 `handleGenerateClips`로 **패치되지 않은 상태**다. 계획서 명세(`handleRenderFinal`로 교정)가 미적용되었다. Stage 5 카드의 재시도 버튼을 클릭하면 비디오 클립 생성(`handleGenerateClips`)이 잘못 호출된다. **핵심 UX 버그가 코드베이스에 현존한다.**

---

### [R-2] handleRenderFinal 내 CSRF 자동 재발급 로직

### 판정: ✅ PASS

**검증 내용 (`RaptorWorkflow.tsx:671–684`):**

```tsx
let activeCsrfToken = store.csrfToken;
if (!activeCsrfToken) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/auth/csrf-token`, ...);
    if (res.ok) {
      const data = await res.json();
      if (data.csrf_token) {
        store.setCsrfToken(data.csrf_token);
        activeCsrfToken = data.csrf_token;  // ← 지역 변수 정상 할당
      }
    }
  } catch (err) {}
}
if (activeCsrfToken) headers['X-CSRF-Token'] = activeCsrfToken;
```

`activeCsrfToken` 지역 변수가 정상 선언·할당되며, CSRF 토큰 미보유 시 자동 재발급 후 헤더에 반영하는 흐름이 완전하다.

---

### [R-3] Step 4 버튼 로딩 스피너 조건 교정

### 판정: ✅ PASS

**검증 내용 (`RaptorWorkflow.tsx:1909`):**

```tsx
{loading && !isRendering ? (
  <><Loader2 className="w-4 h-4 animate-spin text-blue-300" /> <span>클립 생성 중...</span></>
) : (
  <><Film className="w-5 h-5" /> <span>비디오 클립 생성 (Step 4)</span></>
)}
```

`loading && !isRendering` 조건이 정확히 적용되어 있다. 최종 렌더링(`isRendering=true`) 중에는 Step 4 버튼이 로딩 스피너를 표시하지 않으며, Step 4 자체 작업 중(`loading=true, isRendering=false`)에만 스피너가 동작한다.

---

## 3. 구현과 계획서(v2) 간 일치도 평가

| 항목 | 계획서 명세 | 실제 구현 | 일치도 |
|------|------------|----------|--------|
| R-5 `task_id = None` 초기화 | `render-final` 상단 추가 | `main.py:2235` 적용 | ✅ 일치 |
| R-5 가드 조건 `and task_id` | `except` 블록 내 이중 조건 | `main.py:2277` 적용 | ✅ 일치 |
| R-1 Stage 5 action 교정 | `handleRenderFinal`로 변경 | `handleGenerateClips` 유지 (미적용) | ❌ **불일치** |
| R-2 CSRF 자동 재발급 | `handleRenderFinal` 내 추가 | `RaptorWorkflow.tsx:671–684` 적용 | ✅ 일치 |
| R-3 스피너 조건 교정 | `loading && !isRendering` | `RaptorWorkflow.tsx:1909` 적용 | ✅ 일치 |

---

## 4. 최종 결론

### 판정: ❌ FAIL (조건부 — [R-1] 단일 잔존 결함)

**요약:**
- 백엔드 패치 (R-5): 완전히 정상 적용. DB 오염 방어 구조 완벽.
- 프론트엔드 패치 (R-2, R-3): 정상 적용.
- **[R-1] Stage 5 트래커 버튼 `action`이 `handleGenerateClips`로 유지되어 있으며, `handleRenderFinal`로의 교정이 누락됨.** 이로 인해 Stage 5 "최종 렌더링 재시도" 버튼 클릭 시 비디오 클립 생성 핸들러가 잘못 호출되는 UX 버그가 현존한다.

**권장 즉각 조치:**

```tsx
// RaptorWorkflow.tsx:1772 — 수정 필요
// Before
{ id: 5, ..., action: handleGenerateClips, actionLabel: '최종 렌더링 재시도' },

// After
{ id: 5, ..., action: handleRenderFinal, actionLabel: '최종 렌더링 재시도' },
```

이 1줄 수정을 v2.17.2 패치로 즉시 적용하면 전체 핫픽스가 완결된다.
