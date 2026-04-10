import requests
import logging
from typing import Dict, Any
from bs4 import BeautifulSoup
from backend.config import settings
from backend.utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

oliveyoung_cb = CircuitBreaker("oliveyoung", fail_max=settings.circuit_breaker_fail_max)

class OliveYoungScraper:
    def __init__(self):
        self.use_mock = settings.use_mock_data
        
    def fetch_ranking(self, keyword: str) -> Dict[str, Any]:
        """올리브영 검색/랭킹 실시간 스크래핑"""
        if self.use_mock:
            return self._get_mock_ranking(keyword)

        def _scrape():
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.oliveyoung.co.kr/"
            }
            # 실제 올리브영 검색 URL 파라미터 규격 적용
            search_url = f"https://www.oliveyoung.co.kr/store/search/getSearchMain.do?query={requests.utils.quote(keyword)}"
            response = requests.get(search_url, headers=headers, timeout=settings.scraper_timeout_seconds)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = []
            
            # 리얼 DOM 요소 파싱: 상품 리스트 '.prd_info' 기준
            product_list = soup.select('.prd_info')
            for idx, prd in enumerate(product_list[:10]):  # Top 10 까지만
                try:
                    name_tag = prd.select_one('.tx_name')
                    price_tag = prd.select_one('.tx_cur .tx_num')
                    img_tag = prd.select_one('img')
                    link_tag = prd.find_parent('a')
                    
                    if name_tag and price_tag:
                        name = name_tag.text.strip()
                        price_str = price_tag.text.replace(',', '').strip()
                        price = int(price_str) if price_str.isdigit() else 0
                        img_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else ""
                        link = link_tag['href'] if link_tag and 'href' in link_tag.attrs else search_url
                        
                        items.append({
                            "name": name,
                            "price": price,
                            "rank": idx + 1,
                            "review_count": 0,  # 검색 페이지에서 리뷰 수는 노출되지 않기도 함 (단순화)
                            "rating": 4.5,
                            "image_url": img_url,
                            "source_url": link
                        })
                except Exception as e:
                    logger.debug(f"[OliveYoung] 파싱 에러 스킵: {e}")
                    continue
            
            if not items:
                logger.warning(f"[OliveYoungScraper] HTML에서 상품을 찾지 못함 (블락되었거나 검색 결과 없음). 키워드: {keyword}")
                # Circuit Open을 유도하기 위해 에러 레이즈
                raise ValueError("No products found")
                
            return {"source": "oliveyoung", "status": "OK", "items": items}

        return oliveyoung_cb.call(
            _scrape,
            fallback=self._get_mock_ranking(keyword)
        )

    def _get_mock_ranking(self, keyword: str) -> Dict[str, Any]:
        return {
            "source": "oliveyoung",
            "status": "MOCK_FALLBACK",
            "items": [
                {
                    "name": f"[올리브영 단독] {keyword} 기획세트 (Mock)",
                    "price": 28000,
                    "rank": 1,
                    "review_count": 1250,
                    "rating": 4.9,
                    "image_url": "https://via.placeholder.com/300?text=OliveYoung+1"
                }
            ]
        }
