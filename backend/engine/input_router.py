import logging
from typing import Dict, Any
from backend.engine.category_manager import CategoryManager

logger = logging.getLogger(__name__)

class InputRouter:
    """사용자가 입력한 분야(domain)를 분석하여 카테고리 특성을 감지"""

    def __init__(self):
        self.beauty_keywords = ["스킨케어", "색조", "헤어", "뷰티", "화장품", "립스틱", "마스크팩", "선크림", "앰플", "세럼", "토너", "에센스", "화장"]
        self.lowprice_keywords = ["수납", "청소", "생활", "주방", "욕실", "정리", "다이소", "저가", "생활용품"]
        self.seasonal_keywords = ["장마", "여름", "겨울", "환절기", "벚꽃", "명절", "캠핑", "피크닉", "가을", "봄", "휴가"]
        
        self.cat_mgr = CategoryManager()
        self.depth1_categories = [
            "패션의류", "패션잡화", "화장품/미용", "디지털/가전", "가구/인테리어", 
            "출산/육아", "식품", "스포츠/레저", "생활/건강", "여가/생활편의"
        ]

    def analyze(self, domain: str) -> Dict[str, Any]:
        """입력 분석 결과 반환"""
        domain_lower = domain.lower()
        
        category_type = "GENERAL"
        if any(k in domain_lower for k in self.beauty_keywords):
            category_type = "BEAUTY"
        elif any(k in domain_lower for k in self.lowprice_keywords):
            category_type = "LOWPRICE"
        elif any(k in domain_lower for k in self.seasonal_keywords):
            category_type = "SEASONAL"
            
        seasonality_score = 0.8 if category_type == "SEASONAL" else 0.3
        
        price_range = "mid"
        if category_type == "LOWPRICE":
            price_range = "low"
        elif category_type == "BEAUTY" and ("명품" in domain_lower or "백화점" in domain_lower):
            price_range = "high"
            
        # Dual Input 로직: 1분류 버튼 클릭인지, 자유입력(keyword)인지 구분
        is_category_search = domain in self.depth1_categories
        
        if is_category_search:
            # 1분류 버튼을 클릭한 경우 트렌드 캐시 조회 (토너먼트 시뮬레이션)
            matched_tree = self.cat_mgr.get_top_trend_tree(domain)
        else:
            # "가성비 주방 설비" 등 텍스트 검색의 경우
            matched_tree = self.cat_mgr.match_from_keyword(domain)
            
        logger.info(f"[InputRouter] '{domain}' -> {category_type} (seasonality:{seasonality_score}, price:{price_range})")
        logger.info(f"[CategoryManger] 매칭된 트렌드: {matched_tree}")

        return {
            "detected_type": category_type,
            "confidence": 0.95,
            "seasonality_score": seasonality_score,
            "price_range": price_range,
            "matched_hierarchy": matched_tree,
            "is_category_search": is_category_search
        }
