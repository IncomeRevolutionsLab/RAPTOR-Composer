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
        
        # [v2.352] 로컬 영속성 스토리지 경로 설정
        self.local_storage_path = os.path.join(os.path.dirname(__file__), "..", "data", "site_stats.json")
        os.makedirs(os.path.dirname(self.local_storage_path), exist_ok=True)
        self._load_from_local_file()
        
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

    def _load_from_local_file(self):
        """로컬 파일에서 통계 정보를 로드합니다."""
        if os.path.exists(self.local_storage_path):
            try:
                with open(self.local_storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    SupabaseClient._local_analysis_count = data.get("total_analysis", 0)
                    SupabaseClient._local_top_domain = data.get("top_domain", "식품")
                    logger.info(f"[Counter] 로컬 파일에서 데이터 로드: {SupabaseClient._local_analysis_count}회")
            except Exception as e:
                logger.error(f"[Counter] 로컬 파일 로드 실패: {e}")

    def _save_to_local_file(self):
        """로컬 파일에 현재 통계 정보를 저장합니다."""
        try:
            data = {
                "total_analysis": SupabaseClient._local_analysis_count,
                "top_domain": SupabaseClient._local_top_domain
            }
            with open(self.local_storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Counter] 로컬 파일 저장 실패: {e}")

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

    def upsert_trend_data(self, keyword: str, trend_data: dict, sync_version: str = "v1"):
        """네이버 API에서 가져온 최신 트렌드를 특정 버전 태그와 함께 DB에 업데이트합니다."""
        if not self.client or not self._db_available:
            return False
            
        try:
            payload = {
                "query_keyword": keyword,
                "trend_data": trend_data,
                "sync_version": sync_version,
                "updated_at": "now()"
            }
            self.client.table('trend_cache').upsert(payload, returning="minimal").execute()
            return True
        except Exception as e:
            logger.error(f"Supabase UPSERT Error: {e}")
            return False

    def upsert_raw_trend_data(self, keyword: str, raw_data: dict, sync_version: str = "raw"):
        """가공 전 네이버 원본 데이터를 별도 테이블에 저장합니다. (v2.75 디버깅 및 감사용)"""
        if not self.client or not self._db_available:
            return False
            
        try:
            payload = {
                "query_keyword": keyword,
                "raw_data": raw_data,
                "sync_version": sync_version,
                "updated_at": "now()"
            }
            # trend_raw 테이블이 없으면 생성되거나 실패할 수 있으므로, 
            # 사용자에게 테이블 생성이 필요함을 안내하거나 trend_cache와 동일 구조임을 가정합니다.
            self.client.table('trend_raw').upsert(payload, returning="minimal").execute()
            return True
        except Exception as e:
            # 테이블이 없는 경우 로깅하고 false 반환
            logger.warning(f"Supabase RAW UPSERT 실패 (trend_raw 테이블 확인 필요): {e}")
            return False

    def get_trend_data(self, keyword: str, sync_version: str = None):
        """DB에서 특정 버전의 키워드 트렌드 데이터를 조회합니다."""
        if not self.client or not self._db_available:
            return None
            
        try:
            query = self.client.table('trend_cache').select('trend_data').eq('query_keyword', keyword)
            if sync_version:
                query = query.eq('sync_version', sync_version)
            else:
                # 버전 미지정 시 최신 활성 버전 자동 조회 (구현 예정)
                active_v = self.get_active_sync_version()
                query = query.eq('sync_version', active_v)
                
            response = query.execute()
            if response.data:
                return response.data[0]['trend_data']
            return None
        except Exception as e:
            logger.error(f"Supabase GET Error: {e}")
            return None

    def get_active_sync_version(self) -> str:
        """현재 서비스 중인 활성 데이터 버전을 가져옵니다."""
        try:
            res = self.client.table('site_stats').select('active_sync_version').eq('id', 1).execute()
            if res.data and res.data[0].get('active_sync_version'):
                return res.data[0]['active_sync_version']
        except: pass
        return "default"

    def get_version_keywords_count(self, version: str) -> int:
        """특정 버전에 수집된 키워드 개수를 반환합니다."""
        if not self.client or not self._db_available: return 0
        try:
            res = self.client.table('trend_cache').select('query_keyword', count='exact').eq('sync_version', version).execute()
            return res.count if res.count is not None else 0
        except: return 0

    def get_all_keywords_by_version(self, version: str) -> set:
        """특정 버전에 이미 수집된 모든 키워드 목록을 반환합니다."""
        if not self.client or not self._db_available: return set()
        try:
            # 대량 조회를 위해 페이지네이션 처리 (필요시)
            res = self.client.table('trend_cache').select('query_keyword').eq('sync_version', version).execute()
            if res.data:
                return {item['query_keyword'] for item in res.data}
        except: pass
        return set()

    def set_active_sync_version(self, version: str):
        """데이터 수집 완료 후 활성 버전을 한꺼번에 교체(Atomic Swap)합니다."""
        if not self.client or not self._db_available: return
        try:
            self.client.table('site_stats').update({"active_sync_version": version}).eq('id', 1).execute()
            logger.info(f"[Sync] 활성 버전 교체 완료: {version}")
        except Exception as e:
            logger.error(f"Failed to swap active version: {e}")

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
        self._save_to_local_file() # 로컬 파일에 즉시 영속화
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

    # ── Popular Keywords Operations ──────────────────────────────────

    def save_daily_keyword_ranking(self, domain: str, keywords: list):
        """매일 수집된 도메인별 인기 검색어 1~10위 기록을 저장합니다."""
        if not self.client or not self._db_available: return
        from datetime import datetime
        try:
            payload = {
                "domain": domain,
                "ranking_data": keywords, # [{"rank": 1, "keyword": "원피스"}, ...]
                "created_at": datetime.now().strftime("%Y-%m-%d")
            }
            # 동일 날짜 동일 도메인 중복 방지를 위해 upsert 권장
            self.client.table('keyword_ranking_history').upsert(payload).execute()
        except Exception as e:
            logger.error(f"Failed to save keyword ranking history: {e}")

    def get_weekly_stable_keywords(self, domain: str):
        """DB에 계산되어 저장된 주간 안정 인기 검색어(Stable)를 가져옵니다."""
        if not self.client or not self._db_available: return None
        try:
            res = self.client.table('popular_keywords_stable').select('items, period').eq('domain', domain).execute()
            if res.data:
                return res.data[0]
        except: pass
        return None

    def refresh_weekly_stable_keywords(self, domain: str):
        """최근 7일간의 순위 데이터를 합산하여 순위가 가장 안정적인 Top 10을 산출합니다."""
        if not self.client or not self._db_available: return
        from datetime import datetime, timedelta
        from collections import Counter
        
        try:
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            res = self.client.table('keyword_ranking_history') \
                .select('ranking_data') \
                .eq('domain', domain) \
                .gte('created_at', seven_days_ago) \
                .execute()
            
            if not res.data: return
            
            # 가중치 계산 (1위: 10점, 2위: 9점 ... 10위: 1점)
            scores = Counter()
            for day in res.data:
                ranking_list = day.get('ranking_data', [])
                for item in ranking_list:
                    kw = item.get('keyword')
                    rank = item.get('rank', 10)
                    score = max(1, 11 - rank)
                    scores[kw] += score
            
            # 상위 10개 추출
            stable_top = []
            for kw, score in scores.most_common(10):
                stable_top.append(kw)
            
            if stable_top:
                period = f"{seven_days_ago} ~ {datetime.now().strftime('%Y-%m-%d')}"
                self.upsert_stable_keywords(domain, stable_top, period)
                logger.info(f"[Sync] {domain} 주간 통계 갱신 완료 ({len(stable_top)}개 키워드)")
                
        except Exception as e:
            logger.error(f"Failed to refresh weekly keywords for {domain}: {e}")
