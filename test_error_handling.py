#!/usr/bin/env python3
"""
Test script to verify robust error handling implementation
"""

import sys
import logging
from unittest.mock import patch, MagicMock
import requests
from dotenv import load_dotenv

sys.path.append('app')
from error_handling import (
    robust_api_request, RetryConfig, calculate_delay,
    PIPEDRIVE_CONFIG, CHATWOOT_CONFIG
)

load_dotenv()


def setup_test_logging():
    """Set up logging for tests"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)


def test_exponential_backoff():
    """Test exponential backoff calculation"""
    logger = setup_test_logging()
    logger.info("🧪 Testing exponential backoff calculation")

    config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=10.0, jitter=False)

    expected_delays = [1.0, 2.0, 4.0, 8.0, 10.0]  # Last one capped at max_delay

    for attempt in range(5):
        delay = calculate_delay(attempt, config)
        expected = expected_delays[attempt]
        logger.info(f"   Attempt {attempt}: delay={delay:.2f}s, expected={expected:.2f}s")
        assert abs(delay - expected) < 0.1, f"Delay mismatch: got {delay}, expected {expected}"

    logger.info("✅ Exponential backoff calculation test passed")


def test_retry_on_status_codes():
    """Test retry behavior on specific status codes"""
    logger = setup_test_logging()
    logger.info("🧪 Testing retry on status codes")

    config = RetryConfig(max_retries=2, base_delay=0.1, retry_on_status_codes=(429, 500))

    mock_response = MagicMock()
    mock_response.status_code = 429

    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            mock_response.status_code = 429
            return mock_response
        else:
            mock_response.status_code = 200
            return mock_response

    with patch('requests.get', side_effect=mock_get):
        response = robust_api_request(
            requests.get,
            "http://test.com",
            config=config,
            logger=logger,
            operation_name="Test retry"
        )

        assert call_count == 3, f"Expected 3 calls, got {call_count}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    logger.info("✅ Retry on status codes test passed")


def test_retry_on_exceptions():
    """Test retry behavior on exceptions"""
    logger = setup_test_logging()
    logger.info("🧪 Testing retry on exceptions")

    config = RetryConfig(max_retries=2, base_delay=0.1)

    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise requests.exceptions.ConnectionError("Connection failed")
        else:
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

    with patch('requests.get', side_effect=mock_get):
        response = robust_api_request(
            requests.get,
            "http://test.com",
            config=config,
            logger=logger,
            operation_name="Test exception retry"
        )

        assert call_count == 3, f"Expected 3 calls, got {call_count}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    logger.info("✅ Retry on exceptions test passed")


def test_max_retries_exhausted():
    """Test behavior when max retries are exhausted"""
    logger = setup_test_logging()
    logger.info("🧪 Testing max retries exhausted")

    config = RetryConfig(max_retries=2, base_delay=0.1)

    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise requests.exceptions.ConnectionError("Connection failed")

    with patch('requests.get', side_effect=mock_get):
        try:
            robust_api_request(
                requests.get,
                "http://test.com",
                config=config,
                logger=logger,
                operation_name="Test exhausted retries"
            )
            assert False, "Expected exception to be raised"
        except requests.exceptions.ConnectionError:
            assert call_count == 3, f"Expected 3 calls, got {call_count}"

    logger.info("✅ Max retries exhausted test passed")


def test_immediate_success():
    """Test immediate success (no retries needed)"""
    logger = setup_test_logging()
    logger.info("🧪 Testing immediate success")

    config = RetryConfig(max_retries=3, base_delay=0.1)

    mock_response = MagicMock()
    mock_response.status_code = 200

    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_response

    with patch('requests.get', side_effect=mock_get):
        response = robust_api_request(
            requests.get,
            "http://test.com",
            config=config,
            logger=logger,
            operation_name="Test immediate success"
        )

        assert call_count == 1, f"Expected 1 call, got {call_count}"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    logger.info("✅ Immediate success test passed")


def test_config_validation():
    """Test that predefined configs are valid"""
    logger = setup_test_logging()
    logger.info("🧪 Testing predefined configurations")

    configs = {
        'PIPEDRIVE_CONFIG': PIPEDRIVE_CONFIG,
        'CHATWOOT_CONFIG': CHATWOOT_CONFIG
    }

    for name, config in configs.items():
        assert config.max_retries > 0, f"{name}: max_retries must be > 0"
        assert config.base_delay > 0, f"{name}: base_delay must be > 0"
        assert config.max_delay >= config.base_delay, f"{name}: max_delay must be >= base_delay"
        assert config.exponential_base > 1, f"{name}: exponential_base must be > 1"
        assert len(config.retry_on_status_codes) > 0, f"{name}: must have retry status codes"
        assert len(config.retry_on_exceptions) > 0, f"{name}: must have retry exceptions"
        logger.info(f"   ✅ {name} configuration is valid")

    logger.info("✅ Configuration validation test passed")


def main():
    """Run all error handling tests"""
    logger = setup_test_logging()

    logger.info("🚀 Starting Error Handling Tests")
    logger.info("=" * 60)

    tests = [
        test_exponential_backoff,
        test_retry_on_status_codes,
        test_retry_on_exceptions,
        test_max_retries_exhausted,
        test_immediate_success,
        test_config_validation
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            logger.error(f"❌ Test {test.__name__} failed: {e}")
            failed += 1

    logger.info("=" * 60)
    logger.info(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        logger.info("🎉 All error handling tests passed!")
        return True
    else:
        logger.error("❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
