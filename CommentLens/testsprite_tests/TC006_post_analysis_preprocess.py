import requests
import time

BASE_URL = "http://localhost:8000"
ANALYZE_ENDPOINT = f"{BASE_URL}/analysis/analyze"
RESULTS_ENDPOINT = f"{BASE_URL}/analysis/results"
COLLECTION_START_ENDPOINT = f"{BASE_URL}/start"
COLLECTION_STOP_ENDPOINT = f"{BASE_URL}/stop"

def create_collection(video_id: str) -> str:
    payload = {"video_id": video_id}
    resp = requests.post(COLLECTION_START_ENDPOINT, json=payload, timeout=30)
    assert resp.status_code == 202, f"Expected 202 status code, got {resp.status_code}"
    data = resp.json()
    assert "task_id" in data, "Response JSON missing 'task_id'"
    assert "status" in data, "Response JSON missing 'status'"
    assert data["status"] == "started", f"Expected status 'started', got {data['status']}"
    return data["task_id"]

def stop_collection(task_id: str):
    payload = {"task_id": task_id}
    resp = requests.post(COLLECTION_STOP_ENDPOINT, json=payload, timeout=30)
    if resp.status_code not in (200, 204, 202):
        resp.raise_for_status()

def test_post_analysis_preprocess():
    # Step 1: Create a new video_id by starting a collection to have valid video_id for preprocessing
    video_id = f"testvideo-{int(time.time())}"
    task_id = None
    try:
        task_id = create_collection(video_id)
        # Wait short time to ensure collection initialization (optional)
        time.sleep(1)

        # Step 2: Trigger preprocessing analysis with valid video_id
        payload = {"action": "preprocess", "video_ids": [video_id]}
        resp = requests.post(ANALYZE_ENDPOINT, json=payload, timeout=30)

        # Step 3: Validate response 200 and contains job_id and status 'preprocessing'
        assert resp.status_code == 200
        resp_json = resp.json()
        assert "job_id" in resp_json
        assert resp_json.get("status") == "preprocessing"

    finally:
        # Cleanup: stop collection task
        if task_id:
            try:
                stop_collection(task_id)
            except Exception:
                pass

test_post_analysis_preprocess()
