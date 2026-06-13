import pytest
from datetime import datetime
from pydantic import ValidationError
import sys
import os

os.environ.setdefault("COOKIE_ENCRYPTION_KEY", "3u8V_z5Fp3Uo54b1f4g7Y3k5l1pD_s1t4a5g7r8a9v0=")

# Import from main.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import ProjectModel, TaskModel

def test_project_id_validation():
    # project_id는 고유한 문자열이어야 하며 빈 값이 아니어야 함
    with pytest.raises(ValidationError):
        ProjectModel(project_id="", product_name="test", created_at=datetime.now(), user_id="test")

def test_project_valid_creation():
    project = ProjectModel(
        project_id="proj-uuid-1234",
        product_name="좋은 샴푸",
        created_at=datetime.now(),
        user_id="beta_tester"
    )
    assert project.project_id == "proj-uuid-1234"
    assert project.product_name == "좋은 샴푸"

def test_task_type_validation():
    # task_type은 정의된 Literal 중 하나여야 함
    with pytest.raises(ValidationError):
        TaskModel(
            task_id="t1",
            project_id="p1",
            task_type="invalid_type",  # 제한조건 위반
            description="Scene 1 video generation",
            status="pending",
            created_at=datetime.now()
        )

def test_task_status_validation():
    # status는 'pending', 'processing', 'success', 'failed' 중 하나여야 함
    with pytest.raises(ValidationError):
        TaskModel(
            task_id="t1",
            project_id="p1",
            task_type="video_generation",
            description="Scene 1 video generation",
            status="done",  # 제한조건 위반
            created_at=datetime.now()
        )

def test_task_retry_relation():
    # 동일 project_id 하위에 여러 태스크가 공존할 수 있는지 관계적 정합성 검증
    project_id = "proj-1"
    task1 = TaskModel(
        task_id="task-1",
        project_id=project_id,
        task_type="final_render",
        description="최종 렌더링 시도 1",
        status="failed",
        created_at=datetime.now()
    )
    task2 = TaskModel(
        task_id="task-2",
        project_id=project_id,
        task_type="final_render",
        description="최종 렌더링 시도 2 (재시도)",
        status="success",
        created_at=datetime.now()
    )
    assert task1.project_id == task2.project_id
    assert task1.task_id != task2.task_id
