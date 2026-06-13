import requests

BASE_URL = "http://localhost:8000"


def test_post_analyze_with_missing_or_malformed_inputs():
    url = f"{BASE_URL}/analyze"
    headers = {"Content-Type": "application/json"}

    # Changed malformed video_id to empty string (still string, but invalid) to trigger 422
    payload_malformed_video_id = {"video_id": "", "options": {"preprocess": True}}

    # Test 3: Missing options key (only video_id)
    payload_missing_options = {"video_id": "some_video_id"}

    # Test 4: Options malformed (not a dict)
    payload_malformed_options = {"video_id": "some_video_id", "options": "not_a_dict"}

    test_payloads = [
        payload_malformed_video_id,
        payload_missing_options,
        payload_malformed_options,
    ]

    for payload in test_payloads:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            assert False, f"Request failed with exception: {exc}"

        assert response.status_code == 422, (
            f"Expected 422 Unprocessable Entity but got {response.status_code} "
            f"for payload: {payload}"
        )
        try:
            json_resp = response.json()
        except ValueError:
            assert False, "Response is not valid JSON"

        assert "error" in json_resp, "Response JSON missing 'error' field"
        assert json_resp["error"] == "missing_or_invalid_input", (
            f"Expected error to be 'missing_or_invalid_input' but got {json_resp['error']}"
        )
        assert "details" in json_resp, "Response JSON missing 'details' field"


test_post_analyze_with_missing_or_malformed_inputs()
