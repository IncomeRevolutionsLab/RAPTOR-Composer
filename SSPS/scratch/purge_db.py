import os
from supabase import create_client
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

def purge_all():
    if not (url and key):
        print("No Supabase credentials found.")
        return

    try:
        supabase = create_client(url, key)
        
        # 1. 트렌드 캐시 전체 삭제
        print("Purging 'trend_cache' table...")
        # eq('id', 0).neq('id', 0) 식의 꼼수 없이 데이터 삭제가 가능한지 확인
        # Supabase Python SDK에서 전체 삭제는 보통 range나 filter를 사용
        # 여기서는 모든 실데이터를 날리기 위해 gte('id', 0) 등 사용 (id가 PK인 경우)
        res_cache = supabase.table('trend_cache').delete().neq('query_keyword', '___DUMMY_KEYWORD___').execute()
        print(f"Trend Cache Purged. Rows affected: {len(res_cache.data) if res_cache.data else 0}")

        # 2. 통계 초기화
        print("Resetting 'site_stats' table...")
        reset_data = {
            "id": 1, 
            "total_analysis": 0, 
            "top_domain": "패션의류", 
            "top_domain_desc": "(수집 대기 중)"
        }
        res_stats = supabase.table('site_stats').upsert(reset_data).execute()
        print("Site Stats Reset Successful.")
        
    except Exception as e:
        print(f"Error during Purge: {e}")

if __name__ == "__main__":
    purge_all()
