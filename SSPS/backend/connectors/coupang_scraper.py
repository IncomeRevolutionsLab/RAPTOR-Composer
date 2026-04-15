import requests
from bs4 import BeautifulSoup
import urllib.parse
import logging
from typing import Dict, Any

from backend.config import settings
from backend.utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# Coupang Circuit Breaker
coupang_cb = CircuitBreaker("coupang_scraper", fail_max=settings.circuit_breaker_fail_max)

class CoupangScraper:
    def __init__(self):
        self.base_url = "https://www.coupang.com/np/search?componet=&q={}"
        # Coupang heavily blocks requests without standard headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def fetch_ranking(self, domain: str) -> Dict[str, Any]:
        """쿠팡 검색 결과 상위 10개 제품 추출"""
        def _request_coupang():
            encoded_query = urllib.parse.quote(domain)
            url = self.base_url.format(encoded_query)
            
            try:
                response = requests.get(url, headers=self.headers, timeout=settings.scraper_timeout_seconds)
                response.raise_for_status()
            except Exception as e:
                logger.warning(f"Coupang Scraper HTTP Error: {e}")
                raise e
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            product_list = soup.select('li.search-product')
            items = []
            
            for idx, product in enumerate(product_list):
                if len(items) >= 10:
                    break
                    
                # Title
                title_elem = product.select_one('div.name')
                title = title_elem.text.strip() if title_elem else "Unknown Product"
                
                # Price
                price_elem = product.select_one('strong.price-value')
                price_text = price_elem.text.strip().replace(',', '') if price_elem else "0"
                price = int(price_text) if price_text.isdigit() else 0
                
                # Image
                img_elem = product.select_one('img.search-product-wrap-img')
                image_url = ""
                if img_elem:
                    image_url = img_elem.get('src') or img_elem.get('data-src') or ""
                    if image_url and image_url.startswith('//'):
                        image_url = "https:" + image_url
                        
                # Link
                link_elem = product.select_one('a.search-product-link')
                source_url = ""
                if link_elem and link_elem.get('href'):
                    source_url = "https://www.coupang.com" + link_elem.get('href')
                    
                # 데이터 정합성 검사 (v2.49)
                if not title or title == "Unknown Product":
                    continue

                items.append({
                    "name": title,
                    "price": price,
                    "image_url": image_url,
                    "source_url": source_url,
                    "rank": len(items) + 1,
                    "source": "Coupang"
                })
                
            # [v2.49] 5개 미만인 경우에도 최소한의 데이터 구조 보장
            if not items:
                logger.warning("Coupang Scraper: No valid items found.")
                return {"source": "coupang", "status": "EMPTY", "items": []}
                
            return {"source": "coupang", "status": "OK", "items": items}

        # Call with Circuit Breaker
        return coupang_cb.call(
            _request_coupang,
            fallback={"source": "coupang", "status": "FAIL", "items": []}
        )
