# Claude Code Raw Output — Pre-Review (DB Schema)
> **저장 일시**: 2026-06-11T20:28:37Z
> **리뷰 실행 명령**: `echo "[SQL 전문]" | claude -p --output-format text`
> **원칙**: 제7원칙에 따라 단 한 글자도 편집하지 않은 Raw Output 원문
> **Task ID**: `c65b8cac-461a-4f35-8ece-ea43ea293d87/task-460`
> **리뷰 단계**: Step 2 Pre-Review — v2.16.2 DB Schema 초기화

---

## ⚠️ 원문 무결성 고지

이 파일은 `claude -p` 터미널 실행 결과의 **무편집 원문**입니다.

---

## Raw Output (원문)

```
`main.py` 코드를 전부 확인했습니다. 이제 7개 항목별로 심층 리뷰를 작성합니다.

---

# RAPTOR v2 Supabase Schema DBA 리뷰 보고서
**리뷰어:** Claude (DBA 역할) | **날짜:** 2026-06-12

---

## 1. `project_id` 타입 일관성 — `CONDITIONAL_PASS`

**발견된 문제:** `project_id`를 생성하는 경로가 두 곳이며 형식이 다름.

| 코드 경로 | 생성 형식 | 예시 |
|---|---|---|
| `create_project_in_db()` (L386) | `str(uuid.uuid4())` | `"550e8400-e29b-41d4-a716-446655440000"` |
| `record_user_asset()` (L478) | `f"proj_{task_id}"` | `"proj_abc123"` |

**SQL 스키마 평가:**
- `TEXT PRIMARY KEY` 선택은 **정확함** — UUID가 아닌 접두사 형식(`proj_*`)도 저장 가능
- 하지만 스키마 주석에 `"uuid4 생성"`이라고만 적혀있어 실제와 불일치

**위험:** `record_user_asset`에서 `proj_{task_id}` 형식으로 삽입된 row는 `sanitize_uuid()` 검증을 통과하지 못함. 다행히 해당 함수는 `user_id`만 sanitize하고 `project_id`는 그대로 사용.

**권고:**
```sql
-- 주석 수정
project_id  TEXT  PRIMARY KEY,  -- uuid4() OR 'proj_{task_id}' 두 형식 혼재 (record_user_asset 경로)
```
```python
# main.py record_user_asset 상단에 명시적 문서화 필요
# project_id format: 'proj_{task_id}' (non-UUID intentional for legacy asset records)
```

---

## 2. RLS 정책 — `CONDITIONAL_PASS`

### 2-1. `projects` RLS — PASS
4개 정책(SELECT/INSERT/UPDATE/DELETE) 모두 `auth.uid() = user_id` 패턴 — 간결하고 정확.

### 2-2. `tasks` RLS — CONDITIONAL_PASS

**논리적 정확성:** EXISTS 서브쿼리로 프로젝트 소유권 확인 — 올바름.

**그러나 INSERT 정책에 잠재적 경쟁 조건 존재:**
```sql
-- 현재 정책
CREATE POLICY "tasks_insert_own" ON tasks
    FOR INSERT
    WITH CHECK (
        EXISTS (SELECT 1 FROM projects WHERE ...)
    );
```
백엔드 코드(`create_task_in_db`)는 **서비스 롤 키로 RLS를 우회**하므로 실제로 이 정책은 작동하지 않음. 하지만 미래에 클라이언트 직접 접근이 생길 경우를 위해 정책은 유지 권장.

**성능 고려:** tasks 테이블의 RLS 정책은 모든 행 접근 시 `projects` 테이블 조인이 발생. `idx_projects_user_id` 인덱스가 이를 커버하므로 수용 가능하나, tasks 행이 수만 건 이상 될 경우 모니터링 필요.

### 2-3. 핵심 지적: 백엔드는 RLS를 완전히 우회함

```python
# main.py L192
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
```
이 클라이언트는 모든 RLS 정책을 우회. 따라서 **데이터 격리는 전적으로 애플리케이션 레이어(`.eq("user_id", sanitized_user)`)에 의존**함. RLS는 외부 직접 접근 차단용 방어선으로만 기능.

---

## 3. `SUPABASE_SERVICE_ROLE_KEY` RLS 우회 — `CONDITIONAL_PASS`

**현재 구조 평가:**

| 위협 | 완화 수단 | 평가 |
|---|---|---|
| user_id 위조 | `sanitize_uuid()` UUID 검증 | 부분적 — UUID 형식 검증만, 존재 여부 미검증 |
| JWT 없이 API 직접 호출 | `get_jwt_user_id` Depends | 올바름 |
| 타인 데이터 조회 | `if user_id != jwt_user_id: raise 403` | 올바름 |

**위험 시나리오:**
```python
# get_user_videos, get_dashboard_projects는 user_id 일치 검증 있음 ✓
# 하지만 update_task_in_db(task_id, status)는 task_id 소유권 검증 없음 ⚠
async def update_task_in_db(task_id: str, status: str, ...):
    res = supabase.table("tasks").update(...).eq("task_id", task_id).execute()
    # task_id가 어느 user의 것인지 검증 없음!
```

**권고:**
```python
async def update_task_in_db(task_id: str, status: str, owner_user_id: str = None, ...):
    query = supabase.table("tasks").update(update_data).eq("task_id", task_id)
    if owner_user_id:
        # tasks → projects join으로 소유권 검증
        query = query.eq("project_id", 
            supabase.table("projects").select("project_id").eq("user_id", owner_user_id)
        )
