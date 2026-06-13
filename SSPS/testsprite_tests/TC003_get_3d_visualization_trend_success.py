import requests

def test_get_3d_visualization_trend_success():
    url = "http://localhost:5000/api/v1/domains/trend"
    params = {"simulate_timeout": "true"}
    try:
        response = requests.get(url, params=params, timeout=30)
        assert response.status_code == 504 or response.status_code == 200

        json_response = response.json()

        if response.status_code == 200:
            assert json_response.get("status") == "success"
            months = json_response.get("months")
            categories = json_response.get("categories")
            data = json_response.get("data")

            assert isinstance(months, list)
            # Each month string should end with '월' and have length 3, e.g., '04월'
            for month in months:
                assert isinstance(month, str)
                assert len(month) == 3
                assert month.endswith("월")
                # Further month format validation is intentionally omitted per instructions

            assert isinstance(categories, list)
            for category in categories:
                assert isinstance(category, str)

            assert isinstance(data, list)
            # Validate data is a 2D list of numbers
            for row in data:
                assert isinstance(row, list)
                for value in row:
                    assert isinstance(value, (int, float))
        else:
            # 504 Timeout simulated response validation
            assert json_response.get("status") == "error"
            assert "timeout" in json_response.get("message", "").lower()

    except requests.Timeout:
        assert False, "Request timed out unexpectedly"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

test_get_3d_visualization_trend_success()