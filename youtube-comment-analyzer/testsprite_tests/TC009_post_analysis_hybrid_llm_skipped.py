import requests
import time

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_post_analysis_hybrid_llm_skipped():
    # Step 1: Create a new analysis via hybrid mode with missing LLM API key (llm_api_key: null)
    analyze_url = f"{BASE_URL}/analysis/analyze"
    video_id = "test_video_for_hybrid_llm_skipped"
    payload = {
        "mode": "hybrid",
        "video_ids": [video_id],
        "llm_api_key": None
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(analyze_url, json=payload, headers=headers, timeout=TIMEOUT)
    assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"
    data = response.json()

    assert "job_id" in data, "Response JSON missing 'job_id'"
    # Adjusted assertion: Check for llm_skipped and fallback_to_local flags in the response instead of 'note' string
    assert data.get("llm_skipped") is True or data.get("fallback_to_local") is True, "Response JSON missing 'llm_skipped' or 'fallback_to_local' flags"

    job_id = data["job_id"]

    # Step 2: Poll the results endpoint until analysis is complete or timeout reached
    results_url = f"{BASE_URL}/analysis/results"
    max_wait_time = 60
    interval = 5
    elapsed = 0
    results_data = None

    while elapsed < max_wait_time:
        params = {"job_id": job_id}
        res = requests.get(results_url, params=params, timeout=TIMEOUT)
        if res.status_code == 200:
            results_data = res.json()
            # Assume presence of results means complete, break early
            break
        elif res.status_code == 202:  # Accepted, processing
            time.sleep(interval)
            elapsed += interval
            continue
        else:
            res.raise_for_status()

    assert results_data is not None, "Did not receive completed results in time"

    # Step 3: Verify that results reflect local NLP only and a flag indicating LLM was skipped
    # Check presence of expected local NLP fields
    assert "sentiment_distribution" in results_data or results_data.get("local_nlp_only") is True, \
        "Results missing local NLP output"
    # Check indication that LLM was skipped due to missing API key
    assert results_data.get("llm_skipped") is True or results_data.get("local_nlp_only") is True, \
        "Results do not indicate that LLM was skipped and fallback used"

test_post_analysis_hybrid_llm_skipped()
