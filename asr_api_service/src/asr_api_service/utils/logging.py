"""Logging configuration utilities."""

import logging
import sys
from pathlib import Path
from typing import Optional

import structlog
from structlog.typing import FilteringBoundLogger

from asr_api_service.config import settings, LogLevel, LogFormat


def setup_logging() -> None:
    """Setup structured logging for the application."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.value),
    )
    
    # Configure structlog processors
    processors = [
        # Add log level and timestamp
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="ISO"),
    ]
    
    # Add call site info in development
    if settings.is_development:
        processors.append(structlog.processors.CallsiteParameterAdder())
    
    # Choose output format
    if settings.log_format == LogFormat.JSON:
        processors.extend([
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ])
    else:
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True)
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Setup file logging if specified
    if settings.log_file:
        setup_file_logging()


def setup_file_logging() -> None:
    """Setup file logging with rotation."""
    try:
        from logging.handlers import RotatingFileHandler
        
        # Ensure log directory exists
        log_file = Path(settings.log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create file handler
        handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=_parse_size(settings.log_rotation),
            backupCount=5,
        )
        
        # Set format
        if settings.log_format == LogFormat.JSON:
            formatter = logging.Formatter('%(message)s')
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        handler.setFormatter(formatter)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        
    except Exception as e:
        logger = structlog.get_logger(__name__)
        logger.warning("Failed to setup file logging", error=str(e))


def _parse_size(size_str: str) -> int:
    """Parse size string like '100 MB' to bytes.
    
    Args:
        size_str: Size string with unit
        
    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()
    
    if size_str.endswith('KB'):
        return int(size_str[:-2].strip()) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2].strip()) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2].strip()) * 1024 * 1024 * 1024
    else:
        # Assume bytes
        return int(size_str)


def get_logger(name: str) -> FilteringBoundLogger:
    """Get a configured logger.
    
    Args:
        name: Logger name
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding logging context."""
    
    def __init__(self, logger: FilteringBoundLogger, **context):
        self.logger = logger
        self.context = context
        self.bound_logger: Optional[FilteringBoundLogger] = None
    
    def __enter__(self) -> FilteringBoundLogger:
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Context is automatically removed when logger goes out of scope
        pass


def log_function_call(logger: FilteringBoundLogger):
    """Decorator to log function calls.
    
    Args:
        logger: Logger to use
        
    Returns:
        Decorator function
    """
    def decorator(func):
        import functools
        import inspect
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Log function entry
            logger.debug(
                "Function called",
                function=func_name,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys()),
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.debug("Function completed", function=func_name)
                return result
            except Exception as e:
                logger.error(
                    "Function failed",
                    function=func_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Log function entry
            logger.debug(
                "Function called",
                function=func_name,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys()),
            )
            
            try:
                result = func(*args, **kwargs)
                logger.debug("Function completed", function=func_name)
                return result
            except Exception as e:
                logger.error(
                    "Function failed", 
                    function=func_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator