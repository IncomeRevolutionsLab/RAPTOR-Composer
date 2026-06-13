import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_post_stop_collection_task():
    start_url = f"{BASE_URL}/start"
    stop_url = f"{BASE_URL}/stop"
    
    # Step 1: Create a valid collection task to get a valid task_id
    start_payload = {"video_id": "dQw4w9WgXcQ"}  # Using a common valid video ID example
    try:
        start_resp = requests.post(start_url, json=start_payload, timeout=TIMEOUT)
        assert start_resp.status_code == 202, f"Expected 202 Accepted from /start but got {start_resp.status_code}"
        start_data = start_resp.json()
        assert "task_id" in start_data and start_data.get("status") == "started", "Missing task_id or incorrect status in start response"
        valid_task_id = start_data["task_id"]
        
        # Step 2: Stop the valid task_id - expect success (200 or 202 accepted)
        stop_payload_valid = {"task_id": valid_task_id}
        stop_resp_valid = requests.post(stop_url, json=stop_payload_valid, timeout=TIMEOUT)
        assert stop_resp_valid.status_code in (200, 202), f"Expected 200 or 202 from /stop for valid task_id but got {stop_resp_valid.status_code}"
        stop_data_valid = stop_resp_valid.json()
        # Validate success response presence
        assert "task_id" in stop_data_valid and stop_data_valid["task_id"] == valid_task_id, "Response task_id does not match valid task_id"
        assert stop_data_valid.get("status") in ("stopped", "stopping", "success", "accepted"), "Unexpected status in stop response for valid task_id"
        
        # Step 3: Stop a nonexistent task_id - expect 404 Not Found
        invalid_task_id = "nonexistent-task-12345"
        stop_payload_invalid = {"task_id": invalid_task_id}
        stop_resp_invalid = requests.post(stop_url, json=stop_payload_invalid, timeout=TIMEOUT)
        assert stop_resp_invalid.status_code == 404, f"Expected 404 Not Found from /stop for nonexistent task_id but got {stop_resp_invalid.status_code}"
    finally:
        # Cleanup: attempt to stop the valid task again to ensure no leftover running tasks
        if 'valid_task_id' in locals():
            try:
                requests.post(stop_url, json={"task_id": valid_task_id}, timeout=TIMEOUT)
            except:
                pass

test_post_stop_collection_task()