import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30


def test_post_stop_collection_with_valid_task_id():
    start_url = f"{BASE_URL}/start"
    stop_url = f"{BASE_URL}/stop"

    headers = {"Content-Type": "application/json"}

    # Step 1: Start a collection to get a valid task_id
    start_payload = {"video_id": "dQw4w9WgXcQ"}
    task_id = None

    try:
        start_resp = requests.post(start_url, json=start_payload, headers=headers, timeout=TIMEOUT)
        assert start_resp.status_code == 202, f"Expected 202 Accepted, got {start_resp.status_code}"
        start_data = start_resp.json()
        assert "task_id" in start_data, "Response JSON missing 'task_id'"
        assert "message" in start_data and start_data["message"] == "collection started", "Unexpected start message"
        task_id = start_data["task_id"]
        assert isinstance(task_id, str) and task_id.strip(), "Invalid task_id returned"

        # Step 2: Stop the collection using the obtained task_id
        stop_payload = {"task_id": task_id}
        stop_resp = requests.post(stop_url, json=stop_payload, headers=headers, timeout=TIMEOUT)
        assert stop_resp.status_code == 200, f"Expected 200 OK, got {stop_resp.status_code}"
        stop_data = stop_resp.json()
        assert stop_data.get("task_id") == task_id, "task_id in stop response does not match"
        assert stop_data.get("status") == "stopped", "Status in stop response is not 'stopped'"

    finally:
        # Cleanup: If the stop request failed for any reason and the task_id exists,
        # attempt to stop the collection to avoid lingering tasks.
        if task_id:
            try:
                requests.post(stop_url, json={"task_id": task_id}, headers=headers, timeout=TIMEOUT)
            except Exception:
                pass


test_post_stop_collection_with_valid_task_id()