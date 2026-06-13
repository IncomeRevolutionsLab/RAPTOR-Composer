import requests

def test_get_global_realtime_stats_success():
    base_url = "http://localhost:5000"
    endpoint = "/api/v1/stats"
    url = base_url + endpoint
    timeout = 30
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    assert isinstance(data, dict), f"Response JSON root should be a dict, got {type(data)}"
    assert data.get("status") == "success", f"Expected status 'success', got {data.get('status')}"
    assert "total_analysis" in data, "Response JSON missing 'total_analysis'"
    assert isinstance(data["total_analysis"], (int, float)), f"'total_analysis' should be a number, got {type(data['total_analysis'])}"
    assert "top_domain" in data, "Response JSON missing 'top_domain'"
    assert isinstance(data["top_domain"], str), f"'top_domain' should be a string, got {type(data['top_domain'])}"

test_get_global_realtime_stats_success()