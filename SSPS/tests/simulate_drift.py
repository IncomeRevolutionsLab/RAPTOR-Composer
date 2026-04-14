import json
import os

def simulate_drift():
    PENDING_FILE = r"C:\Antigravity Work\backend\data\pending_sync.json"
    drift_data = {
        "신규분야 > 테스트카테고리 > 최하위분류": {
            "detected_at": "2026-04-13T19:44:00",
            "status": "pending",
            "sample_item_count": 5
        }
    }
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(drift_data, f, ensure_ascii=False, indent=2)
    print("Simulated drift trigger created.")

if __name__ == "__main__":
    simulate_drift()
