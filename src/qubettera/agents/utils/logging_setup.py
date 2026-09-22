"""
Central logging setup for the entire agent framework.
Logs go to both console (INFO+) and a timestamped file (DEBUG+).
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    log_dir: str = "logs",
    log_prefix: str = "agent_framework",
) -> logging.Logger:
    """
    Configure the root logger with console and file handlers.

    Args:
        console_level: Minimum level for console output (e.g., "INFO", "DEBUG")
        file_level: Minimum level for file output (e.g., "DEBUG", "INFO")
        log_dir: Directory to store log files
        log_prefix: Prefix for log filenames

    Returns:
        The configured root logger
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = log_path / f"{log_prefix}_{timestamp}.log"

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything

    # Remove existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # ----- Console Handler (INFO and above) -----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # ----- File Handler (DEBUG and above) -----
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(getattr(logging, file_level.upper()))
    file_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    # Log startup info
    root_logger.info(f"Log file: {log_filename}")
    root_logger.info(f"Console level: {console_level.upper()}, File level: {file_level.upper()}")
    root_logger.info(f"Agent framework logging initialized")

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    """
    return logging.getLogger(name)