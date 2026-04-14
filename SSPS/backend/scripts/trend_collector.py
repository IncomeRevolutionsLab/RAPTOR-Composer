import os
import sys
import time
import logging
import json
from datetime import datetime, timedelta

# 백엔드 모듈 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.connectors.naver_connector import NaverConnector
from backend.connectors.supabase_client import SupabaseClient
from backend.engine.category_manager import CategoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TrendCollector")

class TrendCollector:
    """네이버 쇼핑인사이트 API를 활용하여 카테고리별 트렌드를 수집하고 DB에 적재하는 엔진"""

    def __init__(self):
        self.naver = NaverConnector()
        self.db = SupabaseClient()
        self.manager = CategoryManager()
        self.daily_limit = 1000
        self.batch_name = f"Batch_{datetime.now().strftime('%Y%m%d')}"

    def run_sync(self):
        """가장 오래된 데이터부터 순차적으로 수집 (2일 주기를 목표)"""
        logger.info(f"==== [{self.batch_name}] 카테고리 트렌드 수집 시작 ====")
        
        # 1. 수집 대상 추출 (모든 카테고리 중 naver_cat_id가 실제 네이버 ID인 것들)
        all_cats = list(self.manager.id_to_cat.values())
        
        # [v2.5] 수집 우선순위: Depth가 낮을수록(대분류) 우선, 그 다음은 업데이트가 오래된 순
        # naver_cat_id가 8자리 이하인 것들이 보통 실제 네이버 ID임 (해시 ID는 10자리 이상)
        sync_targets = [c for c in all_cats if len(str(c["naver_cat_id"])) <= 10]
        
        # 실시간 데이터베이스에서 마지막 업데이트 일자 확인 후 정렬 (Mocking for now if DB not fully synced)
        # TODO: self.db.get_oldest_trend_categories(limit=1000)
        
        processed_count = 0
        success_count = 0
        
        for cat in sync_targets:
            if processed_count >= self.daily_limit:
                logger.info("일일 API 호출 한도(1,000회)에 도달했습니다. 작업을 종료합니다.")
                break
            
            cid = cat["naver_cat_id"]
            name = cat["name_ko"]
            path = cat["full_path"]
            
            # [Optimization] 이미 오늘 업데이트된 내역이면 건너뜀 (DB 조회 필요)
            # 여기서는 단순 순차 수집 시뮬레이션
            
            logger.info(f"[{processed_count+1}/{self.daily_limit}] 수집 중: {path} (CID: {cid})")
            
            try:
                result = self.naver.fetch_shopping_trend_by_cid(cid, name)
                
                if result.get("status") == "OK":
                    trend_data = result.get("trend_series")
                    # query_keyword 대신 'cid:1234' 혹은 'Name'으로 저장
                    # CategoryManager와 호환되도록 name_ko를 키로 사용하되 중복 주의
                    # 실제 프로젝트에서는 cid를 키로 하거나 'Path'를 키로 하는 것이 안전
                    storage_key = path 
                    self.db.upsert_trend_data(storage_key, trend_data)
                    success_count += 1
                else:
                    logger.warning(f"  -> 수집 실패: {result.get('reason')}")
                    
            except Exception as e:
                logger.error(f"  -> 에러 발생 ({name}): {e}")
            
            processed_count += 1
            time.sleep(1.0) # 안전한 호출 간격 (1초)

        logger.info(f"==== 수집 완료! 성공: {success_count}, 총 시도: {processed_count} ====")

if __name__ == "__main__":
    collector = TrendCollector()
    collector.run_sync()
