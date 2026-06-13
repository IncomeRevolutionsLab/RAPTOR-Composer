import requests

def test_post_n_depth_category_analysis_large_result_set_error():
    base_url = "http://localhost:5000"
    url = f"{base_url}/api/v1/category_node"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {"path": ["전체"]}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 504, f"Expected status code 504, got {response.status_code}"
    try:
        resp_json = response.json()
    except ValueError:
        assert False, "Response is not in JSON format"

    assert resp_json.get("status") == "error", f"Expected status 'error', got {resp_json.get('status')}"
    message = resp_json.get("message", "").lower()
    assert "result_set_too_large" in message or "too large" in message, "Error message does not indicate large result set"
    assert "pagination" in message or "narrower path" in message, "Error message does not suggest pagination or narrower path"

test_post_n_depth_category_analysis_large_result_set_error()