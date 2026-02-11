import logging
import logging.handlers
from pathlib import Path
import os


def setup_logging(log_dir: str = "logs", name: str = "analyst", console_output: bool = False) -> logging.Logger:
    """
    Configure logging to both console and file.
    
    Args:
        log_dir: Directory to store log files
        name: Logger name/prefix
        console_output: If True, also print logs to console. Default False (file only).
    
    Returns:
        logging.Logger: Configured logger instance
    """
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if logger.hasHandlers():
        return logger
    
    # File handler (rotating logs)
    log_file = log_path / f"{name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
    else:
        console_handler = None
    
    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    if console_handler:
        console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    if console_handler:
        logger.addHandler(console_handler)
    
    return logger
