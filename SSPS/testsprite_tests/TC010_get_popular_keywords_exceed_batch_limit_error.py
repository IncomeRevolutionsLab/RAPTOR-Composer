import requests

def test_get_popular_keywords_exceed_batch_limit_error():
    base_url = "http://localhost:5000"
    endpoint = "/api/v1/popular_keywords"
    keywords = "kw1,kw2,kw3,kw4"  # more than 3 keywords to exceed batch limit
    params = {"keywords": keywords}
    try:
        response = requests.get(f"{base_url}{endpoint}", params=params, timeout=30)
        assert response.status_code == 400, f"Expected status code 400 but got {response.status_code}"
        json_data = response.json()
        assert json_data.get("status") == "error", f"Expected status 'error' but got {json_data.get('status')}"
        assert "naver_batch_limit_exceeded" in json_data.get("message", ""), "Error message does not indicate Naver batch limit exceeded"
    except requests.RequestException as e:
        assert False, f"Request failed with exception: {e}"

test_get_popular_keywords_exceed_batch_limit_error()