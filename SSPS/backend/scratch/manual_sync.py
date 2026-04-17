import os
import sys
import json
import datetime
import requests

# 1. 인코딩 및 환경 변수 강제 주입
if sys.stdout.encoding != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, root_dir)

env_path = os.path.join(root_dir, '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

# API 정보 추출
N_ID = os.environ.get('NAVER_CLIENT_ID', '').strip()
N_SECRET = os.environ.get('NAVER_CLIENT_SECRET', '').strip()

def run_proper_sync():
    print("=== [Deep Debug Sync Start] ===")
    
    # 패션의류 자식들 정의
    # 여성의류(50000167), 남성의류(50000169), 언더웨어(50000168), 스포츠의류(50000171)
    target_cats = [
        {"name": "Women's Clothing", "id": "50000167"},
        {"name": "Men's Clothing", "id": "50000169"},
        {"name": "Underwear", "id": "50000168"},
        {"name": "Sports Wear", "id": "50000171"}
    ]
    
    target_day = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    
    url = "https://openapi.naver.com/v1/datalab/shopping/categories"
    headers = {
        "X-Naver-Client-Id": N_ID,
        "X-Naver-Client-Secret": N_SECRET,
        "Content-Type": "application/json"
    }
    
    body = {
        "startDate": target_day,
        "endDate": target_day,
        "timeUnit": "date",
        "category": [{"name": c['name'], "param": [c['id']]} for c in target_cats],
        "device": "", "gender": "", "ages": []
    }
    
    print(f"DEBUG: Pinging Naver with Client ID starting with {N_ID[:3]}...")
    res = requests.post(url, headers=headers, json=body)
    
    if res.status_code == 200:
        data = res.json()
        results = []
        for r in data.get('results', []):
            val = r['data'][0]['ratio'] if r.get('data') else 0
            results.append({"name": r['title'], "score": val})
            
        results.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"\n[REAL FASHION RANKING - {target_day}]")
        print("-" * 65)
        print(f"{'순위':<5} | {'카테고리명':<25} | {'상대점수(%)':<15}")
        print("-" * 65)
        for i, item in enumerate(results):
            print(f"{i+1:<5} | {item['name']:<25} | {item['score']}%")
        print("-" * 65)
        print("\n✅ 이 데이터를 기반으로 이제 DB 수집 엔진(70%)을 가동합니다.")
        
        # 실제 엔진 가동
        from backend.scripts.trend_collector import TrendCollector
        collector = TrendCollector()
        collector.run_sync()
        
    else:
        print(f"❌ Naver API Error: {res.status_code}")
        print(f"Response: {res.text}")

if __name__ == "__main__":
    run_proper_sync()
