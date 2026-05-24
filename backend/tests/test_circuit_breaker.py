"""Unit tests for circuit breaker."""

import time

from app.core.circuit_breaker import CircuitState, ServiceCircuitBreaker


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = ServiceCircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert not cb.is_open()

    def test_opens_after_threshold(self):
        cb = ServiceCircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_open()

    def test_success_resets(self):
        cb = ServiceCircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_timeout(self):
        cb = ServiceCircuitBreaker("test", failure_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_reset(self):
        cb = ServiceCircuitBreaker("test", failure_threshold=1)
        cb.record_failure()
        assert cb.is_open()
        cb.reset()
        assert cb.state == CircuitState.CLOSED
