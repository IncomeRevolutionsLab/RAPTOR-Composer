import requests
import logging
from typing import Dict, Any
from bs4 import BeautifulSoup
from backend.config import settings
from backend.utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

daiso_cb = CircuitBreaker("daiso", fail_max=settings.circuit_breaker_fail_max)

class DaisoScraper:
    def __init__(self):
        self.use_mock = settings.use_mock_data
        
    def fetch_ranking(self, keyword: str) -> Dict[str, Any]:
        """다이소 검색 페이지 실시간 스크래핑"""
        if self.use_mock:
            return self._get_mock_ranking(keyword)

        def _scrape():
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }
            search_url = f"https://www.daisomall.co.kr/search/search.do?searchTerm={requests.utils.quote(keyword)}"
            response = requests.get(search_url, headers=headers, timeout=settings.scraper_timeout_seconds)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = []
            
            # 리얼 DOM 요소 파싱: 실제 다이소몰 구조는 spa일 가능성 높으나 SSR 텍스트를 파싱
            product_list = soup.select('.item-box')
            for idx, prd in enumerate(product_list[:10]):
                try:
                    name_tag = prd.select_one('.item-name')
                    price_tag = prd.select_one('.price-num')
                    img_tag = prd.select_one('img')
                    
                    if name_tag and price_tag:
                        name = name_tag.text.strip()
                        price_str = price_tag.text.replace(',', '').strip()
                        price = int(price_str) if price_str.isdigit() else 0
                        img_url = img_tag['src'] if img_tag else ""
                        
                        items.append({
                            "name": name,
                            "price": price,
                            "rank": idx + 1,
                            "rating": 4.5,
                            "image_url": img_url,
                            "source_url": search_url
                        })
                except Exception as e:
                    continue
            
            if not items:
                logger.warning(f"[DaisoScraper] 웹 구조 변경 의심, 파싱 내역이 없음. 키워드: {keyword}")
                raise ValueError("No products found")
                
            return {"source": "daiso", "status": "OK", "items": items}

        return daiso_cb.call(
            _scrape,
            fallback=self._get_mock_ranking(keyword)
        )

    def _get_mock_ranking(self, keyword: str) -> Dict[str, Any]:
        return {
            "source": "daiso",
            "status": "MOCK_FALLBACK",
            "items": [
                {
                    "name": f"다이소 가성비 {keyword} (Mock)",
                    "price": 3000,
                    "rank": 1,
                    "review_count": 500,
                    "rating": 4.5,
                    "image_url": "https://via.placeholder.com/300?text=Daiso+1"
                }
            ]
        }
