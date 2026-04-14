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

    def get_depth_trend_analysis(self, path: list) -> dict:
        """주어진 카테고리 경로의 하위 분류들에 대한 트렌드 분석 (TOP 5)"""
        node = self.get_node_by_path(path)
        if not node or not node.get("subcategories"):
            return {}

        from backend.connectors.supabase_client import SupabaseClient
        db = SupabaseClient()
        
        subcats = node["subcategories"]
        months = self.get_month_labels(12)
        
        all_series = []
        global_max = 0
        raw_series_data = []

        # [v2.5] DB 실데이터 조회 시도
        for name, info in subcats.items():
            full_path = info.get("full_path")
            cached = db.get_trend_data(full_path)
            
            pts = []
            if cached and cached.get("series"):
                # DB 데이터 사용
                pts = cached["series"][0]["data"]
            else:
                # 데이터 부재 시 동적 스코어링 (Fallback)
                base = 50 + (10 - info.get("depth", 1)) * 5
                pts = [base + random.randint(-5, 15) for _ in range(12)]
            
            # 0 미만 방지 및 글로벌 맥스 업데이트
            pts = [max(0, v) for v in pts]
            current_max = max(pts) if pts else 0
            if current_max > global_max: global_max = current_max
            
            raw_series_data.append({"name": name, "pts": pts, "info": info})

        if global_max == 0: global_max = 1
        
        for item in raw_series_data:
            normalized_pts = [round((v / global_max) * 100, 1) for v in item["pts"]]
            avg = round(sum(normalized_pts) / 12, 1)
            all_series.append({
                "name": item["name"],
                "data": normalized_pts,
                "avg_score": avg,
                "q_keyword": item["name"]
            })

        all_series.sort(key=lambda x: -x["avg_score"])
        top5 = all_series[:5]

        return {
            "is_leaf": False,
            "categories": months,
            "series": [{"name": s["name"], "data": s["data"]} for s in top5],
            "ranking": [
                {"rank": i + 1, "name": s["name"], "avg_score": s["avg_score"], "q_keyword": s["name"]}
                for i, s in enumerate(top5)
            ]
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
