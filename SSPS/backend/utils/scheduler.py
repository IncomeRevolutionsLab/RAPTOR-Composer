import os
import sys
import time
import logging
from datetime import datetime, timedelta
from collections import Counter

# 백엔드 모듈 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.connectors.naver_connector import NaverConnector
from backend.connectors.supabase_client import SupabaseClient
from backend.engine.category_manager import CategoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FullSyncBot")

def run_daily_batch():
    """매일 새벽 구동되어 데이터 일관성을 보장하며 전체 동기화 및 인기 검색어 통계를 산출합니다."""
    logger.info("==== [v2.58] 데이터 무결성 Full-Sync 크론 봇 시작 ====")
    
    naver = NaverConnector()
    db = SupabaseClient()
    cat_mgr = CategoryManager()
    
    # 1. 신규 수집 버전 생성 (Atomic Swap용)
    new_version = datetime.now().strftime("v%Y%m%d_%H%M")
    logger.info(f" -> 수집 버전 생성: {new_version} (Staging 시작)")

    # 2. 인기 검색어 수집 및 주간 통계 산출
    logger.info(" -> [Step 1] 도메인별 인기 검색어 수집 및 통계 산출")
    domains = cat_mgr.top_level_categories
    for domain in domains:
        try:
            # CID 찾기
            node = cat_mgr.tree.get(domain)
            if not node: continue
            cid = node.get("naver_cat_id")
            
            # API 호출 (1-10위)
            res = naver.fetch_category_keyword_ranking(cid)
            if res.get("status") == "OK":
                db.save_daily_keyword_ranking(domain, res["keywords"])
                logger.info(f"    - {domain} 인기 검색어 수집 완료")
                
                # 주간 통계 산출 (최근 7일 빈도 분석 및 Stable 테이블 갱신)
                db.refresh_weekly_stable_keywords(domain)
        except Exception as e:
            logger.error(f"    - {domain} 수집 실패: {e}")

    # 3. 전체 카테고리 클릭 트렌드 수집 (Batch-5 & Anchoring 적용)
    logger.info(" -> [Step 2] 전체 카테고리 클릭 트렌드 수집 (2일 주기 Staging)")
    try:
        from scripts.trend_collector import TrendCollector
        collector = TrendCollector()
        collector.run_sync() # 내부적으로 2일 누적 및 Atomic Swap 수행
    except Exception as e:
        logger.error(f"Category Trend Sync 실패: {e}")

    logger.info("==== [Success] 데일리 배치 작업이 완료되었습니다. ====")

if __name__ == "__main__":
    run_daily_batch()
