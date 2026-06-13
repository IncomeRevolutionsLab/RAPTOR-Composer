import requests
import time

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_post_analyze_with_valid_inputs_and_llm_key():
    # Setup: create a collection task to get a valid video_id
    video_id = None
    try:
        # Start collection to ensure the video_id exists and data is available
        start_resp = requests.post(
            f"{BASE_URL}/start",
            json={"video_id": "dQw4w9WgXcQ"},
            timeout=TIMEOUT
        )
        assert start_resp.status_code == 202, f"Failed to start collection, got {start_resp.status_code}"
        start_data = start_resp.json()
        # Use the known video id since collection started
        video_id = "dQw4w9WgXcQ"

        # Define valid payload for analyze POST
        analyze_payload = {
            "video_id": video_id,
            "options": {
                "nlp_only": False,
                "llm_token_limit_percent": 5
            },
            "llm_key": "valid_llm_key_123"
        }

        analyze_resp = requests.post(
            f"{BASE_URL}/analyze",
            json=analyze_payload,
            timeout=TIMEOUT
        )
        assert analyze_resp.status_code == 202, f"Expected 202 Accepted, got {analyze_resp.status_code}"

        analyze_data = analyze_resp.json()

        assert "analysis_id" in analyze_data, "Response missing analysis_id"
        # pipeline type expected is hybrid
        assert analyze_data.get("pipeline") == "hybrid", f"Expected pipeline 'hybrid', got {analyze_data.get('pipeline')}"

    finally:
        # Cleanup: stop the collection if it was started
        if video_id:
            # Get history to find the task_id related to this video_id collection
            history_resp = requests.get(f"{BASE_URL}/history", timeout=TIMEOUT)
            if history_resp.status_code == 200:
                tasks = history_resp.json()
                for task in tasks:
                    if task.get("video_id") == video_id and task.get("status") != "stopped":
                        task_id = task.get("task_id")
                        if task_id:
                            try:
                                requests.post(f"{BASE_URL}/stop", json={"task_id": task_id}, timeout=TIMEOUT)
                            except Exception:
                                pass

test_post_analyze_with_valid_inputs_and_llm_key()