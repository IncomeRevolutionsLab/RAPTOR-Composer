# 📐 RAPTOR 앱 설계서 v2.1 (TDD 기반 재설계)
**[데이터 구조 우선 정의 & 테스트 주도 개발 기반 리팩터링]**

---

## 📜 Changelog
- **v1.3 → v2.1:**
  - **제거:** FFmpeg 런타임 자동 감지 및 3-포맷(MP4·WebM·MOV) 분기 → 단일 MP4/H264 파이프라인
  - **제거:** 영상 길이 자동 속도 조절(Speed Adjustment) → `duration_seconds` 고정값(`3|5|7`)으로 대체
  - **제거:** ngrok 실패 시 동기 fallback 렌더링 → 단순 500 에러 반환
  - **추가:** TypeScript 인터페이스 및 Pydantic 스키마 선행 정의 (Data-First)
  - **추가:** 계층별 TDD 테스트 명세 (Red → Green 기준)

---

## 1. 핵심 데이터 타입 정의 (Data Types First)

> **설계 원칙:** 구현 전에 인터페이스 계약을 먼저 확정한다. 모든 API와 컴포넌트는 이 타입을 기준으로 동작을 검증받는다.

### 1.1 TypeScript 인터페이스 (Frontend)

```typescript
// 씬 단위 – duration은 3가지 고정값만 허용
interface Scene {
  scene_index: number;           // 0-based
  duration_seconds: 3 | 5 | 7;  // 고정값, 자동 속도 조절 없음
  prompt: string;
  subtitle: string;              // 최대 200자
  user_video_id?: string;        // '내 비디오 사용' 연동 시만 존재
}

// 기획 엔진 출력 결과 (Claude → Frontend)
interface PlanOutput {
  product_name: string;
  selected_pattern: string;
  scenes: Scene[];               // 최소 3개, 최대 8개
  title: string;                 // 최대 100자
  hashtags: string[];            // 최대 10개
  total_duration: number;        // 각 씬 duration_seconds 합산
}

// 렌더 태스크 요청
interface RenderTaskRequest {
  plan: PlanOutput;
  voice_type: 'male' | 'female' | 'none';
  aspect_ratio: '9:16' | '16:9';
  callback_url: string;
}

// 렌더 태스크 상태 (DB 레코드 기준)
interface RenderTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result_url?: string;
  error?: string;
  created_at: string;            // ISO 8601
  expires_at?: string;           // created_at + 14일
}

// 보관함 목록 아이템
interface ArchiveItem extends RenderTaskStatus {
  product_name: string;
  thumbnail_url?: string;
  plan_snapshot: PlanOutput;
}

// 사용자 업로드 비디오 에셋
interface UserVideoAsset {
  id: string;
  filename: string;
  duration_seconds: number;
  uploaded_at: string;
}
```

### 1.2 Pydantic 스키마 (Backend)

```python
from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional
from datetime import datetime, timedelta

class Scene(BaseModel):
    scene_index: int
    duration_seconds: Literal[3, 5, 7]
    prompt: str = Field(min_length=10)
    subtitle: str = Field(max_length=200)
    user_video_id: Optional[str] = None

class PlanOutput(BaseModel):
    product_name: str
    selected_pattern: str
    scenes: list[Scene] = Field(min_length=3, max_length=8)
    title: str = Field(max_length=100)
    hashtags: list[str] = Field(max_length=10)
    total_duration: int

    @model_validator(mode="after")
    def validate_total_duration(self) -> "PlanOutput":
        expected = sum(s.duration_seconds for s in self.scenes)
        if self.total_duration != expected:
            raise ValueError(f"total_duration {self.total_duration} != {expected}")
        return self

class RenderTaskRequest(BaseModel):
    plan: PlanOutput
    voice_type: Literal["male", "female", "none"]
    aspect_ratio: Literal["9:16", "16:9"]
    callback_url: str

class RenderTaskStatus(BaseModel):
    task_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

class KieWebhookPayload(BaseModel):
    task_id: str
    status: Literal["completed", "failed"]
    result_url: Optional[str] = None
    error: Optional[str] = None

class UserVideoAsset(BaseModel):
    id: str
    filename: str
    duration_seconds: float
    uploaded_at: datetime
```

---

## 2. API 계약 (I/O Contract)

### `POST /api/generate-plan`
- **Headers:** `{ "X-BYOK-Claude": "sk-ant-..." }`
- **Input:**
  ```json
  {
    "product_name": "str",
    "image_url": "str",
    "video_length": 15,
    "quality": "standard | premium",
    "selected_pattern": "str (optional)",
    "manual_additions": { "pain_points": ["str"], "strengths": ["str"] }
  }
  ```
