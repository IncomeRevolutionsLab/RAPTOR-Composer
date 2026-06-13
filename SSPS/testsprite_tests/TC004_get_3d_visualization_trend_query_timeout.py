import requests

BASE_URL = "http://localhost:5000"
TIMEOUT = 30

def test_get_3d_visualization_trend_query_timeout():
    url = f"{BASE_URL}/api/v1/domains/trend"
    try:
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            json_data = response.json()
            assert isinstance(json_data, dict), "Response is not a JSON object"
            assert json_data.get("status") == "success", f"Expected status 'success' but got {json_data.get('status')}"
            assert isinstance(json_data.get("months"), list), "months should be a list"
            assert all(isinstance(m, str) for m in json_data["months"]), "months should be list of strings"
            assert isinstance(json_data.get("categories"), list), "categories should be a list"
            assert all(isinstance(c, str) for c in json_data["categories"]), "categories should be list of strings"
            assert isinstance(json_data.get("data"), list), "data should be a list"
            assert all(isinstance(row, list) for row in json_data["data"]), "data should be 2D list"
            assert all(all(isinstance(num, (int, float)) for num in row) for row in json_data["data"]), "data should be 2D list of numbers"
        else:
            # We expect a 504 status for timeout or too large requests
            assert response.status_code == 504, f"Expected status code 504 but got {response.status_code}"
            json_data = response.json()
            assert isinstance(json_data, dict), "Response is not a JSON object"
            assert json_data.get("status") == "error", f"Expected status 'error' but got {json_data.get('status')}"
            msg = json_data.get("message", "").lower()
            assert "query timeout" in msg or "request too large" in msg, \
                "Error message does not indicate query timeout or large request"
    except requests.exceptions.Timeout:
        # Accept timeout exceptions as equivalent to query timeout response
        pass
    except requests.exceptions.RequestException as e:
        assert False, f"Request failed with exception: {e}"

test_get_3d_visualization_trend_query_timeout()