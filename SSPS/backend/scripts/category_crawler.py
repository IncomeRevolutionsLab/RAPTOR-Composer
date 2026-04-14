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
    
    # [v2.35] 패션잡화 전수 수집 키워드 투입 (100% 매칭용)
    domain_keyword_map = {
        "패션의류": [
            "니트", "풀오버", "카디건", "터틀넥", "원피스", "티셔츠", "블라우스/셔츠", "바지", "청바지", "스커트",
            "재킷", "레더재킷", "퍼재킷", "후드집업", "패딩", "숏코트", "롱코트", "트렌치코트", "레인코트",
            "레깅스", "점퍼", "트레이닝복", "정장세트", "한복", "유니폼/단체복", "파티복", "점프슈트", "코디세트",
            "브라", "여성팬티", "브라팬티세트", "여성잠옷/홈웨어", "시즌성내의", "내복", "힙워머", "모시메리",
            "보정속옷", "니퍼/복대", "코르셋", "올인원/바디쉐이퍼", "거들", "슬립", "러닝/캐미솔", "속치마/속바지", "언더웨어소품",
            "남성니트", "남성티셔츠", "남성셔츠/남방", "남성아우터", "남성재킷", "남성패딩", "남성점퍼", "남성청바지", "남성바지",
            "남성정장세트", "남성트레이닝복", "남성한복", "남성코디세트", "남성팬티", "남성러닝", "남성잠옷/홈웨어"
        ],
        "패션잡화": [
            "여성신발", "부츠", "워커", "로퍼", "펌프스", "스니커즈", "샌들", "기능화", "작업화", "컴포트화",
            "남성운동화", "남성구두", "남성샌들", "기내용 캐리어", "수하물 캐리어", "보스턴백", "여권지갑",
            "반지갑", "장갑", "벨트", "정장벨트", "멜빵", "야구모자", "비니", "페도라", "선캡",
            "패션시계", "시계줄", "가죽시계", "메탈시계", "골드바", "순금기념품",
            "반지", "귀걸이", "목걸이", "팔찌", "펜던트", "발찌", "피어싱", "14K", "18K", "순금주얼리",
            "가발", "헤어밴드", "헤어핀", "양말", "스포츠양말", "스타킹", "우산", "양산", "스카프", "손수건", "넥타이"
        ],
    }
    
    # [v2.40] 패션잡화 정밀 수집 진행
    target_domains = ["패션잡화"]
    
    print("=== [SSPS] 2단계: [패션잡화] 정밀 카테고리 수집 시작 ===")
    for domain in target_domains:
        kws = domain_keyword_map.get(domain, [])
        print(f"\n>>> [{domain}] 분야 수집 중... (키워드 {len(kws)}개 전수 조사)")
        crawler.discover_by_domain(domain, kws)
        crawler.print_summary(domain)
        time.sleep(1)
        
    print("\n=== [SSPS] 1단계 수집 완료. 사용자 확인을 위해 대기합니다. ===")
        
    print("\n=== [SSPS] 모든 분야 데이터 수집 및 마스터 트리 업데이트 완료 ===")
