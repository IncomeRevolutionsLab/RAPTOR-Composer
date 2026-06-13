import requests

BASE_URL = "http://localhost:5000"
TIMEOUT = 30

def test_post_n_depth_category_analysis_with_keyword_success():
    url = f"{BASE_URL}/api/v1/category_node"
    headers = {"Content-Type": "application/json"}
    payload = {"keyword": "패션의류"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        data = response.json()

        # Validate required fields
        assert "path" in data, "'path' field missing in response"
        assert isinstance(data["path"], list), "'path' field is not a list"
        assert len(data["path"]) > 0, "'path' field is empty"

        assert "is_leaf" in data, "'is_leaf' field missing in response"
        assert isinstance(data["is_leaf"], bool), "'is_leaf' is not boolean"

        assert "trend_series" in data, "'trend_series' field missing in response"
        assert isinstance(data["trend_series"], dict), "'trend_series' is not an object"

        assert "products" in data, "'products' field missing in response"
        assert isinstance(data["products"], list), "'products' is not a list"

    except requests.exceptions.RequestException as e:
        assert False, f"Request failed: {e}"

test_post_n_depth_category_analysis_with_keyword_success()