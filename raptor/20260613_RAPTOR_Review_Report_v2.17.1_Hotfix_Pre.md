이제 코드 전체 맥락을 파악했습니다. 사전 리뷰 보고서를 작성하겠습니다.

---

# 📋 RAPTOR v2.17.1 핫픽스 실행 계획 사전 리뷰 보고서 (Pre-Review)

**리뷰 기준일:** 2026-06-13
**리뷰어:** Claude Sonnet 4.6 (자동화 아키텍처 리뷰)
**대상 브랜치:** master (현재 상태 기준 코드 직접 검증)

---

## 1. 실행 계획의 완결성 및 안전성 평가

### 프론트엔드 픽스 (R-1, R-2, R-3)

---

**[R-1] Stage 5 트래커 action 오결선 수정** → **PASS**

코드 검증 완료. `RaptorWorkflow.tsx:1760`에서 결함이 직접 확인됨:

```typescript
// 현재 (버그)
{ id: 5, name: '최종 렌더링', ..., action: handleGenerateClips, actionLabel: '최종 렌더링 재시도' },

// 수정 후 (정상)
{ id: 5, name: '최종 렌더링', ..., action: handleRenderFinal, actionLabel: '최종 렌더링 재시도' },
```

원인 진단 정확도: **완벽**. 트래커의 "재시도" 버튼이 Stage 5 오류 발생 시 `handleGenerateClips`를 호출하여 완전히 잘못된 흐름(클립 재생성)으로 진입하는 버그가 실코드에서 확인됨. Fix는 완벽하다.

---

**[R-2] handleRenderFinal CSRF 재발급 방어 로직 누락** → **PASS**

코드 검증 완료. 두 함수 간 비대칭이 실코드에서 확인됨:

```typescript
// handleGenerateClips (정상, Line 544~557)
let activeCsrfToken = store.csrfToken;
if (!activeCsrfToken) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/auth/csrf-token`, { method: 'GET', credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      if (data.csrf_token) { store.setCsrfToken(data.csrf_token); activeCsrfToken = data.csrf_token; }
    }
  } catch (err) {}
}
if (activeCsrfToken) headers['X-CSRF-Token'] = activeCsrfToken;

// handleRenderFinal (취약, Line 671~672) — 재발급 로직 완전 누락
let activeCsrfToken = store.csrfToken;
if (activeCsrfToken) headers['X-CSRF-Token'] = activeCsrfToken;
```

원인 진단 정확도: **완벽**. 세션 만료 또는 토큰 초기화 상황에서 `handleRenderFinal`만 CSRF 검증 실패(403)로 침묵 종료하는 취약점이 실코드에서 확인됨. Fix 방향 정확.

---

**[R-3] Step 4 버튼 로딩 스피너 조건 오결선** → **PASS**

코드 검증 완료. `RaptorWorkflow.tsx:1897` 문제 확인:

```tsx
// 현재 (버그): Step 5 렌더링 중에도 Step 4 버튼이 "클립 생성 중..." 스피너 표시
{isRendering ? (
  <><Loader2 .../> <span>클립 생성 중...</span></>
) : (
  <><Film .../> <span>비디오 클립 생성 (Step 4)</span></>
)}

// 수정 후 (정상): loading(클립 생성)일 때만 스피너, isRendering(최종 렌더링) 중엔 기본 버튼
{loading && !isRendering ? (
  <><Loader2 .../> <span>클립 생성 중...</span></>
) : (
  <><Film .../> <span>비디오 클립 생성 (Step 4)</span></>
)}
```

`loading`과 `isRendering`은 별개의 상태 플래그로, `loading`은 `handleGenerateClips`가, `isRendering`은 `handleRenderFinal`이 관리한다. Fix 후 두 Stage의 UI 상태가 올바르게 분리됨. 단, `disabled={isRendering || loading}` 조건(Line 1894)은 이미 정확하여 건드릴 필요 없음.

---

### 백엔드 픽스 (R-5)

**[R-5] render-final 예외 처리부 UnboundLocalError 방어** → **CONDITIONAL PASS** ⚠️

코드 검증 완료. `main.py:2235~2278` 전체 구조 확인:

```python
try:
    task_id = f"task_{int(time.time())}"  # Line 2236: 첫 줄에서 정의됨
    if request.project_id:
        await create_task_in_db(...)      # 여기서 예외 가능
    gen = ffmpeg_worker.render_video(...) # 여기서도 예외 가능
    try:
        async for item in gen:
            ...
    finally:
        await gen.aclose()
except Exception as e:
    if request.project_id:
        await update_task_in_db(task_id, "failed", error=str(e))  # Line 2277
    yield ...