- **Output (200):** `PlanOutput` (Pydantic 검증 통과)
- **Error (401):** API 키 없음 / 유효하지 않음
- **Error (422):** 출력 스키마 검증 실패 → 재시도 1회 후 반환

### `POST /api/render-task`
- **Input:** `RenderTaskRequest`
- **Output (202, 즉시):** `{ "task_id": "str", "status": "pending" }`

### `POST /api/webhook/kie`
- **Input:** `KieWebhookPayload`
- **Output (200):** `{ "received": true }`
- **Error (404):** 알 수 없는 `task_id`

### `GET /api/archive`
- **Output:** `{ "items": ArchiveItem[], "total": int }`
- 만료된 항목 자동 필터링, 최대 50건

### `POST /api/user-videos`
- **Input:** `multipart/form-data` (MP4 파일만 허용)
- **Output:** `UserVideoAsset`

---

## 3. TDD 테스트 명세 (Test Specifications)

> **Red-Green 순서:** 아래 테스트가 먼저 작성된 후 구현이 이를 통과시킨다.

### 3.1 스키마 유효성 검증 (Unit)

```python
# tests/test_schemas.py

def test_scene_duration_must_be_3_5_or_7():
    with pytest.raises(ValidationError):
        Scene(scene_index=0, duration_seconds=4, prompt="유효한프롬프트", subtitle="자막")

def test_scene_duration_accepts_valid_values():
    for d in [3, 5, 7]:
        scene = Scene(scene_index=0, duration_seconds=d, prompt="유효한프롬프트", subtitle="자막")
        assert scene.duration_seconds == d

def test_plan_requires_minimum_3_scenes():
    with pytest.raises(ValidationError):
        PlanOutput(product_name="X", selected_pattern="A", scenes=[],
                   title="T", hashtags=[], total_duration=0)

def test_plan_total_duration_must_match_scene_sum():
    scenes = [Scene(scene_index=i, duration_seconds=5, prompt="p"*10, subtitle="s")
              for i in range(3)]
    with pytest.raises(ValidationError):
        PlanOutput(product_name="X", selected_pattern="A", scenes=scenes,
                   title="T", hashtags=[], total_duration=99)  # 실제 합계: 15

def test_subtitle_max_200_chars():
    with pytest.raises(ValidationError):
        Scene(scene_index=0, duration_seconds=5, prompt="p"*10, subtitle="x" * 201)

def test_plan_max_8_scenes():
    scenes = [Scene(scene_index=i, duration_seconds=5, prompt="p"*10, subtitle="s")
              for i in range(9)]
    with pytest.raises(ValidationError):
        PlanOutput(product_name="X", selected_pattern="A", scenes=scenes,
                   title="T", hashtags=[], total_duration=45)
```

### 3.2 기획 엔진 (Unit)

```python
# tests/test_plan_engine.py

def test_generate_plan_returns_valid_plan_output(mock_claude_response):
    result = generate_plan(product_name="샴푸", image_url="https://img.test/1.jpg",
                           video_length=30, api_key="sk-ant-test")
    assert isinstance(result, PlanOutput)
    assert len(result.scenes) >= 3
    assert result.total_duration == sum(s.duration_seconds for s in result.scenes)

def test_selected_pattern_is_respected(mock_claude_response):
    result = generate_plan(..., selected_pattern="Problem-Solution")
    assert result.selected_pattern == "Problem-Solution"

def test_generate_plan_raises_auth_error_without_key():
    with pytest.raises(AuthError):
        generate_plan(product_name="X", image_url="https://...",
                      video_length=15, api_key=None)

def test_generate_plan_retries_once_on_schema_validation_failure(mock_claude_bad_then_good):
    # 첫 번째 응답은 스키마 위반, 두 번째 응답은 유효
    result = generate_plan(...)
    assert mock_claude_bad_then_good.call_count == 2
    assert isinstance(result, PlanOutput)
```

### 3.3 웹훅 파이프라인 (Integration)

