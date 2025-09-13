import os
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Any, Optional

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        if hasattr(record, 'extra_data'):
            log_entry['extra'] = getattr(record, 'extra_data')
            
        return json.dumps(log_entry)

def setup_logger(name: str, log_file: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Set up structured logging with rotation
    
    Args:
        name: Logger name
        log_file: Log file name (without path)
        level: Logging level
    """
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        file_path = os.path.join(log_dir, log_file)
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    
    return logger

def log_with_extra(logger: logging.Logger, level: int, message: str, extra_data: Optional[Dict[str, Any]] = None):
    """Log message with extra structured data"""
    if extra_data:
        logger.log(level, message, extra={'extra_data': extra_data})
    else:
        logger.log(level, message)

def get_sync_logger() -> logging.Logger:
    """Get logger for sync operations"""
    return setup_logger('sync', 'sync.log')

def get_monitor_logger() -> logging.Logger:
    """Get logger for monitoring operations"""
    return setup_logger('monitor', 'monitor.log')

def get_alert_logger() -> logging.Logger:
    """Get logger for alert operations"""
    return setup_logger('alerts', 'alerts.log')

def get_cleanup_logger() -> logging.Logger:
    """Get logger for cleanup operations"""
    return setup_logger('cleanup', 'cleanup.log')
