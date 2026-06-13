import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_post_open_folder_supported_and_unsupported_os():
    url = f"{BASE_URL}/open-folder"

    # Test attempt assuming Windows OS (supported)
    try:
        response = requests.post(url, timeout=TIMEOUT)
        # The PRD implies this is expected to succeed on Windows
        # but no success schema is explicitly specified. We check for 200 OK or 204 No Content as success codes.
        assert response.status_code in (200, 204), f"Expected 200 or 204 on Windows, got {response.status_code}"
        # Since no schema is defined for success, no further content check is done.
    except requests.RequestException as e:
        raise AssertionError(f"Request failed on supported OS test with error: {e}")

    # Test attempt simulating unsupported OS.
    # Since the server detects OS itself, we can't directly simulate OS override via the API.
    # So we must confirm that when not Windows (e.g., by running on Linux or macOS), the API returns 500 with error unsupported_os.
    # If on Windows environment, this test cannot be checked properly.
    try:
        unsupported_response = requests.post(url, timeout=TIMEOUT)
        if unsupported_response.status_code == 500:
            json_resp = unsupported_response.json()
            assert "error" in json_resp and json_resp["error"] == "unsupported_os", \
                "Expected error 'unsupported_os' key in response JSON"
            assert "message" in json_resp and "open-folder available only on Windows" in json_resp["message"], \
                "Expected message indicating open-folder only on Windows"
        elif unsupported_response.status_code in (200, 204):
            # This means this environment is Windows, so unsupported OS test cannot be validated here.
            pass
        else:
            raise AssertionError(
                f"Unexpected status code for unsupported OS test: {unsupported_response.status_code}, body: {unsupported_response.text}")
    except requests.RequestException as e:
        raise AssertionError(f"Request failed on unsupported OS test with error: {e}")

test_post_open_folder_supported_and_unsupported_os()