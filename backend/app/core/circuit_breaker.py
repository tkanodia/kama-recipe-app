"""Per-service circuit breakers to protect against cascading failures from external APIs."""

import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ServiceCircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            if time.monotonic() - self._last_failure_time >= self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = None

    def reset(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = None


ocr_breaker = ServiceCircuitBreaker("ocr", failure_threshold=3, reset_timeout=120)
whisper_breaker = ServiceCircuitBreaker("whisper", failure_threshold=3, reset_timeout=120)
llm_breaker = ServiceCircuitBreaker("llm", failure_threshold=5, reset_timeout=60)
youtube_breaker = ServiceCircuitBreaker("youtube", failure_threshold=5, reset_timeout=120)
social_breaker = ServiceCircuitBreaker("social", failure_threshold=5, reset_timeout=120)
