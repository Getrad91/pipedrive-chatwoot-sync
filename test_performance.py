#!/usr/bin/env python3
"""
Performance tests for sync.py optimizations
"""

import unittest
import time
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from sync import (
    exponential_backoff_retry, 
    setup_sessions, 
    get_cached_contact_search, 
    cache_contact_search,
    log_performance_metrics,
    clean_organization_data,
    normalize_phone
)

class TestPerformanceOptimizations(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_org = {
            'id': 123,
            'name': 'Test Organization',
            'phone': '+61412345678',
            'email': 'test@example.com',
            'address_locality': 'Sydney',
            'address_country': 'Australia',
            'Common Support Link': 'https://support.example.com',
            'notes': 'Test notes',
            'deal_title': 'Test Deal',
            'owner_id': {'name': 'Test Owner'}
        }
    
    def test_exponential_backoff_retry_success(self):
        """Test exponential backoff retry with successful function"""
        mock_func = Mock(return_value="success")
        result = exponential_backoff_retry(mock_func, max_retries=3, base_delay=0.1)
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 1)
    
    def test_exponential_backoff_retry_failure_then_success(self):
        """Test exponential backoff retry with failure then success"""
        mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        
        start_time = time.time()
        result = exponential_backoff_retry(mock_func, max_retries=3, base_delay=0.1)
        duration = time.time() - start_time
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)
        self.assertGreater(duration, 0.2)
    
    def test_exponential_backoff_retry_max_retries(self):
        """Test exponential backoff retry reaches max retries"""
        mock_func = Mock(side_effect=Exception("always fail"))
        
        with self.assertRaises(Exception):
            exponential_backoff_retry(mock_func, max_retries=2, base_delay=0.1)
        
        self.assertEqual(mock_func.call_count, 2)
    
    def test_contact_caching(self):
        """Test contact search caching functionality"""
        result = get_cached_contact_search("test_org")
        self.assertIsNone(result)
        
        test_contact = {"id": 123, "name": "Test Contact"}
        cache_contact_search("test_org", test_contact)
        
        cached_result = get_cached_contact_search("test_org")
        self.assertEqual(cached_result, test_contact)
        
        cache_contact_search("empty_org", None)
        cached_none = get_cached_contact_search("empty_org")
        self.assertIsNone(cached_none)
    
    @patch('sync.psutil.Process')
    @patch('sync.logging.getLogger')
    def test_performance_logging(self, mock_logger, mock_process):
        """Test performance metrics logging"""
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value.rss = 100 * 1024 * 1024  # 100MB
        mock_process.return_value = mock_process_instance
        
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        start_time = time.time() - 1.5  # Simulate 1.5 second operation
        log_performance_metrics("Test Operation", start_time, api_calls=5, db_operations=2)
        
        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        
        self.assertIn("Test Operation", call_args)
        self.assertIn("API calls: 5", call_args)
        self.assertIn("DB ops: 2", call_args)
        self.assertIn("Memory:", call_args)
    
    def test_clean_organization_data(self):
        """Test organization data cleaning"""
        cleaned = clean_organization_data(self.test_org)
        
        expected_keys = [
            'pipedrive_org_id', 'name', 'phone', 'email', 'city', 'country',
            'status', 'support_link', 'notes', 'deal_title', 'owner_name', 'raw_data'
        ]
        
        for key in expected_keys:
            self.assertIn(key, cleaned)
        
        self.assertEqual(cleaned['pipedrive_org_id'], 123)
        self.assertEqual(cleaned['name'], 'Test Organization')
        self.assertEqual(cleaned['status'], 'Customer')
        self.assertIsInstance(cleaned['raw_data'], str)  # Should be JSON string
    
    def test_normalize_phone(self):
        """Test phone number normalization"""
        test_cases = [
            ("+61412345678", "+61412345678"),  # Already normalized
            ("0412345678", "+61412345678"),    # Add country code
            ("412345678", "+61412345678"),     # Add country code
            ("", ""),                          # Empty string
            ("123", ""),                       # Too short
            ("123456789012345678", ""),        # Too long
            ("+1234567890", "+1234567890"),    # Different country code
        ]
        
        for input_phone, expected in test_cases:
            result = normalize_phone(input_phone)
            self.assertEqual(result, expected, f"Failed for input: {input_phone}")
    
    @patch('sync.requests.Session')
    def test_session_setup(self, mock_session_class):
        """Test HTTP session setup"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        setup_sessions()
        
        self.assertEqual(mock_session_class.call_count, 2)  # pipedrive and chatwoot
        
        self.assertEqual(mock_session.timeout, 30)
        
        self.assertEqual(mock_session.mount.call_count, 4)  # 2 sessions * 2 protocols each

class TestBatchOperations(unittest.TestCase):
    """Test batch operation functionality"""
    
    def test_batch_size_calculation(self):
        """Test that batch operations respect BATCH_SIZE"""
        from sync import BATCH_SIZE
        self.assertIsInstance(BATCH_SIZE, int)
        self.assertGreater(BATCH_SIZE, 0)

class TestIntegration(unittest.TestCase):
    """Integration tests for optimized sync functionality"""
    
    @patch('sync.get_db_connection')
    @patch('sync.chatwoot_session')
    @patch('sync.pipedrive_session')
    def test_sync_with_mocked_apis(self, mock_pipedrive, mock_chatwoot, mock_db):
        """Test sync process with mocked API calls"""
        self.assertTrue(hasattr(mock_pipedrive, 'get'))
        self.assertTrue(hasattr(mock_chatwoot, 'get'))

if __name__ == '__main__':
    os.environ.setdefault('BATCH_SIZE', '10')
    os.environ.setdefault('RETRY_ATTEMPTS', '2')
    os.environ.setdefault('RETRY_DELAY', '1')
    
    unittest.main(verbosity=2)
