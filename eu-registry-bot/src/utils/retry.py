"""
Retry logic and error recovery utilities
"""

import time
import functools
from typing import Callable, Optional, Type, Tuple, Any
from enum import Enum

from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)

from ..core.logger import setup_logger

logger = setup_logger(__name__)


class RetryStrategy(Enum):
    """Retry backoff strategies."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


# Default retryable exceptions
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
)


def calculate_delay(
    attempt: int,
    base_delay: float,
    strategy: RetryStrategy,
    max_delay: float = 60.0,
) -> float:
    """
    Calculate delay before next retry.

    Args:
        attempt: Current attempt number (1-based)
        base_delay: Base delay in seconds
        strategy: Backoff strategy
        max_delay: Maximum delay cap

    Returns:
        Delay in seconds
    """
    if strategy == RetryStrategy.FIXED:
        delay = base_delay
    elif strategy == RetryStrategy.LINEAR:
        delay = base_delay * attempt
    elif strategy == RetryStrategy.EXPONENTIAL:
        delay = base_delay * (2 ** (attempt - 1))
    else:
        delay = base_delay

    return min(delay, max_delay)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    exceptions: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
):
    """
    Decorator for retrying functions on failure.

    Args:
        max_attempts: Maximum number of attempts
        delay: Base delay between retries
        strategy: Backoff strategy
        exceptions: Tuple of exception types to retry on
        on_retry: Callback called on each retry

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        wait_time = calculate_delay(attempt, delay, strategy)
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {wait_time:.1f}s..."
                        )

                        if on_retry:
                            on_retry(attempt, e)

                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed. Last error: {e}"
                        )

            raise last_exception

        return wrapper
    return decorator


class RetryExecutor:
    """
    Class-based retry executor with more control.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        exceptions: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
    ):
        """
        Initialize retry executor.

        Args:
            max_attempts: Maximum attempts
            base_delay: Base delay between retries
            strategy: Backoff strategy
            exceptions: Retryable exceptions
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.strategy = strategy
        self.exceptions = exceptions
        self._on_retry_callback: Optional[Callable] = None
        self._on_success_callback: Optional[Callable] = None
        self._on_failure_callback: Optional[Callable] = None

    def on_retry(self, callback: Callable[[int, Exception], None]) -> "RetryExecutor":
        """Set retry callback."""
        self._on_retry_callback = callback
        return self

    def on_success(self, callback: Callable[[Any, int], None]) -> "RetryExecutor":
        """Set success callback."""
        self._on_success_callback = callback
        return self

    def on_failure(self, callback: Callable[[Exception], None]) -> "RetryExecutor":
        """Set failure callback."""
        self._on_failure_callback = callback
        return self

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all attempts fail
        """
        last_exception = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                result = func(*args, **kwargs)

                if self._on_success_callback:
                    self._on_success_callback(result, attempt)

                return result

            except self.exceptions as e:
                last_exception = e

                if attempt < self.max_attempts:
                    wait_time = calculate_delay(
                        attempt, self.base_delay, self.strategy
                    )

                    logger.warning(
                        f"Attempt {attempt}/{self.max_attempts} failed: {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )

                    if self._on_retry_callback:
                        self._on_retry_callback(attempt, e)

                    time.sleep(wait_time)

        if self._on_failure_callback:
            self._on_failure_callback(last_exception)

        raise last_exception


class CircuitBreaker:
    """
    Circuit breaker pattern for preventing repeated failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        if self._state == "open":
            # Check if recovery timeout has passed
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "half-open"
                return False
            return True
        return False

    def record_success(self) -> None:
        """Record a successful operation."""
        self._failures = 0
        self._state = "closed"
        logger.debug("Circuit breaker: recorded success, circuit closed")

    def record_failure(self) -> None:
        """Record a failed operation."""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._failures >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                f"Circuit breaker: opened after {self._failures} failures. "
                f"Recovery in {self.recovery_timeout}s"
            )

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self._failures = 0
        self._last_failure_time = None
        self._state = "closed"
        logger.info("Circuit breaker: manually reset to closed state")

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "state": self._state,
            "failures": self._failures,
            "threshold": self.failure_threshold,
            "last_failure": self._last_failure_time,
            "recovery_timeout": self.recovery_timeout,
        }

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            RuntimeError: If circuit is open
        """
        if self.is_open:
            raise RuntimeError(
                f"Circuit breaker is open. Wait {self.recovery_timeout}s before retrying."
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
