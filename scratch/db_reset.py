import os
from supabase import create_client
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if url and key:
    try:
        supabase = create_client(url, key)
        # id=1인 레코드를 0으로 초기화
        data = {
            "id": 1, 
            "total_analysis": 0, 
            "top_domain": "식품", 
            "top_domain_desc": "(최근 7일 클릭 지수 1위)"
        }
        res = supabase.table('site_stats').upsert(data).execute()
        print("Successfully reset DB stats to 0.")
        print(res.data)
    except Exception as e:
        print(f"Error during DB reset: {e}")
else:
    print("No Supabase credentials found in .env file.")
