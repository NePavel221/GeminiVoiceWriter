"""Logging system for Gemini Voice Writer."""
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from PyQt6.QtCore import QStandardPaths


def get_log_dir() -> str:
    """Get directory for log files."""
    app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    log_dir = os.path.join(app_data, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logger(name: str = "GeminiVoiceWriter") -> logging.Logger:
    """Setup and return application logger with file and console handlers."""
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Log format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (DEBUG and above, rotating)
    log_dir = get_log_dir()
    log_file = os.path.join(log_dir, "app.log")
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    logger.info(f"Logger initialized. Log file: {log_file}")
    return logger


# Global logger instance
_logger = None


def get_logger() -> logging.Logger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger
