#!/usr/bin/env python3
"""
Common utilities for Chatwoot utility scripts
"""

import os
import sys
import time
import logging
import requests
import pymysql
from functools import wraps
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3307')),
    'user': os.getenv('MYSQL_USER', 'sync_user'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE', 'pipedrive_chatwoot_sync'),
    'charset': 'utf8mb4'
}

CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')

BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50'))
RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', '10485760'))
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))

def setup_logging(script_name):
    """Set up structured logging with rotating file handlers"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger(script_name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f"{script_name}.log"),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_db_connection():
    """Get database connection"""
    return pymysql.connect(**DB_CONFIG)

def get_http_session():
    """Get HTTP session with connection pooling"""
    session = requests.Session()
    session.headers.update({'Api-Access-Token': CHATWOOT_API_KEY})
    
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=0
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    return session

def retry_with_backoff(max_attempts=None, base_delay=None):
    """Decorator for retry with exponential backoff"""
    if max_attempts is None:
        max_attempts = RETRY_ATTEMPTS
    if base_delay is None:
        base_delay = RETRY_DELAY
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    if attempt == max_attempts - 1:
                        logger.error(f"Final attempt failed for {func.__name__}: {e}")
                        raise
                    
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                except Exception as e:
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise
            
            return None
        return wrapper
    return decorator

def validate_api_token(session, logger):
    """Validate Chatwoot API token permissions"""
    try:
        response = session.get(f"{CHATWOOT_BASE_URL}/profile", timeout=30)
        if response.status_code == 200:
            logger.info("✅ API token validation successful")
            return True
        else:
            logger.error(f"❌ API token validation failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ API token validation error: {e}")
        return False

def process_in_batches(items, batch_size=None):
    """Process items in batches"""
    if batch_size is None:
        batch_size = BATCH_SIZE
    
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

class ProgressReporter:
    """Progress reporting utility"""
    
    def __init__(self, total_items, logger, operation_name="Processing"):
        self.total_items = total_items
        self.logger = logger
        self.operation_name = operation_name
        self.processed = 0
        self.successful = 0
        self.failed = 0
        self.skipped = 0
    
    def update(self, success=False, failed=False, skipped=False):
        """Update progress counters"""
        self.processed += 1
        if success:
            self.successful += 1
        elif failed:
            self.failed += 1
        elif skipped:
            self.skipped += 1
    
    def log_progress(self, item_name="item"):
        """Log current progress"""
        percentage = (self.processed / self.total_items) * 100 if self.total_items > 0 else 0
        self.logger.info(f"[{self.processed}/{self.total_items}] ({percentage:.1f}%) {self.operation_name}")
    
    def log_summary(self):
        """Log final summary"""
        self.logger.info(f"\n✅ {self.operation_name} Summary:")
        self.logger.info(f"   Total processed: {self.processed}")
        self.logger.info(f"   Successful: {self.successful}")
        self.logger.info(f"   Failed: {self.failed}")
        self.logger.info(f"   Skipped: {self.skipped}")
