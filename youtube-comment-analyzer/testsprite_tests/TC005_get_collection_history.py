import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_get_collection_history():
    url = f"{BASE_URL}/history"
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request to {url} failed: {e}"
    
    assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"
    
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"
    
    assert isinstance(data, list), f"Expected a list but got {type(data)}"
    
    # If data is empty list, no entries yet, otherwise check structure of entries
    if data:
        sample_entry = data[0]
        assert isinstance(sample_entry, dict), "Each history entry should be a dictionary"
        assert "task_id" in sample_entry, "History entry missing 'task_id'"
        assert "collected_comments_count" in sample_entry or "collected_count" in sample_entry, \
            "History entry missing collected comment count field"

test_get_collection_history()