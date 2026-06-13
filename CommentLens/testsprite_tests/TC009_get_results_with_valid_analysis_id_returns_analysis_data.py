import requests
import time

BASE_URL = "http://localhost:8000"
TIMEOUT = 30


def test_get_results_with_valid_analysis_id_returns_analysis_data():
    # Step 1: Start an analysis to get a valid analysis_id
    analyze_url = f"{BASE_URL}/analyze"
    video_id = "dQw4w9WgXcQ"  # Known valid video id for testing
    payload = {
        "video_id": video_id,
        "options": {"nlp_only": True}
    }

    analysis_id = None
    try:
        resp = requests.post(analyze_url, json=payload, timeout=TIMEOUT)
        assert resp.status_code == 202, f"Expected 202 Accepted, got {resp.status_code}"
        resp_json = resp.json()
        assert "analysis_id" in resp_json, "Response missing analysis_id"
        analysis_id = resp_json["analysis_id"]

        # Step 2: Poll /results until analysis completes or timeout after ~2 minutes
        results_url = f"{BASE_URL}/results"
        start_time = time.time()
        while True:
            resp_results = requests.get(results_url, params={"analysis_id": analysis_id}, timeout=TIMEOUT)
            if resp_results.status_code == 200:
                result_json = resp_results.json()
                # Check expected keys presence
                assert "sentiment_stats" in result_json or "local_nlp" in result_json, "Missing sentiment statistics"
                # Topic clusters could be under "topic_clusters" or "local_nlp"."topics"
                if "topic_clusters" in result_json:
                    assert isinstance(result_json["topic_clusters"], (list, dict)), "topic_clusters is not list or dict"
                elif "local_nlp" in result_json and "topics" in result_json["local_nlp"]:
                    assert isinstance(result_json["local_nlp"]["topics"], list), "local_nlp.topics is not a list"
                else:
                    # At least one topic clusters field should be present
                    assert False, "Missing topic clusters data"
                assert "anonymization_report" in result_json, "Missing anonymization_report"
                # llm_summary is optional, can be null or string
                assert "llm_summary" in result_json, "Missing llm_summary key"
                break
            elif resp_results.status_code in (202, 204):
                # Analysis still running or no content yet, wait and retry
                if time.time() - start_time > 120:
                    assert False, "Timeout waiting for analysis results"
                time.sleep(5)
            else:
                # Unexpected error
                assert False, f"Unexpected status code from /results: {resp_results.status_code} {resp_results.text}"
    finally:
        # Cleanup not required for this test since analysis data is needed. If an endpoint existed to delete analysis, it would be called here.
        pass


test_get_results_with_valid_analysis_id_returns_analysis_data()