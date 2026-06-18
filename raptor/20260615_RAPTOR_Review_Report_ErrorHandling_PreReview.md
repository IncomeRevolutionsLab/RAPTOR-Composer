# Claude Code 리뷰 레포트: 교차 환경 에러 분석 및 처리 방안 (401, 403, 500)

## 변경 계획 (2개 파일)

### 1. `AuthDashboard.tsx`

**① State 추가** (line 202 근처):
```typescript
const [dashboardError, setDashboardError] = useState<{ status: number; message: string } | null>(null);
```

**② fetchDashboardData 에러 처리 개선** (lines 248-258):

현재:
```typescript
if (res.ok) {
  const data = await res.json();
  setRows(data.rows || []);
} else {
  throw new Error('서버 응답 오류');
}
```
catch에서 단순 toast만 표시.

변경 후: `res.status` 기준으로 분기
- `401` → "세션 만료, 다시 로그인" + 재로그인 버튼
- `403` → "CSRF/쿠키 만료" + 현재 운영 현황 보기 링크  
- `500+` → "서버 오류" + 현재 운영 현황 보기 링크
- 네트워크 오류 → 연결 실패 메시지
- 에러 상세(status code, 백엔드 detail)는 `console.warn`에만 기록, 사용자에겐 노출 안 함

**③ 프로젝트 탭 UI 추가** (line 1085 근처, rowsLoading 조건부 렌더링):

`dashboardError` 시 인라인 배너 표시 (`rows.length === 0` 빈 상태 대신):
```tsx
{dashboardError && (
  <div className="...red error banner...">
    <AlertCircle /> {dashboardError.message}
    {/* 403/500 전용 */}
    <a href={process.env.NEXT_PUBLIC_STATUS_PAGE_URL || '#'} target="_blank">
      현재 운영 현황 보기 →
    </a>
    {/* 401 전용 */}
    <button onClick={handleLogout}>다시 로그인 →</button>
  </div>
)}
```

---

### 2. `main.py` - `enforce_user_fifo_limit` (lines 432-462)

재시작 후 Supabase HTTP 연결 풀 초기화 시 1회 재시도 추가:

```python
async def enforce_user_fifo_limit(user_id: str, limit: int):
    sanitized_user = sanitize_uuid(user_id)
    
    # 재시작 직후 연결 실패 시 1회 재시도
    for attempt in range(2):
        try:
            res_projects = supabase.table("projects")...execute()
            break
        except Exception as e:
            if attempt == 0:
                print(f"[FIFO] DB 조회 실패 (재시도 중): {e}")
                await asyncio.sleep(1.0)
            else:
                print(f"[FIFO] DB 재시도 실패 — 정리 건너뜀: {e}")
                return
    
    # ... 기존 삭제 로직 (delete도 동일하게 try-except 추가)
```
