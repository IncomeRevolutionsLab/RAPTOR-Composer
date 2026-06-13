import requests
import time

BASE_URL = "http://localhost:8000"
ANALYZE_ENDPOINT = "/analysis/analyze"
RESULTS_ENDPOINT = "/analysis/results"
TIMEOUT = 30

def test_post_analysis_sna_mode():
    # Since no video_id is provided, create a dummy collection task for a valid video_id
    # to be used in SNA analysis. We pick a known test video_id.
    test_video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up (as a stable example)
    job_id = None
    try:
        # Step 1: POST to /analysis/analyze with mode 'sna' and compute_network true
        payload = {
            "mode": "sna",
            "video_ids": [test_video_id],
            "compute_network": True
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(
            f"{BASE_URL}{ANALYZE_ENDPOINT}",
            json=payload,
            headers=headers,
            timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "job_id" in data, "Response JSON missing 'job_id'"
        assert data.get("status") == "sna_running", f"Expected status 'sna_running', got {data.get('status')}"
        job_id = data["job_id"]

        # Step 2: Poll GET /analysis/results?job_id=<job_id> until results are ready (max wait ~90s)
        result_url = f"{BASE_URL}{RESULTS_ENDPOINT}"
        for _ in range(18):
            result_resp = requests.get(
                result_url,
                params={"job_id": job_id},
                timeout=TIMEOUT
            )
            if result_resp.status_code == 200:
                result_data = result_resp.json()
                # Validate presence of network_map (with nodes and edges), cluster_metrics, and distortion_alerts
                assert "network_map" in result_data, "Result missing 'network_map'"
                network_map = result_data["network_map"]
                assert isinstance(network_map.get("nodes"), list), "'nodes' in network_map should be a list"
                assert isinstance(network_map.get("edges"), list), "'edges' in network_map should be a list"
                assert "cluster_metrics" in result_data, "Result missing 'cluster_metrics'"
                assert "distortion_alerts" in result_data, "Result missing 'distortion_alerts'"
                break
            elif result_resp.status_code == 202:
                # Analysis in progress, wait and retry
                time.sleep(5)
            else:
                assert False, f"Unexpected status code {result_resp.status_code} from results: {result_resp.text}"
        else:
            assert False, "Timeout waiting for SNA analysis results"

    finally:
        # No resource creation endpoint for analysis jobs specified, so no cleanup is performed.
        pass

test_post_analysis_sna_mode()