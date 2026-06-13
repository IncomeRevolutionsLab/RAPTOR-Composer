import requests

BASE_URL = "http://localhost:8000"
START_PATH = "/start"
TIMEOUT = 30

def test_post_start_comment_collection():
    url = BASE_URL + START_PATH
    payload = {
        "video_id": "dQw4w9WgXcQ",
        "options": {
            "max_comments": 100,
            "language": "en",
            "include_replies": True
        }
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    # Assert status code 202 Accepted
    assert response.status_code == 202, f"Expected status 202 but got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Assert presence and validity of task_id and status
    assert "task_id" in data, "Response JSON missing 'task_id'"
    assert isinstance(data["task_id"], str) and data["task_id"], "'task_id' should be a non-empty string"
    assert "status" in data, "Response JSON missing 'status'"
    assert data["status"] == "started", f"Expected status 'started' but got '{data['status']}'"


test_post_start_comment_collection()