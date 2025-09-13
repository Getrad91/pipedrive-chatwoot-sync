"""
Robust error handling utilities for API requests with retries and exponential backoff
"""

import time
import random
import logging
import requests
from typing import Optional, Callable
from functools import wraps


class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on_status_codes: tuple = (429, 500, 502, 503, 504),
        retry_on_exceptions: tuple = (requests.exceptions.RequestException,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on_status_codes = retry_on_status_codes
        self.retry_on_exceptions = retry_on_exceptions


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for exponential backoff with jitter"""
    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


def robust_api_request(
    func: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    logger: Optional[logging.Logger] = None,
    operation_name: str = "API request",
    **kwargs
) -> requests.Response:
    """
    Execute an API request with robust error handling, retries, and exponential backoff

    Args:
        func: The requests function to call (requests.get, requests.post, etc.)
        *args: Positional arguments for the requests function
        config: RetryConfig instance for retry behavior
        logger: Logger instance for logging retry attempts
        operation_name: Human-readable name for the operation (for logging)
        **kwargs: Keyword arguments for the requests function

    Returns:
        requests.Response: The successful response

    Raises:
        requests.exceptions.RequestException: If all retries are exhausted
    """
    if config is None:
        config = RetryConfig()

    if logger is None:
        logger = logging.getLogger(__name__)

    last_exception = None
    last_response = None

    for attempt in range(config.max_retries + 1):
        try:
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 30

            response = func(*args, **kwargs)

            if response.status_code in config.retry_on_status_codes:
                last_response = response

                if attempt < config.max_retries:
                    delay = calculate_delay(attempt, config)
                    logger.warning(
                        f"{operation_name} failed with status {response.status_code} "
                        f"(attempt {attempt + 1}/{config.max_retries + 1}). "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"{operation_name} failed after {config.max_retries + 1} attempts. "
                        f"Final status: {response.status_code}"
                    )
                    response.raise_for_status()

            if attempt > 0:
                logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")

            return response
        except config.retry_on_exceptions as e:
            last_exception = e

            if attempt < config.max_retries:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    f"{operation_name} failed with {type(e).__name__}: {str(e)} "
                    f"(attempt {attempt + 1}/{config.max_retries + 1}). "
                    f"Retrying in {delay:.2f} seconds..."
                )
                time.sleep(delay)
                continue
            else:
                logger.error(
                    f"{operation_name} failed after {config.max_retries + 1} attempts. "
                    f"Final error: {type(e).__name__}: {str(e)}"
                )
                raise

    if last_response is not None:
        last_response.raise_for_status()
    if last_exception is not None:
        raise last_exception


def retry_on_failure(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None
):
    """
    Decorator for adding retry logic to functions

    Args:
        config: RetryConfig instance for retry behavior
        operation_name: Human-readable name for the operation (for logging)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if config is None:
                retry_config = RetryConfig()
            else:
                retry_config = config

            op_name = operation_name or f"{func.__name__}"
            logger = logging.getLogger(func.__module__)

            last_exception = None

            for attempt in range(retry_config.max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except retry_config.retry_on_exceptions as e:
                    last_exception = e

                    if attempt < retry_config.max_retries:
                        delay = calculate_delay(attempt, retry_config)
                        logger.warning(
                            f"{op_name} failed with {type(e).__name__}: {str(e)} "
                            f"(attempt {attempt + 1}/{retry_config.max_retries + 1}). "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"{op_name} failed after {retry_config.max_retries + 1} attempts. "
                            f"Final error: {type(e).__name__}: {str(e)}"
                        )
                        raise

            if last_exception is not None:
                raise last_exception

        return wrapper
    return decorator


PIPEDRIVE_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=2.0,
    max_delay=30.0,
    retry_on_status_codes=(429, 500, 502, 503, 504),
    retry_on_exceptions=(
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.RequestException
    )
)

CHATWOOT_CONFIG = RetryConfig(
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0,
    retry_on_status_codes=(429, 500, 502, 503, 504),
    retry_on_exceptions=(
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.RequestException
    )
)

DATABASE_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=0.5,
    max_delay=10.0,
    retry_on_exceptions=(Exception,)  # Catch all database-related exceptions
)
