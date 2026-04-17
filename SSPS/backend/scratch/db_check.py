import os
import sys
import json

# 프로젝트 루트를 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, root_dir)

from backend.connectors.supabase_client import SupabaseClient

def test_connection():
    # 윈도우 인코딩 문제 방지를 위해 print 대신 직접 출력 제어
    def log(msg):
        print(msg.encode('utf-8', 'ignore').decode('utf-8'))

    log("=== Supabase Connection Test Start ===")
    try:
        db = SupabaseClient()
        # db_available 여부와 상관없이 직접 테이블 조회 시도
        if db.client:
            try:
                res = db.client.table('site_stats').select('total_analysis').eq('id', 1).execute()
                if res.data:
                    log(f"SUCCESS: Connected. Analysis Count: {res.data[0].get('total_analysis')}")
                else:
                    log("CONNECTED: But no data in site_stats.")
                
                # 원본 데이터 테이블 존재 여부 확인
                try:
                    db.client.table('trend_raw').select('id').limit(1).execute()
                    log("SUCCESS: trend_raw table is ready.")
                except Exception as e:
                    log(f"WARNING: trend_raw table check failed: {str(e)[:50]}")
            except Exception as e:
                log(f"FAILURE: Data query failed. Maybe project is still waking up or Key issue: {str(e)[:100]}")
        else:
            log("FAILURE: Supabase client could not be initialized.")
    except Exception as e:
        log(f"ERROR: {str(e)}")

if __name__ == "__main__":
    test_connection()
