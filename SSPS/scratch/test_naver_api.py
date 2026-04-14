import os
import sys
import json
import requests

# 백엔드 모듈 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.connectors.naver_connector import NaverConnector
from backend.config import settings

def test_naver_api():
    print(f"Testing Naver API...")
    print(f"Client ID: {settings.naver_client_id[:5]}...")
    connector = NaverConnector()
    
    # 1. 테스트용 키워드 트렌드 조회
    print("\n--- Testing DataLab Trend ---")
    try:
        # 직접 호출하여 상세 정보 확인
        headers = connector.get_headers()
        body = {
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
            "timeUnit": "month",
            "keywordGroups": [{"groupName": "테스트", "keywords": ["테스트"]}]
        }
        
        # User's registered address
        registered_url = "https://ssps-engine-git-master-incomerevolutionslab.vercel.app/"
        headers["Referer"] = registered_url
        headers["Origin"] = registered_url
        
        print(f"URL: {connector.datalab_search_url}")
        print(f"Headers: {headers}")
        
        response = requests.post(connector.datalab_search_url, headers=headers, json=body)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code != 200:
            print(f"ERROR: {response.text}")
            
    except Exception as e:
        print(f"Exception during DataLab Trend: {e}")

    # 2. 쇼핑 인사이트 CID 기반 트렌드 조회 (수정된 메소드 검증)
    print("\n--- Testing Shopping Insight (via Connector) ---")
    try:
        cid = "50000000" # 패션의류
        name = "패션의류"
        
        result = connector.fetch_shopping_trend_by_cid(cid, name)
        print(f"Result Status: {result.get('status')}")
        
        if result.get("status") == "OK":
            print("Successfully fetched trend series!")
            print(f"Data points: {len(result['trend_series']['series'][0]['data'])}")
        else:
            print(f"FAILED: {result.get('reason')}")
            
    except Exception as e:
        print(f"Exception during Shopping Insight: {e}")

if __name__ == "__main__":
    test_naver_api()
