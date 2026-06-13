import os
import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import hmac
import hashlib

# 테스트 환경 변수 설정
os.environ["DATABASE_PATH"] = "test_user_videos.json"
os.environ.setdefault("COOKIE_ENCRYPTION_KEY", "3u8V_z5Fp3Uo54b1f4g7Y3k5l1pD_s1t4a5g7r8a9v0=")
os.environ["WEBHOOK_SECRET"] = "test_webhook_secret_key"
os.environ["SUPABASE_JWT_SECRET"] = "test_supabase_jwt_secret_key"

from main import app

def get_signature_headers(body_str: str) -> dict:
    webhook_secret = os.environ["WEBHOOK_SECRET"]
    sig = hmac.new(webhook_secret.encode('utf-8'), body_str.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        "X-KIE-Signature": sig,
        "Content-Type": "application/json"
    }

@pytest.fixture(autouse=True)
def run_around_tests():
    if os.path.exists("test_user_videos.json"):
        os.remove("test_user_videos.json")
    yield
    if os.path.exists("test_user_videos.json"):
        os.remove("test_user_videos.json")

def test_expires_at_set_to_14_days_after_created_at():
    # 14일 만료 테스트는 test_webhook에서 expires_at 생성이 잘 되는지, 그리고 정확히 14일 차이가 나는지 확인
    client = TestClient(app)
    task_id = "test_task_expiry"
    created_now = datetime.utcnow()
    records = [{
        "user_id": "beta_tester",
        "task_id": task_id,
        "status": "pending",
        "product_name": "Test Product",
        "created_at": created_now.isoformat()
    }]
    with open("test_user_videos.json", "w", encoding="utf-8") as f:
        json.dump(records, f)

    payload = {
        "task_id": task_id,
        "status": "completed",
        "result_url": "https://kie.test/video.mp4"
    }
    body_str = json.dumps(payload, separators=(',', ':'))
    headers = get_signature_headers(body_str)
    resp = client.post("/api/webhook/kie", data=body_str, headers=headers)
    assert resp.status_code == 200
    
    with open("test_user_videos.json", "r", encoding="utf-8") as f:
        db_records = json.load(f)
        
    updated = next(r for r in db_records if r["task_id"] == task_id)
    expires_at = datetime.fromisoformat(updated["expires_at"])
    
    # 14일 오차 범위 1시간 이내
    assert abs((expires_at - created_now).total_seconds() - 14 * 24 * 3600) < 3600

def test_expired_tasks_excluded_from_archive_listing():
    # 만료된 태스크(14일 경과)가 /api/archive 조회 목록에서 제외되는지 테스트
    client = TestClient(app)
    
    expired_time = (datetime.utcnow() - timedelta(days=15)).isoformat()
    valid_time = datetime.utcnow().isoformat()
    
    records = [
        {
            "user_id": "beta_tester",
            "task_id": "expired_task",
            "status": "completed",
            "result_url": "https://kie.test/1.mp4",
            "created_at": expired_time,
            "expires_at": (datetime.utcnow() - timedelta(days=1)).isoformat()
        },
        {
            "user_id": "beta_tester",
            "task_id": "valid_task",
            "status": "completed",
            "result_url": "https://kie.test/2.mp4",
            "created_at": valid_time,
            "expires_at": (datetime.utcnow() + timedelta(days=13)).isoformat()
        }
    ]
    
    with open("test_user_videos.json", "w", encoding="utf-8") as f:
        json.dump(records, f)
        
    # /api/archive 조회 (GET)
    resp = client.get("/api/archive?user_id=beta_tester")
    assert resp.status_code == 200
    items = resp.json()["items"]
    
    assert len(items) == 1
    assert items[0]["task_id"] == "valid_task"

def test_archive_enforces_50_item_fifo_limit():
    # FIFO 50개 용량 한도 초과 시 가장 오래된 레코드 삭제 여부 테스트
    client = TestClient(app)
    
    # 50개의 완료된 레코드를 생성하여 DB에 넣음 (created_at 순서대로 정렬)
    records = []
    base_time = datetime.utcnow() - timedelta(days=10)
    for i in range(50):
        created_time = (base_time + timedelta(minutes=i)).isoformat()
        records.append({
            "user_id": "beta_tester",
            "task_id": f"task_{i}",
            "status": "completed",
            "result_url": f"https://kie.test/{i}.mp4",
            "product_name": f"Product {i}",
            "created_at": created_time,
            "expires_at": (base_time + timedelta(days=4, minutes=i)).isoformat()
        })
        
    with open("test_user_videos.json", "w", encoding="utf-8") as f:
        json.dump(records, f)
        
    # main.py에서 /api/render-task 또는 태스크가 새로 생성될 때(또는 webhook 등 수신 시) FIFO가 일어나는지 검증
    # webhook 수신 처리를 통해 FIFO 트리거하도록 구성
    # 신규 52번째 태스크를 pending으로 생성
    new_task_id = "task_new_52"
    records.append({
        "user_id": "beta_tester",
        "task_id": new_task_id,
        "status": "pending",
        "product_name": "Product New 52",
        "created_at": datetime.utcnow().isoformat()
    })
    with open("test_user_videos.json", "w", encoding="utf-8") as f:
        json.dump(records, f)
        
    # webhook 호출하여 completed 상태로 업데이트
    payload_new = {
        "task_id": new_task_id,
        "status": "completed",
        "result_url": "https://kie.test/new_52.mp4"
    }
    body_str_new = json.dumps(payload_new, separators=(',', ':'))
    headers_new = get_signature_headers(body_str_new)
    resp = client.post("/api/webhook/kie", data=body_str_new, headers=headers_new)
    assert resp.status_code == 200
    
    # DB 확인: 전체 개수가 50개여야 하며, 가장 오래된 'task_0'은 지워지고 'task_1'부터 남아있어야 함
    with open("test_user_videos.json", "r", encoding="utf-8") as f:
        db_records = json.load(f)
        
    assert len(db_records) == 50
    task_ids = [r["task_id"] for r in db_records]
    assert "task_0" not in task_ids
    assert "task_1" in task_ids
    assert new_task_id in task_ids
