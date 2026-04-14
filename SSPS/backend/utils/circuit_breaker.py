import time
import threading
from enum import Enum
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"        # 정상 동작
    OPEN = "OPEN"            # 차단됨 (실패 누적)
    HALF_OPEN = "HALF_OPEN"  # 복구 시도 중


class CircuitBreaker:
    """
    회로 차단기 (Circuit Breaker) 패턴 구현.
    특정 소스에서 연속 실패가 발생하면 자동으로 차단하고,
    일정 시간 후 복구를 시도합니다.
    """

    def __init__(self, name: str, fail_max: int = 3, reset_timeout: int = 60):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.reset_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"[CircuitBreaker:{self.name}] HALF_OPEN - 복구 시도")
            return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def call(self, func: Callable, *args, fallback: Any = None, **kwargs) -> Any:
        """
        함수를 실행하고, 실패 시 Circuit Breaker를 관리합니다.
        Circuit이 OPEN 상태면 fallback 값을 즉시 반환합니다.
        """
        if self.state == CircuitState.OPEN:
            logger.warning(f"[CircuitBreaker:{self.name}] OPEN - 폴백 사용")
            return fallback

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            logger.warning(f"[CircuitBreaker:{self.name}] 실패 → 폴백 사용. 오류: {e}")
            return fallback

    async def async_call(self, coro_func: Callable, *args, fallback: Any = None, **kwargs) -> Any:
        """비동기 함수용 Circuit Breaker"""
        if self.state == CircuitState.OPEN:
            logger.warning(f"[CircuitBreaker:{self.name}] OPEN - 폴백 사용")
            return fallback

        try:
            result = await coro_func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            logger.warning(f"[CircuitBreaker:{self.name}] 실패 → 폴백 사용. 오류: {e}")
            return fallback

    def _on_success(self):
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info(f"[CircuitBreaker:{self.name}] CLOSED - 복구 성공")

    def _on_failure(self, error: Exception):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.fail_max:
                self._state = CircuitState.OPEN
                logger.error(
                    f"[CircuitBreaker:{self.name}] OPEN - "
                    f"{self.fail_max}회 실패. {self.reset_timeout}초 후 재시도. 오류: {error}"
                )

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
        }
