import requests

def test_get_global_realtime_stats_database_timeout():
    base_url = "http://localhost:5000"
    url = f"{base_url}/api/v1/stats"
    params = {"simulate_timeout": "true"}
    headers = {"Accept": "application/json"}
    timeout = 30

    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        assert response.status_code == 503, f"Expected status code 503, got {response.status_code}"
        json_data = response.json()
        assert json_data.get("status") == "error", f"Expected status 'error', got {json_data.get('status')}"
        assert "message" in json_data, "'message' field not found in response"
        assert "timeout" in json_data["message"].lower(), f"Expected timeout message in 'message', got {json_data['message']}"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

test_get_global_realtime_stats_database_timeout()