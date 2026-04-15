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
        """[v2.50] 부모별로 묶어 기준점(Anchor) 기반 전역 정합성 수집"""
        logger.info(f"==== [{self.batch_name}] 앵커링 기반 트렌드 수집 시작 ====")
        
        # 1. 수집 대상 추출 및 부모별 그룹화
        all_cats = list(self.manager.id_to_cat.values())
        groups = {}
        for c in all_cats:
            if len(str(c["naver_cat_id"])) > 10: continue # 유효한 네이버 ID만 선별
            pid = c.get("parent_id")
            if pid not in groups: groups[pid] = []
            groups[pid].append(c)
            
        processed_groups = 0
        total_calls = 0
        
        # 2. 각 그룹(형제들)별로 앵커링 수집 수행
        for pid, siblings in groups.items():
            if processed_groups >= self.daily_limit / 2: # 그룹당 평균 2회 호출 가정
                break
                
            parent_name = self.manager.id_to_cat.get(pid, {}).get("name_ko", "Root")
            logger.info(f"--- 그룹 수집: {parent_name} (자식 {len(siblings)}개) ---")
            
            # 기준점(Anchor) 선정: 첫 번째 자식
            anchor = siblings[0]
            
            # 4개씩 묶어서 배치 처리
            for i in range(0, len(siblings), 4):
                batch = [anchor] + [s for s in siblings[i:i+4] if s["naver_cat_id"] != anchor["naver_cat_id"]]
                if len(batch) == 1 and i > 0: continue
                
                category_list = [{"name": s["name_ko"], "cid": s["naver_cat_id"]} for s in batch]
                
                try:
                    res = self.naver.fetch_multi_shopping_trend(category_list)
                    total_calls += 1
                    
                    if res.get("status") == "OK":
                        trend_series = res.get("trend_series", {})
                        series_data = trend_series.get("series", [])
                        
                        # 이 배치에서의 Anchor 점수 확인 (보정 계수 산출)
                        anchor_series = next((s for s in series_data if s["name"] == anchor["name_ko"]), None)
                        if not anchor_series: continue
                        
                        # 실제 저장 로직: 각 카테고리의 트렌드 데이터를 DB에 업서트
                        # (v2.50: 전역 보정은 조회 시 수행하거나 저장 시 가중치를 둘 수 있음)
                        for s in series_data:
                            # 67: storage_key = f"{pid}_{s['name']}" # 중복 방지를 위해 PID와 조합
                            # 기존 CategoryManager 호환을 위해 Full Path 조회 시도
                            target_cat = next((c for c in siblings if c["name_ko"] == s["name"]), None)
                            storage_key = target_cat["full_path"] if target_cat else s["name"]
                            
                            self.db.upsert_trend_data(storage_key, {"categories": trend_series["categories"], "series": [s]})
                            
                        logger.info(f"  -> 배치 {i//4 + 1} 수집 완료 ({len(series_data)}개)")
                    else:
                        logger.warning(f"  -> 호출 실패: {res.get('reason')}")
                
                except Exception as e:
                    logger.error(f"  -> 에러 발생: {e}")
                
                time.sleep(0.5) # 호출 간격 최적화
            
            processed_groups += 1

        logger.info(f"==== 수집 완료! 총 API 호출: {total_calls}, 처리된 그룹: {processed_groups} ====")

if __name__ == "__main__":
    collector = TrendCollector()
    collector.run_sync()
