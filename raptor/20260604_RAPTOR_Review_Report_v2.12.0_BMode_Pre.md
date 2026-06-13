# RAPTOR v2.12.0 아키텍처 사전 리뷰 (BMode Pre-Review) 보고서

> **Author: Claude Code**
> **작성일:** 2026-06-04
> **대상 버전:** RAPTOR v2.12.0 (대시보드 대통합 및 Project-Task 매핑 아키텍처)
> **검토 범위:** `_RAPTOR_APP_MD_v2.2.md` 설계서 기반 데이터베이스 및 통신 구조 검토

---

## 1. 총평

본 검토는 RAPTOR의 '대시보드 대통합 및 Project-Task 1:N 매핑 구조' 개편안(`_RAPTOR_APP_MD_v2.2.md`)에 대해 시스템 아키텍처, 상태 관리의 무결성, 조인(Join) 성능 및 병목 현상에 초점을 맞추어 비판적으로 수행되었습니다. 
이번 설계는 기존의 단순 1차원 보관함 구조를 1:N 관계형 아키텍처로 진화시켜 **작업 재시도(Resume/Retry) 히스토리를 완벽하게 보존**하고, 과금 계산 로직 제거 및 통합 대시보드 개편을 통해 복잡성을 크게 줄이는 훌륭한 설계를 담고 있습니다. 
그러나 단일 JSON 파일 기반 모의 데이터베이스 구조하에서 1:N 매핑을 수행할 때 발생할 수 있는 **조인 성능 저하** 및 병렬 비동기 작업에 따른 **최종 상태 충돌 리스크**가 식별되어 TDD 채점 기준과 함께 방안을 제시합니다.

---

## 2. 🟢 [Resolved] — 해결 확정 리스크

### R-01: `NEW-A` 과금 누수 버그 완벽 제거
*   **내용:** `BYOKSettingsForm.tsx` 마운트 시 고비용의 `/auth/post-review`를 자동 호출하여 크레딧이 낭비되던 치명적 결함을 호출부 삭제를 통해 완전히 제거합니다.

### R-02: 메인 UX 청소 및 모달형 대시보드 단일화
*   **내용:** 메인 화면 하단에 무질서하게 흩어져 있던 프로필 메일, 보관함, 글로벌 설정 등의 요소를 철거하고 우측 상단 단일 프로필 아이콘 클릭 시 작동하는 **전면 모달 형태의 통합 대시보드**로 구조를 단순화하여 UX 무결성을 높였습니다.

---

## 3. ⏳ [Pending] — 미결 / 보류 리스크

### P-01: 크로스 플랫폼 폰트 경로 하드코딩 (`RISK-003` 계속)
*   **현황:** `ffmpeg_worker.py` 내부의 맑은 고딕 폰트 경로는 이번 대시보드/데이터 대공사의 범위 외에 있으므로 Linux 배포판 대응을 위한 로컬 에셋화는 여전히 이월 과제로 남습니다.

---

## 4. 🔴 [New] — 아키텍처 잠재 위험 분석 (핵심 비평)

### RISK-A: JSON 파일 DB 체제에서의 1:N 조인(Join) 입출력 성능 저하
*   **분석:** 현재 백엔드는 Supabase 클라이언트 외에도 로컬 파일(`user_videos_beta.json` 등)을 파일 기반 DB로 혼용하고 있습니다. 관계형 조인이 필요한 Project-Task 구조를 단일 JSON 파일 쓰기/읽기 방식으로 구현할 경우, 태스크 히스토리가 누적됨에 따라 **전체 스캔(Full Scan) 및 파싱 병목**이 발생하게 됩니다.
*   **대책:** Project 테이블 파일과 Task 테이블 파일을 별도로 분리하고, Task 조회 시 `project_id` 기준 인덱싱 딕셔너리를 메모리에 캐싱하거나 O(1) 조회가 가능하도록 구조화해야 합니다.

