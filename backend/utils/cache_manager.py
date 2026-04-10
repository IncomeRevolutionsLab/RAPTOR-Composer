import time
import hashlib
import json
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    간단한 인메모리 캐시 관리자.
    동일한 분야 요청에 대한 재수집을 방지합니다.
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._store: dict[str, dict] = {}

    def _make_key(self, domain: str, source: str) -> str:
        raw = f"{domain}:{source}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def get(self, domain: str, source: str) -> Optional[Any]:
        key = self._make_key(domain, source)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry["created_at"] > self.ttl:
            del self._store[key]
            logger.debug(f"[Cache] 만료됨 | domain={domain} source={source}")
            return None
        logger.debug(f"[Cache] 히트 | domain={domain} source={source}")
        return entry["data"]

    def set(self, domain: str, source: str, data: Any):
        key = self._make_key(domain, source)
        self._store[key] = {
            "created_at": time.time(),
            "data": data,
        }
        logger.debug(f"[Cache] 저장 | domain={domain} source={source}")

    def invalidate(self, domain: str, source: str):
        key = self._make_key(domain, source)
        if key in self._store:
            del self._store[key]

    def clear_all(self):
        self._store.clear()
        logger.info("[Cache] 전체 캐시 초기화")

    def stats(self) -> dict:
        now = time.time()
        valid = sum(1 for e in self._store.values() if now - e["created_at"] <= self.ttl)
        return {
            "total_entries": len(self._store),
            "valid_entries": valid,
            "expired_entries": len(self._store) - valid,
            "ttl_seconds": self.ttl,
        }


# 싱글톤 인스턴스
cache = CacheManager()