```python
# tests/test_webhook.py

async def test_webhook_completed_updates_task_and_sets_expiry(db, client):
    task = await create_pending_task(db)
    payload = {"task_id": task.task_id, "status": "completed",
               "result_url": "https://kie.test/video.mp4"}
    resp = await client.post("/api/webhook/kie", json=payload)
    assert resp.status_code == 200
    updated = await db.get_task(task.task_id)
    assert updated.status == "completed"
    assert updated.result_url == "https://kie.test/video.mp4"
    assert (updated.expires_at - updated.created_at).days == 14

async def test_webhook_failed_status_stores_error(db, client):
    task = await create_pending_task(db)
    resp = await client.post("/api/webhook/kie",
                             json={"task_id": task.task_id, "status": "failed",
                                   "error": "GPU out of memory"})
    updated = await db.get_task(task.task_id)
    assert updated.status == "failed"
    assert updated.error == "GPU out of memory"

async def test_webhook_returns_404_for_unknown_task_id(client):
    resp = await client.post("/api/webhook/kie",
                             json={"task_id": "NONEXISTENT", "status": "completed",
                                   "result_url": "https://..."})
    assert resp.status_code == 404
```

### 3.4 보관함 보존 정책 (Unit + Integration)

```python
# tests/test_retention.py

def test_expires_at_set_to_14_days_after_created_at():
    created = datetime.utcnow()
    task = build_completed_task(created_at=created, result_url="https://...")
    assert task.expires_at == created + timedelta(days=14)

def test_expired_tasks_excluded_from_archive_listing(db):
    create_task(db, expires_at=datetime.utcnow() - timedelta(days=1))
    items = get_archive_items(db)
    assert len(items) == 0

async def test_archive_enforces_50_item_fifo_limit(db, client):
    for i in range(51):
        await create_completed_task(db, product_name=f"상품 {i}")
    resp = await client.get("/api/archive")
    assert resp.json()["total"] == 50
    names = [item["product_name"] for item in resp.json()["items"]]
    assert "상품 0" not in names   # 가장 오래된 항목 제거됨
    assert "상품 50" in names
```

### 3.5 '내 비디오 사용' 에셋 바인딩 (Integration)

```python
# tests/test_user_video.py

async def test_upload_accepts_mp4_only(client, tmp_mp4_file):
    resp = await client.post("/api/user-videos",
                             files={"file": ("clip.mp4", tmp_mp4_file, "video/mp4")})
    assert resp.status_code == 200

async def test_upload_rejects_non_mp4(client, tmp_mov_file):
    resp = await client.post("/api/user-videos",
                             files={"file": ("clip.mov", tmp_mov_file, "video/quicktime")})
    assert resp.status_code == 422

async def test_scene_rejects_user_video_shorter_than_duration(db):
    asset = await upload_user_video(db, filename="short.mp4", duration_seconds=2)
    with pytest.raises(AssetDurationError):
        await resolve_scene_asset(db,
            Scene(scene_index=0, duration_seconds=5, prompt="p"*10,
                  subtitle="s", user_video_id=asset.id))
```

---

## 4. 단순화된 비디오 파이프라인

### v1.3 대비 변경 항목

| 항목 | v1.3 동작 | v2.1 동작 |
|------|-----------|-----------|
| FFmpeg 탐지 | 런타임 바이너리 자동 탐지, 실패 시 fallback | FFmpeg 설치 전제, 미설치 시 500 반환 |
| 영상 포맷 | MP4·WebM·MOV 3종 자동 변환 | MP4/H264 단일 포맷 (변환 없음) |
| duration 처리 | 씬 시간 부족 시 속도 자동 조절 | 고정값(`3\|5\|7s`), 짧은 클립은 에러 반환 |
| 오버런 처리 | 자동 트림 | `-t` 플래그로 앞 N초만 사용 |
| ngrok 실패 | 동기 fallback 렌더링 | `500 Internal Server Error` 반환 |

### FFmpeg 명령 패턴 (단순화)

```bash
# 사용자 비디오 트림 (앞 N초)
ffmpeg -i input.mp4 -t {duration_seconds} -c:v copy -c:a copy trimmed.mp4

# TTS + 배경음 믹싱
ffmpeg -i tts.mp3 -i bg.mp3 -filter_complex "amix=inputs=2:duration=first" mixed.mp3

# 최종 씬 합성 (영상 + 오디오)
ffmpeg -i trimmed.mp4 -i mixed.mp3 -c:v copy -c:a aac -shortest scene_final.mp4
```

---

## 5. 비용 방어 정책 (Costless Retrieval)

- KIE `resultUrl`만 DB 저장 (파일 다운로드·복제 없음).
- 만료: `created_at + timedelta(days=14)` (`@model_validator`로 스키마 레벨 강제).
- 최대 보관: 50건, 초과 시 `created_at` 오름차순 FIFO 삭제.

---

## 6. 보안

- **BYOK:** `X-BYOK-Claude` 헤더 전달, 백엔드 미저장.
- **Webhook 인증:** `task_id` DB 조회 후 처리, 미존재 시 404.
- **파일 업로드:** MIME 타입 `video/mp4` + 확장자 `.mp4` 이중 검증.
