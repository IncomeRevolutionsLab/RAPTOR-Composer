import requests
import uuid

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_post_analysis_hybrid_pipeline():
    # Step 1: Create a new comment collection task to get a valid video_id
    start_url = f"{BASE_URL}/start"
    video_id = f"test_video_{uuid.uuid4()}"
    start_payload = {"video_id": video_id}
    try:
        start_resp = requests.post(start_url, json=start_payload, timeout=TIMEOUT)
        assert start_resp.status_code == 202, f"Expected 202, got {start_resp.status_code}"
        start_data = start_resp.json()
        assert "task_id" in start_data, "task_id missing in start response"
        # Accept both 'started' and 'accepted' statuses as per PRD
        assert start_data.get("status") in ["started", "accepted"], f"Expected status 'started' or 'accepted', got {start_data.get('status')}"

        # Step 2: POST to /analysis/analyze with mode 'hybrid' and valid video_ids + llm_token_fraction
        analyze_url = f"{BASE_URL}/analysis/analyze"
        analyze_payload = {
            "mode": "hybrid",
            "video_ids": [video_id],
            "llm_token_fraction": 0.05
        }
        analyze_resp = requests.post(analyze_url, json=analyze_payload, timeout=TIMEOUT)
        assert analyze_resp.status_code == 200, f"Expected 200, got {analyze_resp.status_code}"
        analyze_data = analyze_resp.json()
        assert "job_id" in analyze_data, "job_id missing in analysis response"
        assert analyze_data.get("stage") == "local_nlp_running", f"Expected stage 'local_nlp_running', got {analyze_data.get('stage')}"

    finally:
        # Cleanup: stop the collection task and optionally ensure cleanup
        if 'start_data' in locals() and "task_id" in start_data:
            stop_url = f"{BASE_URL}/stop"
            stop_payload = {"task_id": start_data["task_id"]}
            try:
                requests.post(stop_url, json=stop_payload, timeout=TIMEOUT)
            except Exception:
                pass

test_post_analysis_hybrid_pipeline()
