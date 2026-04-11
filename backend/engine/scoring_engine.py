import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
from backend.engine.input_router import InputRouter
from backend.engine.weight_allocator import WeightAllocator
from backend.connectors.naver_connector import NaverConnector
from backend.connectors.oliveyoung_scraper import OliveYoungScraper
from backend.connectors.daiso_scraper import DaisoScraper
from backend.connectors.coupang_scraper import CoupangScraper

logger = logging.getLogger(__name__)

class ScoringEngine:
    def __init__(self):
        self.router = InputRouter()
        self.allocator = WeightAllocator()
        
        self.naver = NaverConnector()
        self.oliveyoung = OliveYoungScraper()
        self.daiso = DaisoScraper()
        self.coupang = CoupangScraper()

    def run_pipeline(self, domain: str, manual_olive: str = "", manual_daiso: str = "", fallback_choice: str = "coupang") -> Dict[str, Any]:
        """
        [Hybrid 스플릿 버전] 네이버는 자동 봇 연동, 올리브영/다이소는 각각 수동입력/자동봇 분할 판단
        """
        logger.info(f"[ScoringEngine] 파이프라인 시작: {domain}")
        category_analysis = self.router.analyze(domain)
        cat_type = category_analysis["detected_type"]
        
        # 1. 다이내믹 카테고리 매핑을 위해 Naver Shopping API 먼저 (동기) 호출
        logger.info(f"[ScoringEngine] 네이버 쇼핑 API 선제 호출을 통한 구조 파악 시작")
        try:
            naver_shopping_res = self.naver.fetch_shopping_search(domain)
        except Exception as e:
            logger.error(f"[ScoringEngine] 네이버 쇼핑 선제 호출 실패: {e}")
            naver_shopping_res = {"status": "FAIL", "items": []}
            
        # 2. 졼핑 API 결과가 있으면 실제 카테고리 트리 분석, 없으면 키워드 휴리스틱 폴백
        matched_tree = self.router.cat_mgr.build_hierarchy_from_items(naver_shopping_res.get("items", []), domain)
        category_analysis["matched_hierarchy"] = matched_tree
        
        # [v1.4] 말단 카테고리 여부 확인: 하위 분류가 없는 경우 (API 실데이터 기준)
        is_leaf = matched_tree.get("is_leaf_category", True)
        has_subcat = matched_tree.get("has_subcat", False)
        
        # [NEW] 단어 검색 시 중간 노드(하위 노드가 있는 경우)이면 N-Depth 트렌드 분석으로 리다이렉트
        if has_subcat:
            path = []
            if matched_tree.get("depth1"): path.append(matched_tree["depth1"])
            if matched_tree.get("depth2"): path.append(matched_tree["depth2"])
            if matched_tree.get("depth3"): path.append(matched_tree["depth3"])
            logger.info(f"[ScoringEngine] Redirecting to N-Depth view for path: {path}")
            return {"action": "redirect_to_ndepth", "path": path}
            
        # 말단이면 원본 사용자 입력어로, 아니면 API에서 확인된 depth3 사용
        search_query = domain if is_leaf else (matched_tree.get("depth3") or domain)
        logger.info(f"[ScoringEngine] is_leaf={is_leaf}, search_query={search_query}, depth4={matched_tree.get('depth4_list')}")

        def parse_text(text: str) -> list:
            import re
            items = []
            if not text: return items
            for line in text.split('\n'):
                if len(line.strip()) < 2: continue
                price_match = re.search(r'([\d,]+)\s*원?', line)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    name = re.sub(r'^\d+\.?\s*위?\s*', '', line).replace(price_match.group(0), '').strip()
                    if len(name) > 2 and price_str.isdigit():
                        items.append({
                            "name": name,
                            "price": int(price_str),
                            "rank": len(items) + 1,
                            "image_url": "", "source_url": ""
                        })
                if len(items) >= 10: break # V1.3: 10개까지 확장
            return items
            
        olive_parsed = parse_text(manual_olive)
        daiso_parsed = parse_text(manual_daiso)

        with ThreadPoolExecutor(max_workers=5) as executor:
            # 기존 네이버 쇼핑은 선제 호출했으므로 패스하거나 캐시 이용 (여기서는 생략)
            # [v1.4] leaf이면 기존 도메인으로 DataLab 조회, 아니면 depth4_list 사용
            kw_list = [domain] if is_leaf else matched_tree.get("depth4_list", [domain])
            if not kw_list: kw_list = [domain]
            future_n_data = executor.submit(self.naver.fetch_datalab_trend, kw_list)
            future_coupang = executor.submit(self.coupang.fetch_ranking, search_query)
            
            future_olive = None
            future_daiso = None
            if not olive_parsed: future_olive = executor.submit(self.oliveyoung.fetch_ranking, search_query)
            if not daiso_parsed: future_daiso = executor.submit(self.daiso.fetch_ranking, search_query)

            # naver_shopping_res 는 이미 위에서 동기적으로 선행 호출됨

            try: naver_datalab_res = future_n_data.result()
            except: naver_datalab_res = {"status": "ERROR"}
            
            try: coupang_res = future_coupang.result()
            except: coupang_res = {"status": "ERROR"}
            
            olive_res = {"status": "MANUAL", "items": olive_parsed} if olive_parsed else (
                        future_olive.result() if future_olive else {"status": "ERROR"})
            
            daiso_res = {"status": "MANUAL", "items": daiso_parsed} if daiso_parsed else (
                        future_daiso.result() if future_daiso else {"status": "ERROR"})

        health = {
            "naver_shopping": naver_shopping_res.get("status", "FAIL"),
            "naver_datalab": naver_datalab_res.get("status", "FAIL"),
            "oliveyoung": olive_res.get("status", "FAIL"),
            "daiso": daiso_res.get("status", "FAIL")
        }
        
        healthy_sources = []
        if health["naver_shopping"] in ["OK"]: healthy_sources.append("naver")
        if health["oliveyoung"] in ["OK", "MANUAL"]: healthy_sources.append("oliveyoung")
        if health["daiso"] in ["OK", "MANUAL"]: healthy_sources.append("daiso")
            
        weights = self.allocator.get_weights(cat_type, healthy_sources)
        
        # 주력 데이터 소스
        if not healthy_sources:
            logger.warning("[ScoringEngine] 모든 소스가 실패하여 긴급 Mock Data(Fallback)를 투입합니다.")
            health["mock_fallback"] = "OK"
            healthy_sources.append("mock")
            weights["mock"] = 1.0
            primary_source = "mock"
            primary_signal = "[안내] API 통신 지연으로 인한 대체 데이터 노출 중"
            base_items = []
            for i in range(1, 11):
                base_items.append({
                    "name": f"[{search_query}] 플랫폼 API 응답 대기용 가상 상품 {i}위", 
                    "price": 10000 + (i * 1500), 
                    "rank": i,
                    "image_url": f"https://via.placeholder.com/300?text=Mock+Item+{i}", 
                    "source_url": f"https://www.coupang.com/np/search?q={search_query}"
                })
        else:
            # 원래 카테고리 특성상 의도되었던 주력 소스 도출
            intended_primary = max(self.allocator.base_weights.get(cat_type, self.allocator.base_weights["GENERAL"]).items(), key=lambda x: x[1])[0]
            is_fallback_mode = intended_primary not in healthy_sources
            
            # 현재 남아있는 소스 중 가장 높은 가중치를 가진 소스
            primary_source = max(weights.items(), key=lambda x: x[1])[0]
            
            if is_fallback_mode and fallback_choice == "coupang" and coupang_res.get("status") == "OK":
                primary_source = "coupang"
                primary_signal = "Coupang_Fallback_Boosting"
                base_items = coupang_res.get("items", [])
                logger.info(f"[ScoringEngine] 의도된 소스({intended_primary}) 차단으로 인해 쿠팡(Coupang) 데이터를 우선 노출합니다.")
            else:
                primary_signal = f"{primary_source.capitalize()}_Boosting"
                
                base_items = []
                if primary_source == "oliveyoung": base_items = olive_res.get("items", [])
                elif primary_source == "daiso": base_items = daiso_res.get("items", [])
                else: base_items = naver_shopping_res.get("items", [])
                
                if not base_items: # 1순위 소스에 데이터가 없으면 차순위 병합
                    base_items = naver_shopping_res.get("items", []) + olive_res.get("items", []) + daiso_res.get("items", [])
            
        # 모델 타이틀 정규화
        group_name = f"[{search_query}] 카테고리 심층 통합 분석"
        
        # 점수 정규화 (순수 단일 소스일 경우 85->100점 만점 처리)
        n_w = weights.get("naver", 0.0)
        o_w = weights.get("oliveyoung", 0.0)
        d_w = weights.get("daiso", 0.0)
        tot_w = n_w + o_w + d_w
        
        base_n = 100.0 if (n_w > 0 and tot_w == n_w) else 89.0
        base_o = 100.0 if (o_w > 0 and tot_w == o_w) else 93.0
        base_d = 100.0 if (d_w > 0 and tot_w == d_w) else 78.0
        
        if tot_w > 0:
            final_score = ( (base_n * n_w) + (base_o * o_w) + (base_d * d_w) ) / tot_w
        else:
            final_score = 0.0
            base_n = base_o = base_d = 0.0
        
        # [v1.4] 데이터 무결성: leaf일 때 가짜 트렌드 생성 금지
        trend_series = None
        if not is_leaf:
            trend_series = naver_datalab_res.get("trend_series")
            if not trend_series:
                # API 실패 시: has_subcat이 True일 때만 시뮬레이션 생성 (지리적 구조 확인된 경우)
                if matched_tree.get("has_subcat", False):
                    sim = self.router.cat_mgr.generate_trend_series(matched_tree)
                    trend_series = {**sim, "is_simulated": True}
        
        return {
            "domain": domain,
            "is_leaf_category": is_leaf,
            "category_analysis": category_analysis,
            "weights_applied": weights,
            "data_source_health": health,
            "primary_source_signal": primary_signal,
            "raw_scores": {
                "final_score": round(final_score, 1),
                "naver_score": base_n if n_w > 0 else 0,
                "oliveyoung_score": base_o if o_w > 0 else 0,
                "daiso_score": base_d if d_w > 0 else 0
            },
            "group_name": group_name,
            "trend_series": trend_series,
            "items": base_items[:10], # 최대 10개 항목 반환
            "all_pool": {
                "naver": naver_shopping_res.get("items", []),
                "oliveyoung": olive_res.get("items", []),
                "daiso": daiso_res.get("items", []),
                "coupang": coupang_res.get("items", [])
            }
        }

    def run_category_node(self, path: list) -> Dict[str, Any]:
        """
        N-Depth 형태의 카테고리 트리 경로를 받아 하위 계층이 있으면 트렌드 비교를,
        하위 계층이 없으면(리프 노드) 쿠팡 쿠팡 검색 랭킹을 반환합니다.
        """
        import time
        import urllib.parse
        from backend.engine.category_manager import CategoryManager

        # 하위 카테고리가 있는지 확인 후 트렌드 분석
        trend_data = self.router.cat_mgr.get_depth_trend_analysis(path)

        if trend_data:
            # 하위 카테고리가 존재함 -> 트렌드 비교 반환 (Phase 1 유사)
            return {
                "path": path,
                "is_leaf": False,
                "trend_series": {
                    "categories": trend_data.get("categories", []),
                    "series": trend_data.get("series", [])
                },
                "ranking": trend_data.get("ranking", [])
            }
        else:
            # 하위 카테고리가 없음 (리프 노드) -> 상품 검색 반환 (Phase 2 유사)
            start = time.time()
            node = self.router.cat_mgr.get_node_by_path(path)
            
            # 검색어 결정: q_keyword > 상위 카테고리 컨텍스트 반영 > path 마지막 단어
            search_query = path[-1]
            if isinstance(node, dict) and "q_keyword" in node:
                search_query = node["q_keyword"]
            elif len(path) >= 3:
                # 상위 카테고리 컨텍스트 반영 (1-depth 대분류 제외)
                # 예: ["패션의류", "여성의류", "바지"] → "여성 바지"
                # 예: ["패션의류", "남성의류", "바지"] → "남성 바지"
                parent = path[-2]  # 직계 상위 카테고리
                leaf = path[-1]    # 현재 리프 노드
                
                # 상위 카테고리에서 성별/대상 키워드 추출
                context_keywords = {
                    "여성의류": "여성", "남성의류": "남성",
                    "여성신발": "여성", "남성신발": "남성",
                    "여성가방": "여성", "남성가방": "남성",
                    "여성언더웨어/잠옷": "여성", "남성언더웨어/잠옷": "남성",
                    "유아동의류": "아동", "유아동신발/잡화": "아동",
                    "여아의류": "여아", "남아의류": "남아",
                }
                context = context_keywords.get(parent, "")
                if context and context not in leaf:
                    search_query = f"{context} {leaf}"
                    logger.info(f"[CategoryNode] 상위 컨텍스트 반영 검색어: '{search_query}' (parent='{parent}', leaf='{leaf}')")

            coupang_res = {"status": "ERROR", "items": []}
            try:
                coupang_res = self.coupang.fetch_ranking(search_query)
            except Exception as e:
                logger.warning(f"[CategoryNode] 쿠팡 스크래핑 실패: {e}")

            items = coupang_res.get("items", [])
            is_coupang_available = coupang_res.get("status") == "OK" and len(items) > 0

            encoded = urllib.parse.quote(search_query)
            coupang_search_url = f"https://www.coupang.com/np/search?q={encoded}"

            products = []
            for idx, it in enumerate(items[:10]):
                products.append({
                    "rank": idx + 1,
                    "title": it.get("name", ""),
                    "price": it.get("price", 0),
                    "image_url": it.get("image_url", ""),
                    "source_url": it.get("source_url", coupang_search_url),
                    "source": "Coupang"
                })

            return {
                "path": path,
                "is_leaf": True,
                "search_query": search_query,
                "is_coupang_available": is_coupang_available,
                "coupang_search_url": coupang_search_url,
                "products": products,
                "execution_time_ms": int((time.time() - start) * 1000)
            }

