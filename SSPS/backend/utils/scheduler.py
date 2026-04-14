import os
import sys
import time
import logging

# 백엔드 모듈 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.connectors.naver_connector import NaverConnector
from backend.connectors.supabase_client import SupabaseClient
from backend.engine.category_manager import NAVER_CATEGORY_TREE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FullSyncBot")

def extract_all_keywords(node, current_list):
    """트리를 순회하며 API 조회용 키워드를 전부 추출합니다."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key not in ["base", "season", "subcategories", "q_keyword"]:
                q_kw = value.get("q_keyword", key) if isinstance(value, dict) else key
                if q_kw not in current_list:
                    current_list.append(q_kw)
            if isinstance(value, dict) and "subcategories" in value:
                extract_all_keywords(value["subcategories"], current_list)

def run_daily_batch():
    """매일 새벽 구동되어 수천 개의 네이버 쇼핑 트리를 DB로 완전 복사(Full-Sync)합니다."""
    logger.info("==== 새벽 자율주행 Full-Sync 크론 봇 시작 ====")
    
    naver = NaverConnector()
    db = SupabaseClient()
    
    # 트리에 존재하는 모든 카테고리 추출
    all_keywords = list(NAVER_CATEGORY_TREE.keys()) # 1차 카테고리
    extract_all_keywords(NAVER_CATEGORY_TREE, all_keywords)
    
    total_nodes = len(all_keywords)
    logger.info(f"발견된 총 카테고리 노드 수: {total_nodes}개")
    logger.info(f"예상 API 호출 횟수: {total_nodes // 5 + 1}회 (안전 기준치 1,000회 미만 통과)")
    
    success_count = 0
    # API 한도를 아끼기 위해 5개 묶음(Chunk)으로 처리
    for i in range(0, total_nodes, 5):
        chunk = all_keywords[i:i+5]
        logger.info(f" -> Fetching Chunk {i//5 + 1}: {chunk}")
        
        try:
            result = naver.fetch_datalab_trend(chunk)
            
            if result and result.get("status") == "OK":
                series_data = result.get("trend_series", {}).get("series", [])
                categories = result.get("trend_series", {}).get("categories", [])
                
                # 5개가 한 번에 왔지만, DB에는 각각의 독자적인 행(Row)으로 저장하여 빠른 개별 조회가 가능케 함
                for item in series_data:
                    kw_name = item["name"]
                    kw_trend = {
                        "categories": categories,
                        "series": [item]
                    }
                    db.upsert_trend_data(kw_name, kw_trend)
                    success_count += 1
                    
        except Exception as e:
            logger.error(f"Chunk 실패: {e}")
            
        time.sleep(2) # 네이버 API 429 Too Many Requests 방지용 쿨다운 (2초)
        
    logger.info(f"==== Full-Sync 완료! 총 {success_count}/{total_nodes} 개 노드 DB 적재 성공 ====")

if __name__ == "__main__":
    run_daily_batch()