```

---

## 4. Storage Bucket RLS — `FAIL`

**이것이 가장 심각한 문제입니다.**

스키마 RLS 정책:
```sql
CREATE POLICY "assets_select_own" ON storage.objects
    FOR SELECT
    USING (
        bucket_id = 'assets'
        AND auth.uid()::text = (storage.foldername(name))[1]  -- 첫 번째 폴더 = user_id 기대
    );
```

실제 업로드 경로 (`main.py`):
```python
# upload_image_to_supabase (L220-228)
file_name = f"raptor_{int(time.time())}_{scene_id}.png"  # ← 플랫 경로, user_id 없음

# upload_user_video (L1774)
path=f"{video_id}.mp4"  # ← 플랫 경로, user_id 없음
```

**실제 경로:** `raptor_1718000000_1.png`
**RLS가 기대하는 경로:** `{user_uuid}/raptor_1718000000_1.png`

`(storage.foldername("raptor_123.png"))[1]` → `NULL`

따라서 `auth.uid()::text = NULL` → 항상 `FALSE` → **인증된 클라이언트의 직접 스토리지 접근은 전부 차단**.

**현재 동작이 깨지지 않는 이유:**
1. 업로드: 서비스 롤 키 → RLS 우회 → 성공
2. Signed URL: 서비스 롤 키로 발급된 URL은 RLS 우회 → 접근 성공
3. 따라서 현재 아키텍처에서 Storage RLS는 **사실상 Dead Code**

**권고 (두 가지 옵션 중 선택):**

**옵션 A** — 경로에 user_id 폴더 추가 (권장, 진정한 Defence-in-Depth):
```python
# upload_image_to_supabase 수정
file_name = f"{user_id}/raptor_{int(time.time())}_{scene_id}.png"
# upload_user_video 수정
path=f"{sanitized_user}/{video_id}.mp4"
```

**옵션 B** — Storage RLS 정책을 현재 아키텍처에 맞게 수정:
```sql
-- 서비스 롤 전용 아키텍처 명시, Signed URL 접근만 허용
DROP POLICY IF EXISTS "assets_select_own" ON storage.objects;
DROP POLICY IF EXISTS "assets_insert_own" ON storage.objects;
DROP POLICY IF EXISTS "assets_delete_own" ON storage.objects;
-- 서비스 롤 키 + Signed URL 아키텍처에서는 Storage RLS가 불필요
```

---

## 5. ENUM `'completed'` 불일치 — `CONDITIONAL_PASS` (주의 요망)

**상태값 매핑 현황:**

| 위치 | 정의된 상태값 |
|---|---|
| `task_status_enum` (DB) | `'pending', 'processing', 'success', 'failed', 'completed'` |
| `TaskModel` (Pydantic) | `'pending', 'processing', 'success', 'failed'` ← **`completed` 없음!** |
| `KieWebhookPayload` | `'completed', 'failed'` |
| `get_user_videos` 쿼리 | `.eq("status", "success")` ← **`completed` 조회 안 함!** |

**두 경로가 실제로 사용되는지에 따라 심각도 결정:**
- KIE 웹훅 경로가 실제로 사용된다면 → 완료된 KIE 작업이 사용자 비디오 목록에 누락 → **P2 버그**
- `record_user_asset`만 실제로 사용된다면 → 현재는 무해

**권고:**
```python
# 옵션 1: get_user_videos 쿼리 수정
.in_("status", ["success", "completed"])

# 옵션 2: KIE 웹훅 핸들러에서 status 매핑
status_map = {"completed": "success", "failed": "failed"}
```

---

## 6. 인덱스 적절성 — `CONDITIONAL_PASS`

### 누락된 인덱스

```sql
-- 누락 1: project_id + task_type + status 복합
CREATE INDEX IF NOT EXISTS idx_tasks_project_type_status 
    ON tasks(project_id, task_type, status);

-- 누락 2: user_video_assets 복합
CREATE INDEX IF NOT EXISTS idx_user_video_assets_user_uploaded 
    ON user_video_assets(user_id, uploaded_at DESC);

-- 누락 3: tasks created_at 정렬
CREATE INDEX IF NOT EXISTS idx_tasks_project_created 
    ON tasks(project_id, created_at DESC);
```

---

## 7. 종합 판정

| # | 항목 | 판정 | 심각도 |
|---|---|---|---|
| 1 | `project_id` 타입 | **CONDITIONAL_PASS** | Low |
| 2 | RLS 정책 논리 | **CONDITIONAL_PASS** | Low |
| 3 | SERVICE_ROLE_KEY 보안 | **CONDITIONAL_PASS** | Medium |
| 4 | Storage Bucket RLS | **FAIL** | Medium — 경로 불일치로 Dead Code |
| 5 | ENUM `completed` 불일치 | **CONDITIONAL_PASS** | Medium |
| 6 | 인덱스 | **CONDITIONAL_PASS** | Low |
| **전체** | | **CONDITIONAL_PASS** | Storage RLS + status 불일치 해결 후 PASS |

**P1 (즉시 수정):** Storage RLS 정책 제거(옵션 B) 또는 경로에 user_id 폴더 추가(옵션 A)
**P2 (다음 릴리즈):** `get_user_videos`에 `completed` 상태 추가, `update_task_in_db` 소유권 검증
**P3 (최적화):** 누락 복합 인덱스 3개 추가
```

---

## 실행 컨텍스트

| 항목 | 내용 |
|------|------|
| 실행 시각 | 2026-06-11T20:24:11Z |
| 명령 | `echo "[SQL 전문]" \| claude -p --output-format text` |
| 리뷰 단계 | Step 2 Pre-Review — DB Schema |
| Task ID | `c65b8cac-461a-4f35-8ece-ea43ea293d87/task-460` |
