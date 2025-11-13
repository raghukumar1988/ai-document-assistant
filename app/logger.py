import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
from datetime import datetime

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add log level
        log_record['level'] = record.levelname
        
        # Add logger name
        log_record['logger'] = record.name
        
        # Add file and line number
        log_record['file'] = record.pathname
        log_record['line'] = record.lineno

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup logger with both console and file handlers
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Console Handler (Human-readable format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # File Handler - JSON format (for log aggregation tools)
    json_file_handler = RotatingFileHandler(
        LOGS_DIR / "app.json.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    json_file_handler.setLevel(level)
    json_formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    json_file_handler.setFormatter(json_formatter)
    
    # File Handler - Text format (human-readable)
    text_file_handler = RotatingFileHandler(
        LOGS_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    text_file_handler.setLevel(level)
    text_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    text_file_handler.setFormatter(text_formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(json_file_handler)
    logger.addHandler(text_file_handler)
    
    return logger

# Create default logger
logger = setup_logger("docuchat")