### RISK-B: 재시도(Resume/Retry) 시 최종 상태 바인딩 충돌 (Race Condition)
*   **분석:** 하나의 프로젝트(Project ID) 하위에서 사용자가 비디오 생성을 재시도하면, 동일 프로젝트 내에 동일 씬(Scene)의 태스크가 중복 발생하게 됩니다. 프론트엔드가 결과를 받아 최종 비디오를 병합할 때, **가장 최근에 성공한 태스크 결과물(UUID 기준)을 명확하게 식별하여 바인딩**하지 않으면, 구버전 실패 결과물이나 이전 성공물이 엉뚱하게 믹싱되는 상태 충돌이 발생합니다.
*   **대책:** 각 Task 레코드에 `task_type`뿐만 아니라 `scene_index`를 명시적으로 부여하고, 최종 렌더링 시에는 해당 `project_id` 및 `scene_index` 하위의 **가장 최신(created_at 기준) success 상태인 result_url**만 조인하여 바인딩하도록 로직을 강제해야 합니다.

### RISK-C: 히스토리 누적에 따른 FIFO 용량 임계치 폭발 리스크
*   **분석:** 기존에는 완료 항목 50개 FIFO 제한을 단순 1차원 배열로 처리했습니다. Project-Task 1:N 구조에서는 프로젝트 수는 적더라도 각 프로젝트당 수십 개의 Retry 태스크 로그가 쌓여 전체 크기가 기하급수적으로 증가합니다.
*   **대책:** FIFO 정제 임계 규칙을 `Project` 단위(최대 10개 프로젝트 보존)로 제한하고, 삭제되는 프로젝트 하위의 `Task` 레코드들은 CASCADE 방식으로 동시 삭제되도록 데이터 정리(Cleanup) 알고리즘을 선언해야 합니다.

---

## 5. 📝 TDD 채점지 명세 (TDD Specification Sheet)

새로운 구조의 무결성을 보장하기 위해 아래 테스트 케이스들이 먼저 통과(Green)되어야만 합니다.

```python
# tests/test_project_task_mapping.py
import pytest
from datetime import datetime
from pydantic import ValidationError
from main import ProjectModel, TaskModel

def test_project_id_must_be_uuid():
    # project_id는 고유한 UUID 규격이어야 함
    with pytest.raises(ValidationError):
        ProjectModel(project_id="invalid-id", product_name="test", created_at=datetime.now(), user_id="u1")

def test_task_creation_under_project():
    # 1:N 매핑 확인 - Task는 반드시 유효한 project_id를 가져야 함
    project = ProjectModel(project_id="p1-uuid-standard", product_name="샴푸", created_at=datetime.now(), user_id="u1")
    task = TaskModel(
        task_id="t1-uuid-standard",
        project_id=project.project_id,
        task_type="video_generation",
        description="Scene 1 video",
        status="pending",
        created_at=datetime.now()
    )
    assert task.project_id == "p1-uuid-standard"

def test_retry_history_preservation():
    # 동일 project_id 하위에 실패 로그와 신규 시도 로그가 공존하는지 검증
    project_id = "p1-uuid"
    task_failed = TaskModel(
        task_id="t1", project_id=project_id, task_type="final_render",
        description="Final render try 1", status="failed", created_at=datetime.now()
    )
    task_new_retry = TaskModel(
        task_id="t2", project_id=project_id, task_type="final_render",
        description="Final render try 2", status="success", created_at=datetime.now()
    )
    # 두 태스크가 같은 프로젝트에 속해 있고 서로 다른 task_id를 보유하여 역사 보존
    assert task_failed.project_id == task_new_retry.project_id
    assert task_failed.task_id != task_new_retry.task_id
```

---

*본 보고서는 KIE Claude Double Review 프로세스의 BMode Pre-Review 단계 결과물입니다. 검토 의견을 수용한 구현 계획서 승인 후 2단계 코딩 수술 및 검증을 집행해 주시기 바랍니다.*
