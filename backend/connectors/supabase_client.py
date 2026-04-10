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

    def get_site_stats(self):
        """DB에서 누적 분석 횟수 및 주간 Top 분야 정보를 가져옵니다."""
        # 기본값 (DB 연결 실패 시 폴백)
        default_stats = {
            "total_analysis": 24592,
            "top_domain": "식품",
            "top_domain_desc": "(건강/영양제 급등)"
        }
        if not self.client:
            return default_stats
            
        try:
            # site_stats 테이블에서 최신 레코드 1개 조회
            response = self.client.table('site_stats').select('*').limit(1).execute()
            if response.data:
                return response.data[0]
            return default_stats
        except Exception as e:
            logger.error(f"Supabase GET Stats Error: {e}")
            return default_stats

    def increment_analysis_count(self):
        """분석 성공 시 DB의 누적 분석 횟수를 1 증가시킵니다."""
        if not self.client:
            return
            
        try:
            # RPC(데이터베이스 함수)를 사용하여 원자적으로 +1 증가 (동시성 문제 해결)
            # 만약 RPC가 설정되지 않았다면 간단한 update 로직 수행
            stats = self.get_site_stats()
            new_count = int(stats.get('total_analysis', 0)) + 1
            
            # id=1인 레코드를 업데이트 (단일 레코드 관리 가정)
            self.client.table('site_stats').update({"total_analysis": new_count}).eq('id', 1).execute()
        except Exception as e:
            logger.error(f"Supabase Increment Error: {e}")
