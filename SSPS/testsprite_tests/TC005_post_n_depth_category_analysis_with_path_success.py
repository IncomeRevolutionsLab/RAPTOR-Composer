import requests

def test_post_n_depth_category_analysis_with_path_success():
    base_url = "http://localhost:5000"
    url = f"{base_url}/api/v1/category_node"
    headers = {"Content-Type": "application/json"}
    payload = {
        "path": ["화장품", "스킨케어"]
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        data = response.json()

        # Validate response keys
        assert "path" in data, "'path' key missing in response"
        assert "is_leaf" in data, "'is_leaf' key missing in response"
        assert "trend_series" in data, "'trend_series' key missing in response"
        assert "products" in data, "'products' key missing in response"

        # Validate path is the same as sent
        assert isinstance(data["path"], list), "'path' should be a list"
        assert data["path"] == payload["path"], f"Expected path {payload['path']}, got {data['path']}"

        # Validate is_leaf boolean
        assert isinstance(data["is_leaf"], bool), "'is_leaf' should be a boolean"

        # Validate trend_series is an object (dict)
        assert isinstance(data["trend_series"], dict), "'trend_series' should be an object"

        # Validate products is an array (list)
        assert isinstance(data["products"], list), "'products' should be a list"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

test_post_n_depth_category_analysis_with_path_success()