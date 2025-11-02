"""
Structured logging configuration for chunking system.

This module provides logging utilities with document_id and phase context.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", use_context: bool = True) -> logging.Logger:
    """
    Configure structured logging for chunking system.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        use_context: If True, use context-aware format with document_id and phase.
                     If False, use simple format for CLI usage (default: True)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("chunking")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Create formatter based on use_context flag
    if use_context:
        # Structured format with document_id and phase (for ChunkingLogger)
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - [%(document_id)s] [%(phase)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # Simple format for CLI usage
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    return logger


class ChunkingLogger:
    """Logger with document and phase context"""

    def __init__(self, document_id: str, phase: str, level: str = "INFO"):
        """
        Initialize logger with context.

        Args:
            document_id: Document identifier
            phase: Processing phase (e.g., "structure_analysis", "boundary_detection")
            level: Logging level
        """
        self.logger = setup_logging(level)
        self.document_id = document_id
        self.phase = phase

    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method with context"""
        extra = {
            "document_id": self.document_id,
            "phase": self.phase
        }
        self.logger.log(level, message, extra=extra, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(logging.ERROR, message, **kwargs)

    def set_phase(self, phase: str):
        """Update phase context"""
        self.phase = phase


# Default logger instance
_default_logger: Optional[logging.Logger] = None


def get_logger(level: str = "INFO") -> logging.Logger:
    """
    Get default logger instance.

    Args:
        level: Logging level

    Returns:
        Logger instance
    """
    global _default_logger

    if _default_logger is None:
        _default_logger = setup_logging(level)

    return _default_logger
