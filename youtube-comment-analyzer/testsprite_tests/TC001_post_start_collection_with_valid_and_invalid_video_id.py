import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_post_start_collection_with_valid_and_invalid_video_id():
    # Test with valid video_id
    valid_video_id = "dQw4w9WgXcQ"  # example valid YouTube video ID
    start_url = f"{BASE_URL}/start"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(start_url, json={"video_id": valid_video_id}, headers=headers, timeout=TIMEOUT)
        assert response.status_code == 202, f"Expected 202 Accepted, got {response.status_code}"
        data = response.json()
        assert "task_id" in data and isinstance(data["task_id"], str) and data["task_id"], "Missing or invalid task_id in response"
        assert "message" in data and data["message"] == "collection started", "Missing or incorrect message in response"

        valid_task_id = data["task_id"]

        # Cleanup: stop the collection task
        stop_url = f"{BASE_URL}/stop"
        stop_response = requests.post(stop_url, json={"task_id": valid_task_id}, headers=headers, timeout=TIMEOUT)
        assert stop_response.status_code == 200, f"Expected 200 OK on stop, got {stop_response.status_code}"
        stop_data = stop_response.json()
        assert stop_data.get("task_id") == valid_task_id, "Stop response task_id mismatch"
        assert stop_data.get("status") == "stopped", "Stop response status not 'stopped'"

    except Exception as e:
        raise AssertionError(f"Valid video_id test failed: {e}")

    # Test with invalid video_id
    invalid_video_ids = [None, "", "invalid_or_missing", "!!!@@@###"]

    for invalid_vid in invalid_video_ids:
        payload = {} if invalid_vid is None else {"video_id": invalid_vid}
        try:
            response = requests.post(start_url, json=payload, headers=headers, timeout=TIMEOUT)
            assert response.status_code == 400, f"Expected 400 Bad Request for invalid video_id '{invalid_vid}', got {response.status_code}"
            data = response.json()
            assert "error" in data and data["error"] == "invalid_video_id", f"Expected error 'invalid_video_id' but got {data.get('error')}"
        except Exception as e:
            raise AssertionError(f"Invalid video_id test '{invalid_vid}' failed: {e}")


test_post_start_collection_with_valid_and_invalid_video_id()