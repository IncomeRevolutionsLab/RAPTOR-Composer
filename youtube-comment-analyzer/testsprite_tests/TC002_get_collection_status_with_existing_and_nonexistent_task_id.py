import requests
import uuid

BASE_URL = "http://localhost:8000"
TIMEOUT = 30


def test_get_collection_status_with_existing_and_nonexistent_task_id():
    headers = {"Content-Type": "application/json"}
    valid_task_id = None

    # Step 1: Start a collection to get a valid task_id
    json_payload = {"video_id": "dQw4w9WgXcQ"}  # example valid video_id
    try:
        start_resp = requests.post(
            f"{BASE_URL}/start",
            json=json_payload,
            headers=headers,
            timeout=TIMEOUT,
        )
        assert start_resp.status_code == 202, f"Unexpected status code from /start: {start_resp.status_code}, body: {start_resp.text}"
        start_data = start_resp.json()
        assert "task_id" in start_data and isinstance(start_data["task_id"], str)
        valid_task_id = start_data["task_id"]

        # Step 2: GET /status with valid task_id
        status_resp = requests.get(
            f"{BASE_URL}/status",
            params={"task_id": valid_task_id},
            headers=headers,
            timeout=TIMEOUT,
        )
        assert status_resp.status_code == 200, f"Expected 200 for valid task_id, got {status_resp.status_code}, body: {status_resp.text}"
        status_data = status_resp.json()
        assert status_data.get("task_id") == valid_task_id
        assert "progress" in status_data and isinstance(status_data["progress"], (int, float))
        assert "checkpoint" in status_data and isinstance(status_data["checkpoint"], str)

        # Step 3: GET /status with a nonexistent task_id
        nonexistent_task_id = str(uuid.uuid4())
        status_not_found_resp = requests.get(
            f"{BASE_URL}/status",
            params={"task_id": nonexistent_task_id},
            headers=headers,
            timeout=TIMEOUT,
        )
        assert status_not_found_resp.status_code == 404, f"Expected 404 for nonexistent task_id, got {status_not_found_resp.status_code}, body: {status_not_found_resp.text}"
        error_data = status_not_found_resp.json()
        assert error_data.get("error") == "task_not_found"

    finally:
        # Cleanup: stop the started task if valid_task_id was obtained
        if valid_task_id:
            try:
                # stop endpoint requires JSON body
                stop_resp = requests.post(
                    f"{BASE_URL}/stop",
                    json={"task_id": valid_task_id},
                    headers=headers,
                    timeout=TIMEOUT,
                )
                # Accept 200 OK or 404 if already stopped/removed
                if stop_resp.status_code not in (200, 404):
                    raise AssertionError(f"Unexpected status code from /stop: {stop_resp.status_code}, body: {stop_resp.text}")
            except Exception:
                # ignore cleanup errors
                pass


test_get_collection_status_with_existing_and_nonexistent_task_id()
