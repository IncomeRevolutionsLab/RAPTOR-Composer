import os
import sys
import json
import time
import logging

# 백엔드 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.connectors.naver_connector import NaverConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CategoryCrawler")

class CategoryCrawler:
    """네이버 쇼핑 API를 통해 실제 카테고리 계층 구조를 역추적하여 수집하는 클래스"""
    
    def __init__(self):
        self.naver = NaverConnector()
        self.master_tree = {}
        self.data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'category_master.json'))
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)

    def load_existing(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    self.master_tree = json.load(f)
                    logger.info("기존 카테고리 마스터 로드 완료.")
            except:
                self.master_tree = {}

    def save_tree(self):
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.master_tree, f, ensure_ascii=False, indent=2)
        logger.info(f"트리 저장 완료: {self.data_path}")

    def discover_by_domain(self, domain_name, keywords):
        """특정 도메인에 대해 키워드 기반으로 카테고리를 탐색합니다."""
        logger.info(f"[{domain_name}] 카테고리 매핑 탐색 시작...")
        
        if domain_name not in self.master_tree:
            self.master_tree[domain_name] = {"base": 50, "subcategories": {}}

        for kw in keywords:
            logger.info(f"  -> '{kw}' 검색 중...")
            try:
                res = self.naver.fetch_shopping_search(kw)
                if res.get("status") == "OK":
                    items = res.get("items", [])
                    for item in items:
                        c1, c2, c3, c4 = item.get("category1"), item.get("category2"), item.get("category3"), item.get("category4")
                        
                        # 도메인이 일치하거나 비어있는 경우(전체 검색) 매칭 시도
                        if c1 == domain_name:
                            self._build_branch(c1, c2, c3, c4)
                        elif not domain_name: # 도메인 지정 없을 시 첫번째 대분류 기준
                            self._build_branch(c1, c2, c3, c4)
                            
            except Exception as e:
                logger.error(f"검색 중 오류: {e}")
            time.sleep(1) # API 부하 방지
            
        self.save_tree()

    def _build_branch(self, c1, c2, c3, c4):
        """1-4단계 카테고리 경로를 트리에 삽입 (중복 무시)"""
        if not c1: return
        
        # depth 1 (Domain)
        if c1 not in self.master_tree:
            self.master_tree[c1] = {"base": 50, "subcategories": {}}
        
        # depth 2
        curr = self.master_tree[c1]["subcategories"]
        if c2 and c2 not in curr:
            curr[c2] = {"base": 50, "subcategories": {}}
        
        # depth 3
        if c2 and c3:
            curr = curr[c2]["subcategories"]
            if c3 not in curr:
                curr[c3] = {"base": 50, "subcategories": {}}
            
            # depth 4
            if c4:
                curr = curr[c3]["subcategories"]
                if c4 not in curr:
                    curr[c4] = {"base": 50} # Leaf node

    def print_summary(self, domain_name):
        """사용자 보고용 트리 요약 출력"""
        if domain_name not in self.master_tree:
            print(f"{domain_name} 데이터가 없습니다.")
            return

        print(f"\n### [{domain_name}] 수집된 계층 구조 보고서 ###")
        tree = self.master_tree[domain_name]["subcategories"]
        for d2, info2 in sorted(tree.items()):
            d3_list = info2.get("subcategories", {})
            print(f"- {d2} ({len(d3_list)}개 소분류)")
            for d3, info3 in sorted(d3_list.items()):
                d4_list = info3.get("subcategories", {})
                if d4_list:
                    d4_names = ", ".join(sorted(d4_list.keys()))
                    print(f"  └ {d3}: {d4_names}")
                else:
                    print(f"  └ {d3}")

if __name__ == "__main__":
    crawler = CategoryCrawler()
    crawler.load_existing()
    
    # [v2.35] 10대 핵심 도메인별 수집 키워드 정의
    domain_keyword_map = {
        "패션의류": ["원피스", "셔츠", "청바지", "가디건", "니트"],
        "패션잡화": ["운동화", "숄더백", "로퍼", "볼캡", "지갑"],
        "화장품/미용": ["스킨케어", "클렌징폼", "마스크팩", "자외선차단제", "쿠션팩트"],
        "디지털/가전": ["자급제폰", "무선이어폰", "노트북", "공기청정기", "가습기"],
        "가구/인테리어": ["수납함", "무드등", "컴퓨터책상", "차박매트", "암막커튼"],
        "출산/육아": ["기저귀", "물티슈", "유모차", "카시트", "분유"],
        "식품": ["제로콜라", "닭가슴살", "밀키트", "단백질쉐이크", "초콜릿"],
        "스포츠/레저": ["캠핑의자", "요가매트", "등산화", "골프채", "수영복"],
        "생활/건강": ["세제", "화장지", "영양제", "마스크", "샤워기헤드"],
        "여가/생활편의": ["여행캐리어", "반려견사료", "강아지간식", "고양이모래", "렌터카"]
    }
    
    print("=== [SSPS] 10대 도메인 순차 카테고리 수집 시작 ===")
    for domain, kws in domain_keyword_map.items():
        print(f"\n>>> [{domain}] 분야 수집 중... (키워드: {', '.join(kws[:3])} 등)")
        crawler.discover_by_domain(domain, kws)
        crawler.print_summary(domain)
        time.sleep(1)
        
    print("\n=== [SSPS] 모든 분야 데이터 수집 및 마스터 트리 업데이트 완료 ===")
