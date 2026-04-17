import os
import sys
import time
import logging
import json
from datetime import datetime, timedelta

# 백엔드 모듈 및 사용자 패키지 경로 추가
import site
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
if hasattr(site, 'getusersitepackages'):
    sys.path.append(site.getusersitepackages())

from backend.connectors.naver_connector import NaverConnector
from backend.connectors.supabase_client import SupabaseClient
from backend.engine.category_manager import CategoryManager
from backend.utils.notifier import send_telegram_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TrendCollector")

class TrendCollector:
    """네이버 쇼핑인사이트 API를 활용하여 카테고리별 트렌드를 수집하고 DB에 적재하는 엔진"""

    def __init__(self):
        self.naver = NaverConnector()
        self.db = SupabaseClient()
        self.manager = CategoryManager()
        self.daily_limit = 1000 # 네이버 API 일일 제한
        
        # [v2.65] 2일 주기 Atomic Swap을 위한 버전 관리
        self.active_version = self.db.get_active_sync_version()
        self.pending_version = "v_beta" if self.active_version == "v_alpha" else "v_alpha"
        self.batch_name = datetime.now().strftime("%Y-%m-%d")
        logger.info(f" -> 현재 활성 버전: {self.active_version}, 대기 수집 버전: {self.pending_version}")

    def check_health(self) -> bool:
        """[v2.80] 본격 수집 전 시스템 상태를 1회 테스트합니다. (Dry-Run)"""
        logger.info(" -> [HealthCheck] 사전 시스템 가동 테스트 시작...")
        
        # [v2.81] 현재 데이터셋에서 검증된 패션의류 ID 사용
        test_category = {"name": "패션의류", "cid": "1960718588"}
        
        try:
            # 1. Naver API 테스트
            res = self.naver.fetch_multi_shopping_trend([test_category])
            if res.get("status") != "OK":
                reason = res.get('reason', '알 수 없는 이유')
                error_msg = f"❌ [HealthCheck] 네이버 API 호출 실패: {reason}"
                logger.error(error_msg)
                send_telegram_message(error_msg)
                return False
                
            # 2. Supabase DB 테스트
            test_save = self.db.upsert_raw_trend_data("system/health_check", res.get("trend_series"), sync_version="test")
            if not test_save:
                error_msg = "❌ [HealthCheck] Supabase DB 저장 실패 (자격 증명 또는 테이블 확인 필요)"
                logger.error(error_msg)
                send_telegram_message(error_msg)
                return False
                
            logger.info(" -> [HealthCheck] 모든 시스템(Naver & Supabase) 정상 작동 확인되었습니다.")
            return True
        except Exception as e:
            error_msg = f"❌ [HealthCheck] 시스템 연동 중 치명적 오류: {str(e)[:100]}"
            logger.error(error_msg)
            send_telegram_message(error_msg)
            return False

    def run_sync(self):
        """[v2.50] 부모별로 묶어 기준점(Anchor) 기반 전역 정합성 수집"""
        
        # [Step 0] 사전 헬스체크
        if not self.check_health():
            logger.error(" !! 사전 테스트 실패로 수집을 중단합니다. !!")
            return
            
        send_telegram_message(f"🚀 [{self.batch_name}] 데이터 수집 작업을 시작합니다. (대상: {self.pending_version})")
        logger.info(f"==== [{self.batch_name}] 앵커링 기반 트렌드 수집 시작 ====")
        
        # 1. 수집 대상 추출 및 부모별 그룹화
        all_cats = list(self.manager.id_to_cat.values())
        groups = {}
        for c in all_cats:
            if len(str(c["naver_cat_id"])) > 10: continue # 유효한 네이버 ID만 선별
            pid = c.get("parent_id")
            if pid not in groups: groups[pid] = []
            groups[pid].append(c)
            
        # 2. 대기 버전에 이미 수집된 키워드 제외 (2일차 수집 시 중복 방지)
        existing_keywords = self.db.get_all_keywords_by_version(self.pending_version)
        logger.info(f" -> 대기 버전({self.pending_version}) 내 이미 수집된 데이터: {len(existing_keywords)}개")
            
        processed_groups = 0
        total_calls = 0
        newly_collected_count = 0
        
        # 3. 각 그룹(형제들)별로 앵커링 수집 수행
        for pid, siblings in groups.items():
            # API 한도 도달 시 중단 (다음 날 나머지 수집 가능)
            if total_calls >= self.daily_limit:
                logger.info(f" !! 일일 API 호출 한도({self.daily_limit})에 도달하여 오늘 작업을 중단합니다.")
                break
                
            # 이미 이 그룹의 모든 자식이 수집되었는지 확인 (Full Path 기준)
            # 모든 자식이 existing_keywords에 있다면 이 그룹은 스킵
            if all(s.get("full_path") in existing_keywords for s in siblings):
                continue
                
            parent_name = self.manager.id_to_cat.get(pid, {}).get("name_ko", "Root")
            logger.info(f"--- 그룹 수집: {parent_name} (자식 {len(siblings)}개) ---")
            
            # 4. [v2.70] 동적 자식 앵커(Dynamic Sibling Anchor) 전략
            # [v3.1] 지능형 그룹화: 카테고리 명칭을 분석하여 성격이 유사한 것끼리 우선 묶음
            siblings = sorted(siblings, key=lambda x: x.get('name_ko', ''))
            
            group_anchor = None
            group_anchor_ref_val = None # 첫 배치에서의 앵커 평균치 (Reference)
            
            # [v2.87] 네이버 규정(최대 3개) 준수형 배치 전략
            for i in range(0, len(siblings), 3):
                if group_anchor:
                    # 이후 배치: 브릿지 앵커 + 신규 자식 2개 (총 3개)
                    batch = [group_anchor] + [s for s in siblings[i:i+2] if s["naver_cat_id"] != group_anchor["naver_cat_id"]]
                else:
                    # 첫 배치: 순서대로 3개
                    batch = siblings[i:i+3]
                
                if not batch: continue
                
                # [v2.86] 데이터 정밀화: 특수문자 제거 및 ID 유효성 확보
                category_list = []
                for s in batch:
                    clean_name = s["name_ko"].replace("/", " ").replace("&", " ").strip()
                    category_list.append({"name": clean_name, "cid": str(s["naver_cat_id"])})
                
                try:
                    res = self.naver.fetch_multi_shopping_trend(category_list)
                    total_calls += 1
                    
                    if res.get("status") == "OK":
                        trend_series = res.get("trend_series", {})
                        series_data = trend_series.get("series", [])
                        
                        # [Step Raw] v2.75 원본 데이터 무조건 별도 보관 (교체 방식)
                        for s_raw in series_data:
                            target_cat_raw = next((c for c in siblings if c["name_ko"] == s_raw["name"]), None)
                            storage_key_raw = target_cat_raw["full_path"] if target_cat_raw else s_raw["name"]
                            self.db.upsert_raw_trend_data(storage_key_raw, {"categories": trend_series["categories"], "series": [s_raw]})
                        
                        # [Step A] 첫 배치인 경우: 가장 높은 자식을 앵커로 선정
                        if not group_anchor:
                            # 3개월 평균 클릭량이 가장 높은 녀석 탐색
                            best_series = max(series_data, key=lambda s: sum(s["data"][-3:]) / 3 if s["data"] else 0)
                            group_anchor = next(s for s in siblings if s["name_ko"] == best_series["name"])
                            group_anchor_ref_val = sum(best_series["data"][-3:]) / 3
                            logger.info(f"    -> 그룹 앵커 선정: {group_anchor['name_ko']} (Ref: {group_anchor_ref_val:.1f})")
                            
                            # 첫 배치는 보정 없이 그대로 저장
                            scale_factor = 1.0
                        else:
                            # [Step B] 이후 배치인 경우: 브릿지 앵커를 기준으로 보정
                            cur_anchor_series = next((s for s in series_data if s["name"] == group_anchor["name_ko"]), None)
                            if not cur_anchor_series:
                                scale_factor = 1.0
                            else:
                                cur_anchor_val = sum(cur_anchor_series["data"][-3:]) / 3
                                scale_factor = (group_anchor_ref_val / cur_anchor_val) if cur_anchor_val > 0 else 1.0
                        
                        # [Step C] 데이터 보정 및 저장
                        for s in series_data:
                            # 앵커 이미 저장되었고 이후 배치에서 중복되는 경우 스키마상 중복 저장 방지 (선택 사항)
                            if i > 0 and group_anchor and s["name"] == group_anchor["name_ko"]: continue
                            
                            scaled_data = [round(v * scale_factor, 2) for v in s.get("data", [])]
                            s["data"] = scaled_data
                            
                            target_cat = next((c for c in siblings if c["name_ko"] == s["name"]), None)
                            storage_key = target_cat["full_path"] if target_cat else s["name"]
                            self.db.upsert_trend_data(storage_key, {"categories": trend_series["categories"], "series": [s]}, sync_version=self.pending_version)
                            newly_collected_count += 1
                            
                        logger.info(f"  -> 배치 {i//4 + 1} 수집 완료 (Scale: {scale_factor:.2f})")
                    else:
                        logger.warning(f"  -> 호출 실패: {res.get('reason')}")
                
                except Exception as e:
                    logger.error(f"  -> 에러 발생: {e}")
                
                time.sleep(0.5) # 호출 간격 최적화
            
            processed_groups += 1

        logger.info(f"==== 수집 완료! 신규 수집: {newly_collected_count}, 총 API 호출: {total_calls} ====")
        
        # 4. 전체 수집 완료 확인 및 Atomic Swap
        total_target = len([c for c in all_cats if len(str(c["naver_cat_id"])) <= 10]) # 유효 카테고리 총합 (실제로는 약 5,807개)
        current_total = self.db.get_version_keywords_count(self.pending_version)
        
        logger.info(f" -> 전체 진행률 확인: {current_total} / {total_target} (목표)")
        
        if current_total >= total_target * 0.98: # 98% 이상 수집 시 전체 데이터 정합성이 확보된 것으로 간주
            logger.info(f"!!!! [Atomic Swap] 데이터 수집이 완료되어 {self.pending_version}으로 활성 버전을 교체합니다. !!!!")
            self.db.set_active_sync_version(self.pending_version)
            send_telegram_message(f"✅ [{self.batch_name}] 전체 수집 및 버전 교체(Atomic Swap) 완료! ({current_total}/{total_target})")
        else:
            remaining = total_target - current_total
            logger.info(f" -> 아직 {remaining}개의 데이터가 더 필요합니다. 내일 수집을 계속합니다.")
            send_telegram_message(f"⌛ [{self.batch_name}] 오늘 분량 수집 완료. (현재 진행률: {current_total}/{total_target})")

if __name__ == "__main__":
    collector = TrendCollector()
    collector.run_sync()
