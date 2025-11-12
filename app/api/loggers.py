 # Code generated via "Slingshot" 
import logging
import sys
import uuid
from typing import Optional
from datetime import datetime
from pathlib import Path

class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID to log records"""
    
    def filter(self, record):
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = 'no-correlation-id'
        return True

class LoggerConfig:
    """Centralized logging configuration"""
    
    def __init__(self, log_level: str = "INFO", log_file: str = "app.log"):
        self.log_level = getattr(logging, log_level.upper())
        self.log_file = log_file
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure structured logging with correlation IDs"""
        
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Custom formatter with correlation ID
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(correlation_id)s]'
        )
        
        # File handler
        file_handler = logging.FileHandler(log_dir / self.log_file)
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(CorrelationFilter())
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(CorrelationFilter())
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear existing handlers to avoid duplicates
        root_logger.handlers.clear()
        
        # Add our handlers
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

class AppLogger:
    """Application logger with correlation ID support"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.correlation_id: Optional[str] = None
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for this logger instance"""
        self.correlation_id = correlation_id
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method with correlation ID"""
        extra = kwargs.get('extra', {})
        extra['correlation_id'] = self.correlation_id or 'unknown'
        kwargs['extra'] = extra
        self.logger.log(level, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with correlation ID"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with correlation ID"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with correlation ID"""
        self._log(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with correlation ID"""
        self._log(logging.DEBUG, message, **kwargs)

# Global logger configuration
logger_config = LoggerConfig()

def get_logger(name: str) -> AppLogger:
    """Factory function to create logger instances"""
    return AppLogger(name)

def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())