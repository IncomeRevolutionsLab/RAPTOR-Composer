import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_get_results_with_failed_or_incomplete_analysis():
    # Trigger an analysis that causes failure due to missing or invalid input
    analyze_url = f"{BASE_URL}/analyze"
    headers = {"Content-Type": "application/json"}
    payload = {
        "video_id": "invalid_or_missing",  # According to PRD this triggers 422 on analyze
        "options": {}  # minimal options to adhere to required schema
    }

    response_analyze = requests.post(analyze_url, json=payload, headers=headers, timeout=TIMEOUT)
    assert response_analyze.status_code == 422, f"Expected 422 Unprocessable Entity but got {response_analyze.status_code}"
    data_analyze = response_analyze.json()
    assert "error" in data_analyze and data_analyze["error"] == "missing_or_invalid_input"

    # Test GET /results with dummy analysis_ids that represent failed or incomplete analysis
    test_analysis_ids = [
        "nonexistent_failed_analysis_id",  # expecting 400 Bad Request with error analysis_failed
        "nonexistent_incomplete_analysis_id"  # possibly 204 No Content with message indicating not produced
    ]

    results_url = f"{BASE_URL}/results"

    for analysis_id in test_analysis_ids:
        params = {"analysis_id": analysis_id}
        response_results = requests.get(results_url, params=params, timeout=TIMEOUT)
        if response_results.status_code == 400:
            data_results = response_results.json()
            assert "error" in data_results, "Expected error key in response JSON for 400 status"
            assert data_results["error"] == "analysis_failed", f"Expected error 'analysis_failed', got {data_results['error']}"
        elif response_results.status_code == 204:
            try:
                data_results = response_results.json()
                assert "message" in data_results and isinstance(data_results["message"], str), "Expected message in 204 response"
            except ValueError:
                pass
        else:
            assert False, f"Unexpected status code {response_results.status_code} for analysis_id {analysis_id}"

test_get_results_with_failed_or_incomplete_analysis()
