import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_get_collection_history_returns_recent_tasks_list():
    url = f"{BASE_URL}/history"
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request to GET /history failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    assert isinstance(data, list), f"Expected response to be a list, got {type(data)}"

    # Optionally, check if list elements look like recent collection tasks by having keys like 'task_id'
    if len(data) > 0:
        assert isinstance(data[0], dict), "Items in the history list should be dictionaries"
        assert "task_id" in data[0], "Recent task items should contain 'task_id' key"

test_get_collection_history_returns_recent_tasks_list()