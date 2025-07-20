import logging
import os
from rich.logging import RichHandler
from logging.handlers import RotatingFileHandler

# Store whether logging has been configured to avoid duplicate setup
_logging_configured = False


def setup_logging(
    console_level="INFO",
    file_level="DEBUG",
    log_file=None,
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5,
):
    """
    Configure logging with rich console output and optional file logging.

    Args:
        console_level (str): Console log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        file_level (str): File log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file (str): Path to log file, or None to disable file logging.
        max_bytes (int): Max size of log file before rotation.
        backup_count (int): Number of backup log files to keep.
    """
    global _logging_configured
    if _logging_configured:
        return

    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Root logger captures all levels

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Rich console handler
    console_handler = RichHandler(
        rich_tracebacks=True,  # Show rich-formatted tracebacks
        show_time=True,
        show_level=True,
        show_path=True,
        markup=True,  # Enable [bold], [red], etc. in log messages
    )
    console_handler.setLevel(getattr(logging, console_level))
    console_formatter = logging.Formatter(
        "%(name)s: %(message)s"  # RichHandler adds time/level automatically
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (if enabled)
    if log_file:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, file_level))
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    _logging_configured = True


def get_logger(name):
    """
    Get a logger for a specific module, ensuring logging is configured.

    Args:
        name (str): Name of the logger (e.g., __name__).

    Returns:
        logging.Logger: Configured logger instance.
    """
    if not _logging_configured:
        console_level = os.getenv("LOG_LEVEL", "INFO")
        setup_logging(console_level=console_level)
    return logging.getLogger(name)
