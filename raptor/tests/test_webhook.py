import os
import json
import pytest
from fastapi.testclient import TestClient
import hmac
import hashlib

# 테스트 환경 변수 설정
os.environ["DATABASE_PATH"] = "test_user_videos.json"
os.environ.setdefault("COOKIE_ENCRYPTION_KEY", "3u8V_z5Fp3Uo54b1f4g7Y3k5l1pD_s1t4a5g7r8a9v0=")
os.environ["WEBHOOK_SECRET"] = "test_webhook_secret_key"

from main import app

@pytest.fixture(autouse=True)
def run_around_tests():
    # Setup: clean test DB
    if os.path.exists("test_user_videos.json"):
        os.remove("test_user_videos.json")
    yield
    # Teardown: clean test DB
    if os.path.exists("test_user_videos.json"):
        os.remove("test_user_videos.json")

def get_signature_headers(body_str: str) -> dict:
    webhook_secret = os.environ["WEBHOOK_SECRET"]
    sig = hmac.new(webhook_secret.encode('utf-8'), body_str.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        "X-KIE-Signature": sig,
        "Content-Type": "application/json"
    }

def post_webhook(client, payload):
    body_str = json.dumps(payload, separators=(',', ':'))
    headers = get_signature_headers(body_str)
    return client.post("/api/webhook/kie", data=body_str, headers=headers)

def test_webhook_completed_updates_task_and_sets_expiry():
    client = TestClient(app)
    
    # 1. 태스크 생성(pending 상태 레코드 생성)
    task_id = "test_task_123"
    records = [{
        "user_id": "beta_tester",
        "task_id": task_id,
        "status": "pending",
        "product_name": "Test Product",
        "created_at": "2026-06-03T12:00:00"
    }]
    with open("test_user_videos.json", "w", encoding="utf-8") as f:
        json.dump(records, f)

    payload = {
        "task_id": task_id,
        "status": "completed",
        "result_url": "https://kie.test/video.mp4"
    }
    
    resp = post_webhook(client, payload)
    assert resp.status_code == 200
    assert resp.json() == {"received": True}
    
    # DB 반영 검증
    with open("test_user_videos.json", "r", encoding="utf-8") as f:
        db_records = json.load(f)
    
    updated = next(r for r in db_records if r["task_id"] == task_id)
    assert updated["status"] == "completed"
    assert updated["result_url"] == "https://kie.test/video.mp4"
    assert "expires_at" in updated

def test_webhook_failed_status_stores_error():
    client = TestClient(app)
    task_id = "test_task_456"
    records = [{
        "user_id": "beta_tester",
        "task_id": task_id,
        "status": "pending",
        "product_name": "Test Product",
        "created_at": "2026-06-03T12:00:00"
    }]
    with open("test_user_videos.json", "w", encoding="utf-8") as f:
        json.dump(records, f)

    payload = {
        "task_id": task_id,
        "status": "failed",
        "error": "GPU out of memory"
    }
    resp = post_webhook(client, payload)
    assert resp.status_code == 200
    
    with open("test_user_videos.json", "r", encoding="utf-8") as f:
        db_records = json.load(f)
    
    updated = next(r for r in db_records if r["task_id"] == task_id)
    assert updated["status"] == "failed"
    assert updated["error"] == "GPU out of memory"

def test_webhook_returns_404_for_unknown_task_id():
    client = TestClient(app)
    payload = {
        "task_id": "NONEXISTENT",
        "status": "completed",
        "result_url": "https://..."
    }
    resp = post_webhook(client, payload)
    assert resp.status_code == 404

def test_webhook_invalid_signature():
    client = TestClient(app)
    payload = {
        "task_id": "test_task_123",
        "status": "completed",
        "result_url": "https://..."
    }
    body_str = json.dumps(payload, separators=(',', ':'))
    headers = {
        "X-KIE-Signature": "invalid_signature_value",
        "Content-Type": "application/json"
    }
    resp = client.post("/api/webhook/kie", data=body_str, headers=headers)
    assert resp.status_code == 401

def test_webhook_missing_signature():
    client = TestClient(app)
    payload = {
        "task_id": "test_task_123",
        "status": "completed",
        "result_url": "https://..."
    }
    body_str = json.dumps(payload, separators=(',', ':'))
    headers = {
        "Content-Type": "application/json"
    }
    resp = client.post("/api/webhook/kie", data=body_str, headers=headers)
    assert resp.status_code == 401
