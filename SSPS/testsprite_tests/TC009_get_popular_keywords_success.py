import requests

def test_get_popular_keywords_success():
    base_url = "http://localhost:5000"
    endpoint = "/api/v1/popular_keywords"
    params = {
        "domain": "beauty",
        "window": 7,
        "simulate_timeout": "true"
    }
    headers = {
        "Accept": "application/json"
    }
    try:
        response = requests.get(
            url=base_url + endpoint,
            params=params,
            headers=headers,
            timeout=30
        )
    except requests.exceptions.Timeout:
        assert False, "Request timed out unexpectedly."
    except requests.exceptions.RequestException as e:
        assert False, f"Request failed: {e}"
    
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    json_data = response.json()
    assert json_data.get("status") == "success", f"Expected status 'success', got {json_data.get('status')}"
    assert "items" in json_data, "Response JSON missing 'items' field"
    assert isinstance(json_data["items"], list), "'items' is not a list"
    
    for item in json_data["items"]:
        assert isinstance(item, dict), "Each item should be a dict"
        assert "keyword" in item, "Item missing 'keyword'"
        assert isinstance(item["keyword"], str), "'keyword' should be a string"
        assert "score" in item, "Item missing 'score'"
        assert isinstance(item["score"], (int, float)), "'score' should be a number"
        assert "domain" in item, "Item missing 'domain'"
        assert isinstance(item["domain"], str), "'domain' should be a string"
        assert "timeframe" in item, "Item missing 'timeframe'"
        assert item["timeframe"] in ["daily", "weekly"], "'timeframe' should be 'daily' or 'weekly'"

test_get_popular_keywords_success()