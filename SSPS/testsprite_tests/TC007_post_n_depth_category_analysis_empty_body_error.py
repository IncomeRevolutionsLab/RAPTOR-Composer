import requests

def test_post_n_depth_category_analysis_empty_body_error():
    base_url = "http://localhost:5000"
    url = f"{base_url}/api/v1/category_node"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json={}, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 400, f"Expected status code 400, got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    assert data.get("status") == "error", f"Expected status 'error', got {data.get('status')}"
    expected_message = "path or keyword required"
    assert data.get("message") == expected_message, f"Expected message '{expected_message}', got '{data.get('message')}'"


test_post_n_depth_category_analysis_empty_body_error()