```

**진단:** 현재 코드에서 `task_id`는 `try` 블록의 첫 줄(Line 2236)에서 할당되므로, 이후 모든 예외 경로에서 `task_id`는 이미 바인딩되어 있음. 순수 이론적으로 `UnboundLocalError`가 발생하는 경우는 사실상 없음. 그러나 `task_id = None`으로 명시적 초기화하는 방어적 코딩 자체는 올바른 방향이다.

**단, 설계에 잠재적 결함이 존재함** — 아래 3번 섹션 참조.

---

## 2. 기술 부채 관리 전략 (R-4 Skip) 타당성 평가

**[R-4] 씬별 다중 AsyncClient 개방 보류 결정** → **PASS**

```
판단 근거:
- 현재 아키텍처: N개 씬 처리 시 각 씬이 독립적 AsyncClient 생성
- 운용 환경: 소규모 동시 사용자 (RAPTOR Classic 베타 10 프로젝트/월 제한)
- 리스크 수준: 일반적 N=3~8 씬에서 Connection Pool 압박 실질적 없음
- 연결 누수 여부: async context manager 또는 finally 블록으로 정상 해제됨
```

소규모 N 환경에서는 연결 누수 없이 정상 해제되고 있어 당장의 운영 리스크는 낮다. 세션 공유 리팩토링은 `asyncio.gather` 병렬 처리 구조 개편과 맞물려야 하는 고비용 작업이므로, 이를 분리하여 v2.18.x 이후로 연기하는 전략은 **합리적인 기술 부채 관리**다. 다만 MAU가 증가할 경우 조기 착수가 권장된다.

---

## 3. 예상되는 부작용 및 잠재적 취약점

### 🔴 중요도 HIGH: R-5 Fix의 방어 조건 불완전

**현재 제안된 R-5 Fix:**
```python
# 함수 최상단에 추가
task_id = None
# ... (기존 코드)
```

**문제:** `except` 블록의 guard 조건이 `task_id`의 `None` 여부를 체크하지 않음:
```python
except Exception as e:
    if request.project_id:                           # task_id가 None인지 확인하지 않음
        await update_task_in_db(task_id, "failed")   # task_id=None이면 DB 오염 위험
```

`task_id = None`이고 `request.project_id`가 존재하면, `supabase.table("tasks").update(...).eq("task_id", None)`이 실행되어 `task_id IS NULL`인 모든 레코드를 `failed`로 일괄 업데이트할 수 있음. 이는 이론적 경로지만 방어 코드가 오히려 공격면을 만드는 상황이다.

**권장 수정안:**
```python
except Exception as e:
    if request.project_id and task_id:  # task_id None 가드 추가
        await update_task_in_db(task_id, "failed", error=str(e))
    yield f"data: {json.dumps({'error': f'FFmpeg Error: {str(e)}'})}\n\n"
```

---

### 🟡 중요도 MEDIUM: R-2 Fix 코드 복붙 시 `activeCsrfToken` 재할당 누락 위험

R-2 Fix 구현 시 `handleGenerateClips`에서 패턴을 복사할 때, 다음 두 줄이 **반드시 함께** 있어야 함:
```typescript
store.setCsrfToken(data.csrf_token);  // store 갱신
activeCsrfToken = data.csrf_token;   // 지역 변수 갱신 (이 줄 빠지면 헤더에 반영 안됨)
```
지역 변수 재할당이 누락되면 재발급된 토큰이 `headers`에 세팅되지 않아 R-2가 수정 후에도 동일하게 403으로 실패한다. 구현 시 주의 요망.

---

### 🟢 중요도 LOW: R-1 Fix 후 `handleRenderFinal` 파라미터 시그니처 확인

Stage 트래커의 `action`이 호출될 때 인자 없이 `stage.action()` 형태로 호출되는지 확인 필요. `handleRenderFinal`은 파라미터가 없으므로 문제없을 가능성이 높으나, 트래커 렌더링 코드에서 인자가 주입될 경우 무시 처리가 되는지 확인 권장.

---

## 4. TDD 채점표

| 항목 | 결함 ID | 원인 진단 정확도 | Fix 설계 완결성 | 부작용 위험 | 판정 |
|------|---------|--------------|--------------|------------|------|
| Stage 5 트래커 action 오결선 | R-1 | ✅ 정확 | ✅ 완벽 | 없음 | **PASS** |
| CSRF 재발급 로직 누락 | R-2 | ✅ 정확 | ✅ 완벽 (구현 주의 필요) | 낮음 | **PASS** |
| Step 4 스피너 조건 오결선 | R-3 | ✅ 정확 | ✅ 완벽 | 없음 | **PASS** |
| render-final UnboundLocalError 방어 | R-5 | ⚠️ 이론적 | ⚠️ 조건문 보완 필요 | 중간 (DB 오염) | **CONDITIONAL PASS** |
| 다중 AsyncClient 보류 | R-4 | ✅ 정확 | N/A | 낮음 (스케일업 시 재검토) | **PASS** |

---

## 5. 최종 결론 및 코딩 진입 승인 여부

### **APPROVED (조건부 승인) — 단, R-5 Fix 수정 후 진입**

R-1, R-2, R-3의 설계는 원인 진단이 정확하고 Fix 방향이 완벽하다. 즉시 코딩 가능.

R-5는 방어 코드의 의도는 올바르나, `except` 블록에서 `task_id = None`인 경우 DB 오염을 방지하는 가드 조건이 미흡하다. **아래 한 줄 수정을 R-5 Fix 사양에 반드시 포함할 것:**

```python
# main.py:2235 위 — task_id = None 초기화 추가 (계획 유지)
task_id = None

# main.py:2276 — 가드 조건 강화 (계획 수정 필요)
if request.project_id and task_id:  # ← 'and task_id' 추가
    await update_task_in_db(task_id, "failed", error=str(e))
```

이 한 줄 수정을 계획서에 반영 후 코딩 진입을 승인한다.
