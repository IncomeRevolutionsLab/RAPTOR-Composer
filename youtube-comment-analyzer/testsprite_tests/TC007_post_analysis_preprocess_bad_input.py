import requests

BASE_URL = "http://localhost:8000"
ANALYZE_ENDPOINT = f"{BASE_URL}/analysis/analyze"
RESULTS_ENDPOINT = f"{BASE_URL}/analysis/results"
TIMEOUT = 30

def test_post_analysis_preprocess_bad_input():
    malformed_input_path = "1_collection/data/fake_video_id/bad_format.csv"
    analyze_payload = {
        "action": "preprocess",
        "input_path": malformed_input_path
    }
    headers = {"Content-Type": "application/json"}

    # Step 1: POST with malformed CSV input, expect 400 Bad Request with error message 'malformed CSV'
    response_post = requests.post(
        ANALYZE_ENDPOINT,
        json=analyze_payload,
        headers=headers,
        timeout=TIMEOUT
    )
    assert response_post.status_code == 400, f"Expected 400, got {response_post.status_code}"
    try:
        error_data = response_post.json()
    except Exception:
        assert False, "Response to malformed input is not json"

    error_message = None
    if "error" in error_data:
        error_message = error_data["error"]
    elif "detail" in error_data:
        detail = error_data["detail"]
        if isinstance(detail, list) and len(detail) > 0:
            # detail might be a list of dict with 'msg' key
            first_item = detail[0]
            if isinstance(first_item, dict) and "msg" in first_item:
                error_message = first_item["msg"]
            else:
                error_message = str(first_item)
        else:
            # detail is a string or empty
            error_message = str(detail)
    else:
        assert False, "Response JSON has neither 'error' nor 'detail' key"

    assert "malformed CSV" in error_message, f"Expected 'malformed CSV' error, got: {error_message}"

    # Extract job_id from error response if present, else construct a dummy job_id to test GET results
    job_id = error_data.get("job_id")
    if not job_id:
        # Use an unlikely job_id to simulate lookup of non-existent job
        job_id = "invalid_job_id_for_bad_csv"

    # Step 2: GET /analysis/results?job_id=<job_id> - expect 404 Not Found
    params = {"job_id": job_id}
    response_get = requests.get(RESULTS_ENDPOINT, params=params, timeout=TIMEOUT)
    assert response_get.status_code == 404, f"Expected 404, got {response_get.status_code}"


test_post_analysis_preprocess_bad_input()