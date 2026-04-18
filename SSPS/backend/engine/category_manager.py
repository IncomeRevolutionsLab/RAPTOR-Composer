import random
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# [v2.43] 자동 동기화용 트리거 파일 경로
SYNC_TRIGGER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "pending_sync.json"))

try:
    from dateutil.relativedelta import relativedelta
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

class CategoryManager:
    """N-Depth 네이버 쇼핑 카테고리 트리 관리 및 클릭 트렌드 제공 (DB/JSON 연동 버전)"""

    def __init__(self):
        self.categories_file = os.path.join(os.path.dirname(__file__), "..", "data", "category_master_import.json")
        self.id_to_cat = {}
        self.tree = {}
        self.top_level_categories = []
        self._last_match_is_exact = False
        self._load_categories()

    def _load_categories(self):
        """JSON 데이터로부터 카테고리 체계를 로드하고 트리 구조를 재빌드합니다."""
        if not os.path.exists(self.categories_file):
            logger.error(f"Category data file not found: {self.categories_file}")
            return

        try:
            with open(self.categories_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_cats = data.get("categories", [])
                
                # 1. ID 매핑 구축
                for cat in raw_cats:
                    self.id_to_cat[cat["naver_cat_id"]] = cat
                    cat["subcategories"] = {} # 트리 구성을 위한 초기화

                # 2. 트리 구조 구성
                for cat in raw_cats:
                    pid = cat["parent_id"]
                    if pid is None:
                        self.tree[cat["name_ko"]] = cat
                    elif pid in self.id_to_cat:
                        self.id_to_cat[pid]["subcategories"][cat["name_ko"]] = cat

                self.top_level_categories = list(self.tree.keys())
                logger.info(f"Loaded {len(self.id_to_cat)} categories from JSON.")
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")

    def get_node_by_path(self, path: list) -> dict:
        """N-Depth 경로에 해당하는 카테고리 노드 반환"""
        current = self.tree
        last_node = {}
        
        for i, p in enumerate(path):
            if p in current:
                last_node = current[p]
                current = last_node.get("subcategories", {})
            else:
                return {} # 경로 중간에 끊김
        return last_node

    def get_month_labels(self, n=12):
        now = datetime.now()
        if HAS_DATEUTIL:
            return [(now - relativedelta(months=i)).strftime("%y-%m") for i in range(n-1, -1, -1)]
        labels = []
        year, month = now.year, now.month
        for _ in range(n-1, -1, -1):
            labels.append(f"{str(year)[2:]}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return labels[::-1]

    def get_depth_trend_analysis(self, path: list, naver_connector=None) -> dict:
        """
        [v2.47] 하위 분류들에 대한 트렌드 분석 (멀티 호출로 격차 보존)
        - naver_connector를 직접 전달받아 실시간 그룹 조회를 수행합니다.
        """
        node = self.get_node_by_path(path)
        if not node or not node.get("subcategories"):
            return {}

        subcats = node["subcategories"]
        months = self.get_month_labels(12)
        
        # 분석 대상 카테고리 리스트 작성 (v2.50: 모든 자식 포함)
        all_subcats = []
        for name, info in subcats.items():
            all_subcats.append({
                "name": name,
                "cid": info.get("naver_cat_id")
            })

        if not all_subcats:
            return {}

        # [v2.58] DB 캐시 우선 조회 (Atomic Swap 버전 기준)
        from backend.connectors.supabase_client import SupabaseClient
        db = SupabaseClient()
        active_version = db.get_active_sync_version()
        
        cached_series = []
        missing_any = False
        
        for cat in all_subcats:
            res = db.get_trend_data(cat["name"], sync_version=active_version)
            if res:
                cached_series.append({
                    "name": cat["name"],
                    "data": res["series"][0]["data"],
                    "avg_score": sum(res["series"][0]["data"][-3:]) / 3
                })
            else:
                missing_any = True
                break
        
        if not missing_any and cached_series:
            # [v3.24] 안정적 정렬 적용: 점수가 같으면 이름순으로 고정
            cached_series.sort(key=lambda x: (-x["avg_score"], x["name"]))
            return {
                "is_leaf": False,
                "categories": months,
                "series": [{"name": s["name"], "data": s["data"]} for s in cached_series],
                "ranking": [{"rank": i+1, **s} for i, s in enumerate(cached_series)]
            }

        # 1. 네이버 커넥터가 있고 DB에 데이터가 부족할 때만 실시간 호출 (폴백)
        if naver_connector:
            try:
                logger.info(f"[CategoryManager] {len(all_subcats)}개 카테고리 동적 앵커링 보정 조회 시작")
                
                global_ranking = []
                final_series_data = []
                final_categories = []
                
                group_anchor = None # 동적으로 선정될 브릿지 앵커
                group_anchor_ref_val = None
                
                for i in range(0, len(all_subcats), 4 if group_anchor else 5):
                    time.sleep(0.5) 
                    
                    if group_anchor:
                        current_batch = [group_anchor] + [c for c in all_subcats[i:i+4] if c["cid"] != group_anchor["cid"]]
                    else:
                        current_batch = all_subcats[i:i+5]
                        
                    if not current_batch: continue
                    res = naver_connector.fetch_multi_shopping_trend(current_batch)
                    
                    if res.get("status") == "OK":
                        trend_series = res.get("trend_series", {})
                        batch_series = trend_series.get("series", [])
                        if not final_categories: final_categories = trend_series.get("categories", [])
                        
                        # [Step A] 앵커 선정 또는 기준값 추출
                        if not group_anchor:
                            # 첫 배치에서 가장 높은 녀석을 앵커로 선택
                            best_s_data = max(batch_series, key=lambda s: sum(s["data"][-3:]) / 3 if s["data"] else 0)
                            group_anchor = next(c for c in all_subcats if c["name"] == best_s_data["name"])
                            group_anchor_ref_val = sum(best_s_data["data"][-3:]) / 3
                            scale_factor = 1.0
                        else:
                            # 브릿지 앵커를 통해 보정 계수 산출
                            cur_anchor_series = next((s for s in batch_series if s["name"] == group_anchor["name"]), None)
                            if not cur_anchor_series:
                                scale_factor = 1.0
                            else:
                                cur_anchor_val = sum(cur_anchor_series["data"][-3:]) / 3
                                scale_factor = (group_anchor_ref_val / cur_anchor_val) if cur_anchor_val > 0 else 1.0
                        
                        for s in batch_series:
                            if i > 0 and group_anchor and s["name"] == group_anchor["name"]: continue
                            
                            # 데이터 포인트 보정 (Bridge-Scaling 적용)
                            scaled_points = [round(v * scale_factor, 2) for v in s.get("data", [])]
                            s["data"] = scaled_points 
                            
                            score = round(sum(scaled_points[-3:]) / min(len(scaled_points), 3), 1) if scaled_points else 0
                            global_ranking.append({"name": s["name"], "avg_score": score, "q_keyword": s["name"]})
                            final_series_data.append(s)
                            
                # [v3.24] 전역 랭킹 안정적 정렬 적용
                global_ranking.sort(key=lambda x: (-x["avg_score"], x["name"]))
                
                # 전역 최댓값 100 정규화
                max_score = max([r["avg_score"] for r in global_ranking]) if global_ranking else 100
                if max_score > 0:
                    norm_factor = 100 / max_score
                    for r in global_ranking: r["avg_score"] = round(r["avg_score"] * norm_factor, 1)
                    for s in final_series_data: s["data"] = [round(v * norm_factor, 2) for v in s["data"]]
                
                return {
                    "is_leaf": False,
                    "categories": final_categories or months,
                    "series": final_series_data,
                    "ranking": global_ranking[:12]
                }
            except Exception as e:
                logger.error(f"[CategoryManager] 앵커링 조회 중 오류: {e}")

        # 2. Fallback: 데이터 부재 시 (v2.58: 랜덤 제거, 안정된 기본값 유지)
        all_series = []
        for item in all_subcats:
            base = 50 # 고정값으로 변경하여 호출 시마다 순위가 변하는 현상 차단
            pts = [base for _ in range(12)]
            avg = base
            all_series.append({"name": item["name"], "data": pts, "avg_score": avg, "q_keyword": item["name"]})

        # [v3.24] 폴백 모드에서도 이름순으로 순위 고정
        all_series.sort(key=lambda x: (-x["avg_score"], x["name"]))
        return {
            "is_leaf": False,
            "categories": months,
            "series": [{"name": s["name"], "data": s["data"]} for s in all_series],
            "ranking": [{"rank": i+1, **s} for i, s in enumerate(all_series)]
        }
    def get_month_labels(self, n=12):
        now = datetime.now()
        if HAS_DATEUTIL:
            return [(now - relativedelta(months=i)).strftime("%y-%m") for i in range(n-1, -1, -1)]
        labels = []
        year, month = now.year, now.month
        for _ in range(n-1, -1, -1):
            labels.append(f"{str(year)[2:]}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return labels[::-1]

    def get_path_from_keyword(self, keyword: str, items: list = None) -> list:
        """키워드 기반 카테고리 매칭 (복수 경로 추천 지원)
        Returns: 만약 중복 이름 발견 시 List[List[str]] 형태, 아니면 List[str]
        """
        def normalize(s):
            if not s: return ""
            return "".join(s.lower().split()).replace("-","").replace("/","").replace("_","")

        kw_norm = normalize(keyword)
        possible_paths = []

        # 1. 트리 내 검색 (모든 일치 항목 수집)
        def search_recursive(nodes, current_path):
            for name, node in nodes.items():
                node_norm = normalize(name)
                if kw_norm == node_norm:
                    possible_paths.append(current_path + [name])
                if node.get("subcategories"):
                    search_recursive(node["subcategories"], current_path + [name])

        search_recursive(self.tree, [])

        # 결과에 따른 반환
        if len(possible_paths) > 1:
            # 중의적 결과 발견 (추천 리스트화)
            self._last_match_is_exact = False
            return possible_paths 
        elif len(possible_paths) == 1:
            self._last_match_is_exact = True
            return possible_paths[0]

        # 2. 쇼핑 검색 결과 아이템 기반 추론
        if items:
            cat_counter = {}
            for item in items:
                full = " > ".join([item.get(f"category{i}", "") for i in range(1, 5) if item.get(f"category{i}")])
                if full:
                    cat_counter[full] = cat_counter.get(full, 0) + 1
            if cat_counter:
                best_str = max(cat_counter.items(), key=lambda x: x[1])[0]
                best_path = [n.strip() for n in best_str.split(">")]
                self._last_match_is_exact = False
                return best_path

        self._last_match_is_exact = False
        return ["생활/건강", "생활잡화"]

    def match_from_keyword(self, keyword: str) -> dict:
        result = self.get_path_from_keyword(keyword, [])
        
        # 복수 경로 추천 결과인 경우 처리
        if isinstance(result[0], list):
            paths = result
            main_path = paths[0] # 일단 첫 번째 선택
            is_ambiguous = True
        else:
            main_path = result
            paths = [result]
            is_ambiguous = False

        node = self.get_node_by_path(main_path)
        is_leaf = not bool(node.get("subcategories"))

        return {
            "depth1": main_path[0] if len(main_path) > 0 else None,
            "depth2": main_path[1] if len(main_path) > 1 else None,
            "depth3": main_path[2] if len(main_path) > 2 else None,
            "depth4": main_path[3] if len(main_path) > 3 else None,
            "has_subcat": not is_leaf,
            "is_leaf_category": is_leaf,
            "is_ambiguous": is_ambiguous,
            "all_paths": paths # 추천 리스트용 데이터
        }

    def _track_category_drift(self, full_path_str: str, items: list = None):
        """[v2.43] 미등록 카테고리 감지 시 로그 기록 및 자동 동기화 트리거"""
        try:
            pending = {}
            if os.path.exists(SYNC_TRIGGER_PATH):
                with open(SYNC_TRIGGER_PATH, "r", encoding="utf-8") as f:
                    pending = json.load(f)
            
            if full_path_str not in pending:
                pending[full_path_str] = {
                    "detected_at": datetime.now().isoformat(),
                    "status": "pending",
                    "sample_item_count": len(items) if items else 0
                }
                with open(SYNC_TRIGGER_PATH, "w", encoding="utf-8") as f:
                    json.dump(pending, f, ensure_ascii=False, indent=2)
                logger.info(f"Category Drift Detected: {full_path_str}. Sync triggered.")
        except Exception as e:
            logger.error(f"Failed to track category drift: {e}")
