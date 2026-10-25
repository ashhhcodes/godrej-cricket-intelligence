"""
Logging configuration with sensitive credential masking.
Ensures API keys and database passwords never leak into stdout or log files.
"""

import logging
import re
import sys
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """
    Regex filter to scrub API keys, query parameters, and database passwords from logs.
    """
    PATTERNS = [
        (re.compile(r"(apikey=)[^&\s]+", re.IGNORECASE), r"\1[MASKED_API_KEY]"),
        (re.compile(r"(password=)[^&\s]+", re.IGNORECASE), r"\1[MASKED_PASSWORD]"),
        (re.compile(r"(:)[^@/:]+(@)", re.IGNORECASE), r"\1[MASKED_CREDENTIAL]\2"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        if record.args:
            args_list = list(record.args) if isinstance(record.args, tuple) else record.args
            if isinstance(args_list, list):
                for i, arg in enumerate(args_list):
                    if isinstance(arg, str):
                        for pattern, replacement in self.PATTERNS:
                            args_list[i] = pattern.sub(replacement, arg)
                record.args = tuple(args_list)
        return True


def setup_logger(name: str = "godrej_cricket", log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Sets up a structured logger equipped with sensitive data masking.
    """
    logger = logging.getLogger(name)
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers if re-initialized
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    sensitive_filter = SensitiveDataFilter()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    logger.addHandler(console_handler)

    # File Handler (Optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.addFilter(sensitive_filter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Failed to initialize file logger at {log_file}: {e}")

    return logger
