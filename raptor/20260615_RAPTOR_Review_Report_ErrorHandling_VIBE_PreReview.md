# Claude Code 리뷰 레포트: 교차 환경 에러 (401, 403, 500) 세분화 및 백엔드 무결성 방어 

## `src/lib/api-client.ts` 변경 (2곳)

**① 파일 상단 — `ApiError` 클래스 추가**
```typescript
export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}
```

**② `!response.ok` 블록 — 상태별 메시지 분기**
```typescript
if (!response.ok) {
  const errorText = await response.text();
  let detail = errorText;
  try {
    const json = JSON.parse(errorText);
    detail = json.detail || errorText;
  } catch (e) {}

  let userMessage: string;
  if (response.status === 401) {
    userMessage = 'API 키가 유효하지 않거나 만료되었습니다. 설정에서 API 키를 다시 입력해 주세요.';
  } else if (response.status === 403) {
    userMessage = `접근이 거부되었습니다. CSRF 토큰이 만료되었을 수 있습니다. 페이지를 새로고침 후 다시 시도해 주세요. (${detail})`;
  } else if (response.status === 500) {
    userMessage = `서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요. (${detail})`;
  } else {
    userMessage = `API Error (${response.status}): ${detail}`;
  }
  throw new ApiError(response.status, userMessage);
}
```

---

## `src/components/AuthDashboard.tsx` 변경 (1곳)

**`fetchDashboardData` — HTTP 상태별 에러 + toast에 `err.message` 사용**
```typescript
if (!res.ok) {
  if (res.status === 401) {
    throw new Error('API 키가 유효하지 않거나 만료되었습니다. 설정에서 API 키를 다시 입력해 주세요.');
  } else if (res.status === 403) {
    throw new Error('접근이 거부되었습니다. 페이지를 새로고침 후 다시 시도해 주세요.');
  } else if (res.status === 500) {
    throw new Error('서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
  }
  throw new Error('서버 응답 오류가 발생했습니다.');
}
const data = await res.json();
setRows(data.rows || []);
// ...
} catch (err: any) {
  console.warn("Failed to fetch dashboard rows:", err);
  setToast({ message: err.message || "대시보드 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.", type: "error" });
}
```

---

## `main.py` 변경 (2곳)

**① `_supabase_retry` 헬퍼 추가 (enforce_user_fifo_limit 바로 위)**
```python
import time

def _supabase_retry(operation, max_retries: int = 2, delay: float = 0.5):
    """Retry a Supabase call on transient network/API failure."""
    last_exc: Exception = None
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"[Supabase Retry] Attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
    raise last_exc
```

**② `enforce_user_fifo_limit` — try-except 래핑 + 삭제 호출에 `_supabase_retry` 적용**
```python
async def enforce_user_fifo_limit(user_id: str, limit: int):
    try:
        # ... (기존 로직 그대로 유지)
        _supabase_retry(lambda: supabase.table("projects").delete().in_("project_id", to_delete_ids).execute())
        print(f"[CASCADE FIFO] Cleaned up oldest projects: {to_delete_ids} to enforce limit {limit}")
    except Exception as e:
        print(f"[CASCADE FIFO] Warning: FIFO enforcement failed (non-critical, skipped): {str(e)}")
```
