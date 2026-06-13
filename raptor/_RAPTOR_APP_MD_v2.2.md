# 📐 RAPTOR 앱 설계서 v2.2 (Project-Task 매핑 아키텍처)
**[대시보드 대통합 및 1:N Project-Task 매핑 기반 데이터 설계]**

---

## 📜 Changelog
- **v1.0 - v2.1:** Grok/OpenAI 파이프라인 정비, TypeScript 및 Pydantic 데이터 구조 정의, 에러 UI 노출 강화 및 `Film` import 핫픽스 적용.
- **v2.2 (Current):**
  - **긴급 조치:** 새로고침 시 과금 누수를 유발하는 `BYOKSettingsForm.tsx` 마운트 시의 `/auth/post-review` 자동 트리거 완전 삭제 (`NEW-A` 차단)
  - **대통합:** 메인 UI 하단 요소(beta_tester 메일 주소, 내 보관함, 로그아웃, Global Settings)를 철거하고, 우측 상단 사용자 프로필 버튼을 통한 전면 모달 형태의 **[통합 대시보드]** 신설
  - **통합 대시보드 탭 구성:** [설정] (KIE API Key), [프로젝트 관리] (프로젝트-태스크 매핑 게시판), [계정] (로그아웃)
  - **과금 철거:** 크레딧 계산 로직 및 `kie_pricing.json` 의존성 완전 삭제 (KIE 플랫폼에서 직접 확인하도록 위임)
  - **아키텍처 대수술:** 기존 1차원 보관함 구조를 1:N 구조의 **Project-Task 매핑** 데이터베이스 스키마로 개편하여 재시도(Resume/Retry) 히스토리 완전 보존 보장

---

## 1. 데이터베이스 스키마 설계 (Data Schemas)

### 1.1 Project (프로젝트) 스키마
프로젝트는 사용자가 Step 1에서 클로드를 통한 상품 분석을 시작할 때 최초로 생성되는 단위입니다.

*   `project_id`: String (UUID, 고유 키)
*   `product_name`: String (상품명)
*   `created_at`: String (ISO 8601 생성 일시)
*   `user_id`: String (사용자 고유 ID)
*   `plan_snapshot`: Object (Claude가 분석하여 도출한 `PlanOutput` 최초 JSON 구조 보존, 선택 사항)

### 1.2 Task (태스크) 스키마
프로젝트 하위에 귀속되는 개별 작업의 로그입니다. 텍스트 분석, 개별 씬 이미지/비디오 생성, 최종 FFmpeg 렌더링 시도마다 독립적으로 기록됩니다. 재시도 시 기존 레코드를 덮어쓰지 않고 신규 태스크 레코드를 추가합니다.

*   `task_id`: String (UUID, KIE Task ID 혹은 로컬 ID, 고유 키)
*   `project_id`: String (소속 프로젝트 ID - `Project.project_id` 외래키 참조)
*   `task_type`: String (`'text_generation' | 'image_generation' | 'video_generation' | 'final_render'`)
*   `description`: String (작업 설명 예: "씬 1 비디오 생성", "최종 MP4 렌더링")
*   `status`: String (`'pending' | 'processing' | 'success' | 'failed'`)
*   `result_url`: String (결과물 다운로드/재생 링크 - 비디오 또는 이미지 URL, 선택 사항)
*   `error`: String (실패 시 에러 세부 메시지, 선택 사항)
*   `created_at`: String (ISO 8601 생성 일시)

---

## 2. TypeScript 인터페이스 (Frontend)

```typescript
export interface Project {
  project_id: string;
  product_name: string;
  created_at: string;
  user_id: string;
  plan_snapshot?: any;
}

export interface Task {
  task_id: string;
  project_id: string;
  task_type: 'text_generation' | 'image_generation' | 'video_generation' | 'final_render';
  description: string;
  status: 'pending' | 'processing' | 'success' | 'failed';
  result_url?: string;
  error?: string;
  created_at: string;
}

// 통합 대시보드 게시판 출력용 병합 인터페이스
export interface DashboardProjectRow {
  product_name: string;
  project_id: string;
  task_id: string;
  description: string;
  status: 'pending' | 'processing' | 'success' | 'failed';
  result_url?: string;
  created_at: string;
}
```

---

## 3. Pydantic 스키마 (Backend)

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class ProjectModel(BaseModel):
    project_id: str
    product_name: str
    created_at: datetime
    user_id: str
    plan_snapshot: Optional[dict] = None

class TaskModel(BaseModel):
    task_id: str
    project_id: str
    task_type: Literal['text_generation', 'image_generation', 'video_generation', 'final_render']
    description: str
    status: Literal['pending', 'processing', 'success', 'failed']
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
```

---

## 4. API 계약 (I/O Contract)

### `POST /api/projects`
Step 1 상품 분석 시작 순간 호출되어 새로운 프로젝트를 생성합니다.
*   **Input:**
    ```json
    {
      "product_name": "str",
      "user_id": "str"
    }
    ```
*   **Output (201):** `ProjectModel`

### `POST /api/projects/{project_id}/tasks`
개별 작업 시작 시 태스크 레코드를 추가합니다.
*   **Input:**
    ```json
    {
      "task_id": "str",
      "task_type": "str",
      "description": "str"
    }
    ```
*   **Output (201):** `TaskModel`

### `PATCH /api/tasks/{task_id}`
작업 완료 또는 실패 시 태스크의 상태를 업데이트합니다.
*   **Input:**
    ```json
    {
      "status": "success | failed",
      "result_url": "str (optional)",
      "error": "str (optional)"
    }
    ```
*   **Output (200):** `TaskModel`

### `GET /api/dashboard/projects`
통합 대시보드 프로젝트 관리 탭에 출력할 게시판 형태의 병합 목록을 조회합니다.
*   **Output (200):**
    ```json
    {
      "rows": [
        {
          "product_name": "str",
          "project_id": "str",
          "task_id": "str",
          "description": "str",
          "status": "success | failed | pending | processing",
          "result_url": "str (optional)",
          "created_at": "str"
        }
      ]
    }
    ```

---

## 5. TDD 테스트 명세 (Test Specifications)

```python
# tests/test_project_task_mapping.py
import pytest
from pydantic import ValidationError
from datetime import datetime
from main import ProjectModel, TaskModel

def test_project_requires_id_and_product_name():
    with pytest.raises(ValidationError):
        ProjectModel(project_id="", product_name="", created_at=datetime.now(), user_id="test")

def test_task_type_constraints():
    with pytest.raises(ValidationError):
        TaskModel(
            task_id="t1",
            project_id="p1",
            task_type="invalid_type",  # 제한조건 위반
            description="test desc",
            status="pending",
            created_at=datetime.now()
        )

def test_task_status_constraints():
    for valid_status in ['pending', 'processing', 'success', 'failed']:
        task = TaskModel(
            task_id="t1",
            project_id="p1",
            task_type="final_render",
            description="test desc",
            status=valid_status,
            created_at=datetime.now()
        )
        assert task.status == valid_status
```
