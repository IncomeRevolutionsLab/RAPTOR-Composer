import os
import json
import logging
from dotenv import load_dotenv

# .env 파일 자동 로드 (클라우드 환경에서는 환경변수로 대체됨)
load_dotenv()

logger = logging.getLogger(__name__)

class SupabaseClient:
    """Supabase DB 연동을 위한 클라이언트 모듈 (스케줄러 및 실시간 캐시 룩업용)"""
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL", "")
        self.key = os.environ.get("SUPABASE_KEY", "")
        self.client = None
        
        if self.url and self.key:
            try:
                from supabase import create_client, Client
                self.client: Client = create_client(self.url, self.key)
            except ImportError:
                logger.warning("supabase 파이썬 패키지가 설치되지 않았습니다.")
        else:
            logger.info("Supabase 자격 증명이 없어 로컬 Mock 캐시 모드로 동작합니다.")

    def get_trend_data(self, keyword: str):
        """DB에서 키워드 트렌드 데이터를 조회합니다."""
        if not self.client:
            return None
            
        try:
            response = self.client.table('trend_cache').select('trend_data').eq('query_keyword', keyword).execute()
            
            if response.data:
                # 조회수(인기도) 캐시에서 +1 업데이트 (비동기로 진행하는 것이 바람직하나 간단하게 처리)
                # self.client.rpc('increment_popularity', {'kw': keyword}).execute()
                return response.data[0]['trend_data']
            return None
        except Exception as e:
            logger.error(f"Supabase GET Error: {e}")
            return None

    def upsert_trend_data(self, keyword: str, trend_data: dict):
        """네이버 API에서 가져온 최신 트렌드를 DB에 업데이트합니다."""
        if not self.client:
            return False
            
        try:
            payload = {
                "query_keyword": keyword,
                "trend_data": trend_data
            }
            # keyword가 이미 있으면 덮어쓰기(upsert) 수행
            self.client.table('trend_cache').upsert(payload, returning="minimal").execute()
            return True
        except Exception as e:
            logger.error(f"Supabase UPSERT Error: {e}")
            return False
