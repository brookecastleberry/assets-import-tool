import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Optional

def setup_logging(name: str = 'create_targets', debug: bool = False) -> logging.Logger:
    """
    Setup logging - only produces logs when debug=True
    
    Args:
        name: Logger name
        debug: Enable enhanced DEBUG logging. If False, no logs are produced.
    """
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    if not debug:
        # No logging when debug is False - set level very high so nothing gets logged
        logger.setLevel(logging.CRITICAL + 1)  # Higher than any standard level
        # Add a null handler to prevent propagation
        logger.addHandler(logging.NullHandler())
        return logger
    
    # Debug mode enabled - setup enhanced logging
    log_path = os.environ.get('SNYK_LOG_PATH')
    
    if not log_path:
        print("Warning: SNYK_LOG_PATH environment variable not set. Debug logs will only be displayed on console.")
        logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        return logger
    
    # Setup file and console logging for debug mode
    os.makedirs(log_path, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_path, f'{name}_{timestamp}.log')
    
    logger.setLevel(logging.DEBUG)
    
    # Enhanced file handler with detailed formatting for debug
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler for debug output (less verbose than file)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    print(f"📝 Debug logging enabled - writing to: {log_file}")
    return logger

def log_error_with_context(logger: logging.Logger, message: str, exception: Optional[Exception] = None):
    """
    Log error with full context including stack trace
    
    Args:
        logger: Logger instance
        message: Error message
        exception: Exception to log (optional)
    """
    logger.error(f"❌ {message}")
    
    if exception:
        logger.error(f"Exception type: {type(exception).__name__}")
        logger.error(f"Exception message: {str(exception)}")
        logger.debug(f"Full stack trace:\n{traceback.format_exc()}")
    else:
        # Log current stack trace if no specific exception
        logger.debug(f"Stack trace:\n{''.join(traceback.format_stack())}")

def log_api_request(logger: logging.Logger, method: str, url: str, headers: Optional[dict] = None):
    """
    Log API request details (DEBUG level)
    
    Args:
        logger: Logger instance  
        method: HTTP method
        url: Request URL
        headers: Request headers (sensitive data will be masked)
    """
    logger.debug(f"🌐 API Request: {method} {url}")
    if headers:
        # Mask sensitive headers
        safe_headers = {}
        for key, value in headers.items():
            if key.lower() in ['authorization', 'x-snyk-token', 'private-token']:
                safe_headers[key] = f"{value[:10]}..." if len(value) > 10 else "***"
            else:
                safe_headers[key] = value
        logger.debug(f"   Headers: {safe_headers}")

def log_api_response(logger: logging.Logger, status_code: int, url: str, response_time: float, response_size: Optional[int] = None):
    """
    Log API response details (DEBUG level)
    
    Args:
        logger: Logger instance
        status_code: HTTP status code
        url: Request URL
        response_time: Response time in seconds
        response_size: Response body size in bytes (optional)
    """
    status_emoji = "✅" if 200 <= status_code < 300 else "⚠️" if 300 <= status_code < 500 else "❌"
    size_info = f", {response_size} bytes" if response_size else ""
    logger.debug(f"🌐 API Response: {status_emoji} {status_code} for {url} ({response_time:.2f}s{size_info})")

def log_retry_attempt(logger: logging.Logger, attempt: int, max_retries: int, url: str, delay: float):
    """
    Log retry attempt details
    
    Args:
        logger: Logger instance
        attempt: Current attempt number (1-based)
        max_retries: Maximum retry attempts
        url: Request URL
        delay: Delay before retry in seconds
    """
    logger.warning(f"🔄 Retry {attempt}/{max_retries} for {url} (waiting {delay:.1f}s)")

def log_progress(logger: logging.Logger, current: int, total: int, item_name: str = "item"):
    """
    Log progress details
    
    Args:
        logger: Logger instance
        current: Current item number (1-based)
        total: Total number of items
        item_name: Name of items being processed
    """
    percentage = (current / total) * 100 if total > 0 else 0
    logger.debug(f"📊 Progress: {current}/{total} {item_name}s processed ({percentage:.1f}%)")
