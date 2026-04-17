import os
import requests
import datetime

# .env 직접 읽기
env = {}
if os.path.exists('.env'):
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                parts = line.strip().split('=', 1)
                if len(parts) == 2:
                    env[parts[0].strip()] = parts[1].strip().strip('"').strip("'")

N_ID = env.get('NAVER_CLIENT_ID')
N_SECRET = env.get('NAVER_CLIENT_SECRET')

def get_fashion_category_data():
    print("--- [Verification Sync] Fashion Category Analysis (Final) ---")
    
    headers = {
        "X-Naver-Client-Id": N_ID,
        "X-Naver-Client-Secret": N_SECRET,
        "Content-Type": "application/json"
    }
    
    target_day = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    
    body = {
        "startDate": target_day,
        "endDate": target_day,
        "timeUnit": "date",
        "category": [
            {"name": "Female Fashion", "param": ["50000167"]},
            {"name": "Male Fashion", "param": ["50000169"]},
            {"name": "Shoes", "param": ["50000173"]}
        ],
        "device": "", "gender": "", "ages": []
    }
    
    res = requests.post("https://openapi.naver.com/v1/datalab/shopping/categories", headers=headers, json=body)
    
    if res.status_code == 200:
        data = res.json()
        print(f"SUCCESS: Found data for {target_day}")
        
        results = []
        for res_item in data.get('results', []):
            name = res_item['title']
            # 'value' 대신 'ratio' 사용
            val = res_item['data'][0]['ratio'] if res_item['data'] else 0
            results.append({"name": name, "value": val})
            
        results.sort(key=lambda x: x['value'], reverse=True)
        
        print(f"\n[RANKING LIST - FASHION ({target_day})]")
        print("-" * 50)
        print(f"{'Rank':<5} | {'Category Name':<20} | {'Click Ratio(%)':<15}")
        print("-" * 50)
        for i, item in enumerate(results):
            print(f"{i+1:<5} | {item['name']:<20} | {item['value']}%")
        print("-" * 50)
        print("\n✅ 데이터 확인 완료! 아침에 앱분석을 하실 때 위와 같은 순서와 비율로 데이터가 제공됩니다.")
            
    else:
        print(f"FAIL: {res.status_code}")

if __name__ == "__main__":
    get_fashion_category_data()
