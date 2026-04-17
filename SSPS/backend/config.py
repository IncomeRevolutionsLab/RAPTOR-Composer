import os
from dotenv import load_dotenv

# [.env 로드 경로를 절대 경로로 수정하여 인식률 강화]
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(env_path)

class Settings:
    def __init__(self):
        self.naver_client_id = os.getenv("NAVER_CLIENT_ID", "")
        self.naver_client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
        self.supabase_url = os.getenv("SUPABASE_URL", "")
        self.supabase_key = os.getenv("SUPABASE_KEY", "")
        self.cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", 3600))
        self.circuit_breaker_fail_max = int(os.getenv("CIRCUIT_BREAKER_FAIL_MAX", 3))
        self.circuit_breaker_reset_timeout = int(os.getenv("CIRCUIT_BREAKER_RESET_TIMEOUT", 60))
        self.scraper_timeout_seconds = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", 15))
        
        # 문자열을 boolean으로 파싱
        mock_env = str(os.getenv("USE_MOCK_DATA", "False")).lower()
        self.use_mock_data = mock_env in ("true", "1", "yes")
        
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = 5000
        
        # [v2.80] 알림 설정
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

settings = Settings()
