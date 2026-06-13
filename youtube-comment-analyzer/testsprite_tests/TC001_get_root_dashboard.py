import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_get_root_dashboard():
    url = f"{BASE_URL}/"
    try:
        response = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed with exception: {e}"

    assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"

    content_type = response.headers.get("Content-Type", "")
    # Check if Content-Type indicates HTML/JS content
    assert "text/html" in content_type or "application/javascript" in content_type or "text/javascript" in content_type, \
        f"Expected HTML or JS content type but got '{content_type}'"

    content = response.text
    # Basic checks for SPA dashboard HTML/JS presence
    assert "<html" in content.lower(), "Response does not contain HTML content"
    assert ("<script" in content.lower() or "window." in content.lower() or "webpack" in content.lower()), \
        "Response does not appear to contain SPA JavaScript content"

    # Check for route metadata or operator guidance presence (heuristic)
    keywords = ["route", "status", "dashboard", "analysis", "collection"]
    assert any(keyword in content.lower() for keyword in keywords), "Response does not contain expected route metadata or dashboard keywords"

test_get_root_dashboard()