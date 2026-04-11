import os
import json
import logging
from dotenv import load_dotenv

# .env 파일 자동 로드 (클라우드 환경에서는 환경변수로 대체됨)
load_dotenv()

logger = logging.getLogger(__name__)

class SupabaseClient:
    """Supabase DB 연동을 위한 클라이언트 모듈 (스케줄러 및 실시간 캐시 룩업용)"""
    
    # [v2.351] 로컬 메모리 카운터 (DB 연결 실패 시 폴백용, 클래스 변수로 공유)
    _local_analysis_count = 0
    _local_top_domain = "식품"
    
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL", "")
        self.key = os.environ.get("SUPABASE_KEY", "")
        self.client = None
        self._db_available = False
        
        if self.url and self.key:
            try:
                from supabase import create_client, Client
                self.client: Client = create_client(self.url, self.key)
                # DB 연결 테스트: site_stats 테이블 접근 가능 여부 확인
                test = self.client.table('site_stats').select('id').limit(1).execute()
                if test.data:
                    self._db_available = True
                    logger.info("Supabase DB 연결 성공 (site_stats 테이블 확인 완료)")
                else:
                    logger.warning("Supabase 연결은 됐으나 site_stats 테이블에 데이터가 없습니다. 초기 레코드를 생성합니다.")
                    try:
                        self.client.table('site_stats').upsert({
                            "id": 1, "total_analysis": 0,
                            "top_domain": "식품", "top_domain_desc": "(최근 7일 클릭 지수 1위)"
                        }).execute()
                        self._db_available = True
                    except Exception as init_e:
                        logger.error(f"site_stats 초기 레코드 생성 실패: {init_e}")
            except ImportError:
                logger.warning("supabase 파이썬 패키지가 설치되지 않았습니다. 로컬 카운터 모드로 동작합니다.")
            except Exception as e:
                logger.warning(f"Supabase 연결 실패: {e}. 로컬 카운터 모드로 동작합니다.")
        else:
            logger.info("Supabase 자격 증명이 없어 로컬 카운터 모드로 동작합니다.")

    def get_trend_data(self, keyword: str):
        """DB에서 키워드 트렌드 데이터를 조회합니다."""
        if not self.client or not self._db_available:
            return None
            
        try:
            response = self.client.table('trend_cache').select('trend_data').eq('query_keyword', keyword).execute()
            
            if response.data:
                return response.data[0]['trend_data']
            return None
        except Exception as e:
            logger.error(f"Supabase GET Error: {e}")
            return None

    def upsert_trend_data(self, keyword: str, trend_data: dict):
        """네이버 API에서 가져온 최신 트렌드를 DB에 업데이트합니다."""
        if not self.client or not self._db_available:
            return False
            
        try:
            payload = {
                "query_keyword": keyword,
                "trend_data": trend_data
            }
            self.client.table('trend_cache').upsert(payload, returning="minimal").execute()
            return True
        except Exception as e:
            logger.error(f"Supabase UPSERT Error: {e}")
            return False

    def get_site_stats(self):
        """DB에서 누적 분석 횟수 및 주간 Top 분야 정보를 가져옵니다."""
        default_stats = {
            "total_analysis": SupabaseClient._local_analysis_count,
            "top_domain": SupabaseClient._local_top_domain,
            "top_domain_desc": "(최근 7일 클릭 지수 1위)"
        }
        
        if not self.client or not self._db_available:
            return default_stats
            
        try:
            response = self.client.table('site_stats').select('*').eq('id', 1).limit(1).execute()
            if response.data:
                db_stats = response.data[0]
                # DB 값과 로컬 카운터 동기화 (DB가 더 크면 DB 기준)
                db_count = int(db_stats.get('total_analysis', 0))
                if db_count > SupabaseClient._local_analysis_count:
                    SupabaseClient._local_analysis_count = db_count
                return db_stats
            return default_stats
        except Exception as e:
            logger.error(f"Supabase GET Stats Error: {e}")
            return default_stats

    def increment_analysis_count(self):
        """분석 성공 시 누적 분석 횟수를 1 증가시킵니다. DB 실패 시 로컬 카운터 사용."""
        # [v2.351] 로컬 카운터는 항상 증가 (DB 성공 여부와 무관)
        SupabaseClient._local_analysis_count += 1
        logger.info(f"[Counter] 분석 카운트 +1 → 현재 로컬 카운터: {SupabaseClient._local_analysis_count}")
        
        if not self.client or not self._db_available:
            logger.info(f"[Counter] DB 미연결 → 로컬 카운터만 사용: {SupabaseClient._local_analysis_count}")
            return
            
        try:
            # 현재 DB 값 조회 후 +1 업데이트
            response = self.client.table('site_stats').select('total_analysis').eq('id', 1).limit(1).execute()
            if response.data:
                current_count = int(response.data[0].get('total_analysis', 0))
                new_count = current_count + 1
                update_res = self.client.table('site_stats').update({"total_analysis": new_count}).eq('id', 1).execute()
                logger.info(f"[Counter] DB 업데이트 성공: {current_count} → {new_count}")
                # 로컬 카운터도 DB 기준 동기화
                SupabaseClient._local_analysis_count = new_count
            else:
                # 레코드가 없으면 생성
                self.client.table('site_stats').upsert({
                    "id": 1,
                    "total_analysis": SupabaseClient._local_analysis_count,
                    "top_domain": "식품",
                    "top_domain_desc": "(최근 7일 클릭 지수 1위)"
                }).execute()
                logger.info(f"[Counter] DB 레코드 생성 완료: {SupabaseClient._local_analysis_count}")
        except Exception as e:
            logger.error(f"[Counter] DB 업데이트 실패 (로컬 카운터로 폴백): {e}")
