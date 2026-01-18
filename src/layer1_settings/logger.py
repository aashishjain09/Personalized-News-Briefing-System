"""Layer 1: Settings - Structured logging setup."""

import logging
import logging.config
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger
from pathlib import Path
from uuid import uuid4
from contextvars import ContextVar

# Context variable for request ID (thread-safe)
request_id_context: ContextVar[str] = ContextVar('request_id', default='')


class RequestIdFilter(logging.Filter):
    """Add request_id to all log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_context.get()
        if not request_id:
            request_id = str(uuid4())
        record.request_id = request_id
        return True


class JsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with timestamp."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name


def setup_logging(log_level: str = "INFO", config_path: Path = None):
    """
    Initialize structured logging with JSON format.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        config_path: Path to logging YAML config (optional)
    """
    # Create logs directory if not exists
    logs_dir = Path("./logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Add request ID filter to all handlers
    request_id_filter = RequestIdFilter()
    
    # Console handler (standard format during development)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(request_id_filter)
    
    # File handler (JSON format for parsing)
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=10485760,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(JsonFormatter())
    file_handler.addFilter(request_id_filter)
    
    # Error file handler (errors only, JSON format)
    error_file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "errors.log",
        maxBytes=10485760,
        backupCount=5
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(JsonFormatter())
    error_file_handler.addFilter(request_id_filter)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_file_handler)
    
    # Suppress verbose loggers
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def set_request_id(request_id: str):
    """Set request ID for current context."""
    request_id_context.set(request_id)


def get_request_id() -> str:
    """Get current request ID."""
    return request_id_context.get()


# Initialize logging on module import
setup_logging()
