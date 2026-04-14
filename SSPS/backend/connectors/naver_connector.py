import requests
import logging
from typing import Dict, Any, List
from backend.config import settings
from backend.utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

naver_datalab_cb = CircuitBreaker("naver_datalab", fail_max=settings.circuit_breaker_fail_max)
naver_shopping_cb = CircuitBreaker("naver_shopping", fail_max=settings.circuit_breaker_fail_max)

class NaverConnector:
    def __init__(self):
        self.client_id = settings.naver_client_id
        self.client_secret = settings.naver_client_secret
        
        self.use_mock = False # 100% 실제 API 모드 강조 강제 설정
        
        self.datalab_search_url = "https://openapi.naver.com/v1/datalab/search"
        self.shopping_url = "https://openapi.naver.com/v1/search/shop.json"

    def get_headers(self) -> dict:
        # 네이버 개발자 센터에 등록된 서비스 URL을 Referer/Origin으로 설정하여 요청 유효성 확보
        registered_url = "https://ssps-engine-git-master-incomerevolutionslab.vercel.app/"
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Referer": registered_url,
            "Origin": registered_url
        }

    def fetch_datalab_trend(self, keywords: List[str]) -> Dict[str, Any]:
        """네이버 데이터랩(통합검색어) 트렌드 조회: 5개 키워드 비교 및 DB 캐시 최우선 룩업"""
        
        # [Zero-API-Cost] 클라우드 DB 캐시 확인 (2026년 실시간 데이터 준수를 위해 이번 작업에서는 캐시 버스팅)
        # TODO: 향후 캐시 데이터의 timestamp를 확인하여 1주일 이내 데이터만 사용하도록 개선 필요
        FORCE_FRESH = True 
        if not FORCE_FRESH and len(keywords) == 1:
            try:
                from backend.connectors.supabase_client import SupabaseClient
                db_client = SupabaseClient()
                cached_data = db_client.get_trend_data(keywords[0])
                if cached_data:
                    logger.info(f"[Cache Hit] 네이버 API 호출 없이 Supabase DB에서 '{keywords[0]}' 반환 완료!")
                    return {"status": "OK", "trend_series": cached_data, "source": "Supabase DB Cache"}
            except Exception as e:
                logger.warning(f"Supabase DB 룩업 실패, 네이버 API로 Fallback: {e}")
        def _request_datalab():
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            end_date = datetime.now()
            start_date = end_date - relativedelta(years=1)
            
            # 최대 5개까지만 전송
            groups = []
            for kw in keywords[:5]:
                groups.append({"groupName": kw, "keywords": [kw]})
                
            body = {
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "timeUnit": "month",
                "keywordGroups": groups
            }
            response = requests.post(
                self.datalab_search_url, 
                headers=self.get_headers(), 
                json=body,
                timeout=settings.scraper_timeout_seconds
            )
            if response.status_code != 200:
                logger.error(f"Naver API Error ({response.status_code}): {response.text}")
            response.raise_for_status()
            
            # 응답에서 series array 추출
            data = response.json()
            series = []
            categories = []
            
            for g in data.get("results", []):
                name = g.get("title")
                points = g.get("data", [])
                
                if not categories and points:
                    categories = [p.get("period")[-5:] for p in points] # '01-01'
                    
                series.append({
                    "name": name,
                    "data": [p.get("ratio", 0) for p in points]
                })
                
            # 상대 트렌드 합계 점수를 계산 (최근 3개월 집중)
            trend_score = 0.0
            if series and series[0]["data"]:
                recent_vals = series[0]["data"][-3:]
                trend_score = sum(recent_vals) / len(recent_vals) * 1.5 if len(recent_vals) > 0 else 0
                
            return {
                "source": "naver_datalab", 
                "status": "OK", 
                "trend_score": min(trend_score, 100),
                "trend_series": {"categories": categories, "series": series}
            }

        return naver_datalab_cb.call(
            _request_datalab,
            fallback={"source": "naver_datalab", "status": "FAIL", "trend_score": 0.0, "reason": "Circuit Breaker OPEN or Timeout/Error"}
        )

    def fetch_shopping_search(self, query: str) -> Dict[str, Any]:
        """네이버 쇼핑 검색 결과 API 조회"""
        def _request_shopping():
            response = requests.get(
                self.shopping_url,
                headers=self.get_headers(),
                params={"query": query, "display": 15, "sort": "sim"},
                timeout=settings.scraper_timeout_seconds
            )
            response.raise_for_status()
            
            data = response.json()
            items = []
            for idx, r in enumerate(data.get("items", [])):
                items.append({
                    "name": r.get("title", "").replace("<b>", "").replace("</b>", ""),
                    "price": int(r.get("lprice", 0)),
                    "rank": idx + 1,
                    "image_url": r.get("image"),
                    "source_url": r.get("link"),
                    "category1": r.get("category1", ""),
                    "category2": r.get("category2", ""),
                    "category3": r.get("category3", ""),
                    "category4": r.get("category4", "")
                })
            return {"source": "naver_shopping", "status": "OK", "items": items}

        return naver_shopping_cb.call(
            _request_shopping,
            fallback={"source": "naver_shopping", "status": "FAIL", "items": [], "reason": "Circuit Breaker OPEN or Timeout/Error"}
        )

    def fetch_popular_keywords(self, domain: str) -> Dict[str, Any]:
        """[신규] 최근 1주일 가장 핫한 급상승/인기 검색어 랭킹 조회 (Mock 또는 우회 구현)"""
        # 네이버 쇼핑인사이트 OpenAPI는 검색어 랭킹 API를 직접 제공하지 않아,
        # 분야별로 가상의 트렌디한 키워드 룰셋 혹은 파싱된 결과를 제공합니다.
        
        import random
        from datetime import datetime, timedelta
        
        today = datetime.now()
        start_dt = (today - timedelta(days=7)).strftime("%m.%d")
        end_dt = today.strftime("%m.%d")
        period = f"{start_dt} ~ {end_dt}"
        
        # 키워드 풀셋 구성 (PPL/시즌/급상승 반영)
        pools = {
            "패션의류": ["경량패딩", "바람막이", "여름 니트", "크롭 티셔츠", "조거팬츠", "트위드 자켓", "와이드팬츠", "하객룩", "오버핏 셔츠", "롱원피스"],
            "패션잡화": ["리본 헤어핀", "크록스 지비츠", "에코백", "실버 목걸이", "라피아햇", "투명 안경테", "여행용 캐리어", "버킷햇", "진주 귀걸이", "카드지갑"],
            "화장품/미용": ["두바이 수분크림", "모델링팩", "올영세일 추천템", "모공세럼", "순한 선크림", "괄사 마사지기", "여드름 패치", "아이패치", "쿠션 팩트", "헤어 에센스"],
            "디지털/가전": ["미니 선풍기", "에어컨 추천", "제습기", "블루투스 이어폰 케이스", "보조배터리", "스마트워치 스트랩", "가습기", "태블릿 거치대", "로봇청소기", "닌텐도 스위치 칩"],
            "식품": ["두바이 쫀득쿠키", "제로 콜라", "단백질 쉐이크", "닭가슴살 소시지", "요아정", "초당옥수수", "스테비아 토마토", "프로틴바", "납작복숭아", "다이어트 곤약젤리"]
        }
        
        # 폴백
        default_pool = ["다용도 수납장", "캠핑 의자", "아기물티슈", "단백질 보충제", "방향제", "요가매트", "세차용품", "문구류 세트", "홈트 용품", "비타민"]
        
        results = pools.get(domain, default_pool)
        
        # 트렌디한 변형
        random.shuffle(results)
        
        items = []
        for i, kw in enumerate(results[:10]):
            trend_val = random.randint(-2, 15)  # 상승/하락 등락
            items.append({
                "rank": i + 1,
                "keyword": kw,
                "trend_status": "UP" if trend_val > 0 else ("DOWN" if trend_val < 0 else "NEW"),
                "trend_val": abs(trend_val)
            })
            
        return {
            "source": "datalab_popular_mock",
            "status": "OK",
            "period": period,
            "items": items
        }

    def fetch_shopping_trend_by_cid(self, cid: str, name: str) -> Dict[str, Any]:
        """쇼핑인사이트 API: 카테고리 ID(cid) 기반 클릭 트렌드 조회"""
        def _request_shopping_trend():
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            # API 호출 시 CID는 문자열이어야 함
            str_cid = str(cid)
            end_date = datetime.now()
            start_date = end_date - relativedelta(years=1)
            
            body = {
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "timeUnit": "month",
                "category": [{"name": name, "param": [str_cid]}]
            }
            
            # 쇼핑인사이트 카테고리별 클릭 추이 공식 URL
            url = "https://openapi.naver.com/v1/datalab/shopping/categories"
            
            response = requests.post(
                url, 
                headers=self.get_headers(), 
                json=body,
                timeout=settings.scraper_timeout_seconds
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            if not results:
                return {"status": "FAIL", "reason": "No results for CID"}
            
            res = results[0]
            points = res.get("data", [])
            categories = [p.get("period")[-5:] for p in points]
            series = [{
                "name": name,
                "data": [p.get("ratio", 0) for p in points]
            }]
            
            return {
                "source": "naver_shopping_insight", 
                "status": "OK", 
                "trend_series": {"categories": categories, "series": series}
            }

        return naver_datalab_cb.call(
            _request_shopping_trend,
            fallback={"source": "naver_shopping_insight", "status": "FAIL", "reason": "Circuit Breaker / API Error"}
        )
