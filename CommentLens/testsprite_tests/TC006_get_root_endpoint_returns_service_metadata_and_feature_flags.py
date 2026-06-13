import requests

def test_get_root_endpoint_returns_service_metadata_and_feature_flags():
    base_url = "http://localhost:8000"
    headers = {
        "Accept": "application/json"
    }
    try:
        response = requests.get(f"{base_url}/", headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request to root endpoint failed with exception: {e}"
    assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"
    # Validate presence of service metadata keys and feature flags (features key)
    expected_meta_keys = {"project", "date", "prepared_by"}
    assert "meta" in data, "'meta' key not found in response JSON"
    assert expected_meta_keys.issubset(data["meta"].keys()), f"'meta' does not contain expected keys {expected_meta_keys}"
    assert "features" in data, "'features' key not found in response JSON"
    assert isinstance(data["features"], list), "'features' should be a list"
    # Optional: check that features contain expected keys name and description
    for feature in data["features"]:
        assert isinstance(feature, dict), "Each feature should be a dict"
        assert "name" in feature and "description" in feature, "Feature missing 'name' or 'description'"
    # Additional sanity check of project name
    assert data["meta"]["project"] == "YT-Comment Insight Engine V2", "Unexpected project name in metadata"

test_get_root_endpoint_returns_service_metadata_and_feature_flags()