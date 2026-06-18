## Post-Review: 에러 핸들링 세분화 (401/403/500 + FIFO 재시도)

### 종합 판정: **PASS with Gaps**

핵심 변경 3건은 모두 올바르게 구현됨. 단, 실제 운영에서 문제가 될 수 있는 **P2 이슈 2건** 발견.

---

### `api-client.ts` — ✅ 완전 통과 (계획 초과)

| 항목 | 판정 |
|------|------|
| `ApiError` 클래스 (line 6–11) | ✅ |
| 401/403/500 메시지 분기 (line 100–108) | ✅ |
| `throw new ApiError(...)` (line 109) | ✅ |
| AbortError·네트워크 오류 처리 (line 113–121) | ✅ 미계획 추가 개선 |

이상 없음.

---

### `AuthDashboard.tsx` — ⚠️ 메시지 의미 오류 1건

구현 자체는 VIBE 플랜 기준 완료. 단:

```typescript
// line 251 — 현재 (문제):
throw new Error('API 키가 누락되었거나 만료되었습니다. 우측 상단에 API 키를 다시 입력해 주세요.');

// /api/dashboard/projects는 KIE Key가 아닌 Supabase JWT로 인증함.
// 401 = JWT 세션 만료 → 사용자를 API 키 설정으로 잘못 유도.
// 권고:
throw new Error('세션이 만료되었습니다. 다시 로그인해 주세요.');
```

인라인 에러 배너(`dashboardError` state, Plan 1)는 VIBE가 toast 방식으로 유지 — 허용 가능한 범위 축소.

---

### `main.py` — ⚠️ 초기 DB 조회 2곳 미보호

`_supabase_retry`가 **삭제**에만 적용됨. **초기 조회 2곳은 여전히 무방비.**

```python
# line 450 — try-except 없음, retry 없음
res_projects = supabase.table("projects").select(...).execute()

# line 460 — 동일 문제
res_tasks = supabase.table("tasks").select("task_id")...execute()
```

Koyeb 재시작 직후 이 쿼리가 실패하면 예외가 `check_and_enforce_user_limits`로 전파 → 프로젝트 생성 자체 실패 가능. 함수 전체를 outer `try-except`로 감싸거나, 두 조회에도 `_supabase_retry` 적용 필요.

---

### 수정 우선순위

| 우선순위 | 파일 | 수정 규모 |
|----------|------|-----------|
| P2 | `AuthDashboard.tsx` line 251 | 1줄 |
| P2 | `main.py` `enforce_user_fifo_limit` | ~4줄 |
