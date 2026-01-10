"""
Logging and error handling utilities for DMARC Lens.

This module provides centralized logging configuration and error handling
utilities for the DMARC analysis platform.
"""

import logging
import sys
import json
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path
import os


class DMARCLensFormatter(logging.Formatter):
    """Custom formatter for DMARC Lens logging."""
    
    def __init__(self, include_json: bool = False):
        """
        Initialize the formatter.
        
        Args:
            include_json: Whether to format logs as JSON
        """
        self.include_json = include_json
        
        if include_json:
            super().__init__()
        else:
            fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            super().__init__(fmt, datefmt='%Y-%m-%d %H:%M:%S')
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record."""
        if self.include_json:
            return self._format_json(record)
        else:
            return super().format(record)
    
    def _format_json(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)


def setup_logging(
    level: Union[str, int] = logging.INFO,
    log_file: Optional[Path] = None,
    json_format: bool = False,
    include_console: bool = True
) -> logging.Logger:
    """
    Set up logging configuration for DMARC Lens.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        json_format: Whether to use JSON formatting
        include_console: Whether to include console output
        
    Returns:
        Configured logger instance
    """
    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    
    # Get root logger for dmarc_lens
    logger = logging.getLogger('dmarc_lens')
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = DMARCLensFormatter(include_json=json_format)
    
    # Add console handler if requested
    if include_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Add file handler if requested
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def setup_lambda_logging(json_format: bool = True) -> logging.Logger:
    """
    Set up logging specifically for AWS Lambda functions.
    
    Args:
        json_format: Whether to use JSON formatting (recommended for CloudWatch)
        
    Returns:
        Configured logger instance
    """
    # Lambda environment typically uses INFO level
    level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    return setup_logging(
        level=level,
        json_format=json_format,
        include_console=True,
        log_file=None  # Lambda uses CloudWatch, not files
    )


class ErrorHandler:
    """Centralized error handling for DMARC Lens operations."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize error handler.
        
        Args:
            logger: Logger instance to use for error reporting
        """
        self.logger = logger or logging.getLogger('dmarc_lens.error_handler')
    
    def handle_parsing_error(
        self, 
        error: Exception, 
        context: Dict[str, Any],
        reraise: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Handle parsing-related errors.
        
        Args:
            error: The exception that occurred
            context: Context information about the error
            reraise: Whether to re-raise the exception
            
        Returns:
            Error information dictionary if not re-raising
        """
        error_info = {
            'error_type': 'parsing_error',
            'error_class': error.__class__.__name__,
            'error_message': str(error),
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.error(
            f"Parsing error: {error}",
            extra={'extra_fields': error_info},
            exc_info=True
        )
        
        if reraise:
            raise error
        
        return error_info
    
    def handle_validation_error(
        self, 
        error: Exception, 
        context: Dict[str, Any],
        reraise: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Handle validation-related errors.
        
        Args:
            error: The exception that occurred
            context: Context information about the error
            reraise: Whether to re-raise the exception
            
        Returns:
            Error information dictionary if not re-raising
        """
        error_info = {
            'error_type': 'validation_error',
            'error_class': error.__class__.__name__,
            'error_message': str(error),
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.error(
            f"Validation error: {error}",
            extra={'extra_fields': error_info},
            exc_info=True
        )
        
        if reraise:
            raise error
        
        return error_info
    
    def handle_processing_error(
        self, 
        error: Exception, 
        context: Dict[str, Any],
        reraise: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Handle general processing errors.
        
        Args:
            error: The exception that occurred
            context: Context information about the error
            reraise: Whether to re-raise the exception
            
        Returns:
            Error information dictionary if not re-raising
        """
        error_info = {
            'error_type': 'processing_error',
            'error_class': error.__class__.__name__,
            'error_message': str(error),
            'context': context,
            'timestamp': datetime.utcnow().isoformat(),
            'traceback': traceback.format_exc()
        }
        
        self.logger.error(
            f"Processing error: {error}",
            extra={'extra_fields': error_info},
            exc_info=True
        )
        
        if reraise:
            raise error
        
        return error_info
    
    def log_operation_start(self, operation: str, context: Dict[str, Any]) -> None:
        """
        Log the start of an operation.
        
        Args:
            operation: Name of the operation
            context: Context information
        """
        self.logger.info(
            f"Starting operation: {operation}",
            extra={'extra_fields': {'operation': operation, 'context': context}}
        )
    
    def log_operation_success(self, operation: str, result: Dict[str, Any]) -> None:
        """
        Log successful completion of an operation.
        
        Args:
            operation: Name of the operation
            result: Result information
        """
        self.logger.info(
            f"Operation completed successfully: {operation}",
            extra={'extra_fields': {'operation': operation, 'result': result}}
        )
    
    def log_operation_failure(self, operation: str, error: Exception) -> None:
        """
        Log failure of an operation.
        
        Args:
            operation: Name of the operation
            error: The exception that caused the failure
        """
        self.logger.error(
            f"Operation failed: {operation} - {error}",
            extra={'extra_fields': {'operation': operation}},
            exc_info=True
        )


def create_context_logger(base_logger: logging.Logger, context: Dict[str, Any]) -> logging.LoggerAdapter:
    """
    Create a logger adapter that includes context in all log messages.
    
    Args:
        base_logger: Base logger instance
        context: Context information to include in logs
        
    Returns:
        Logger adapter with context
    """
    class ContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            if 'extra_fields' not in kwargs['extra']:
                kwargs['extra']['extra_fields'] = {}
            kwargs['extra']['extra_fields'].update(self.extra)
            return msg, kwargs
    
    return ContextAdapter(base_logger, context)


def log_performance(logger: logging.Logger, operation: str):
    """
    Decorator to log performance metrics for operations.
    
    Args:
        logger: Logger instance
        operation: Name of the operation being measured
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = func(*args, **kwargs)
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                logger.info(
                    f"Performance: {operation} completed in {duration:.3f}s",
                    extra={
                        'extra_fields': {
                            'operation': operation,
                            'duration_seconds': duration,
                            'start_time': start_time.isoformat(),
                            'end_time': end_time.isoformat()
                        }
                    }
                )
                
                return result
                
            except Exception as e:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                logger.error(
                    f"Performance: {operation} failed after {duration:.3f}s",
                    extra={
                        'extra_fields': {
                            'operation': operation,
                            'duration_seconds': duration,
                            'start_time': start_time.isoformat(),
                            'end_time': end_time.isoformat(),
                            'error': str(e)
                        }
                    },
                    exc_info=True
                )
                
                raise
        
        return wrapper
    return decorator


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """
    Get the global error handler instance.
    
    Returns:
        Global ErrorHandler instance
    """
    global _global_error_handler
    
    if _global_error_handler is None:
        logger = logging.getLogger('dmarc_lens')
        _global_error_handler = ErrorHandler(logger)
    
    return _global_error_handler


def set_error_handler(error_handler: ErrorHandler) -> None:
    """
    Set the global error handler instance.
    
    Args:
        error_handler: ErrorHandler instance to use globally
    """
    global _global_error_handler
    _global_error_handler = error_handler