import json
import os
import sys
from typing import Any, Dict, List


def sanitize_path(path: str) -> str:
    """
    Sanitize file path to prevent path traversal attacks
    
    Args:
        path: File path to sanitize
        
    Returns:
        Normalized safe path
        
    Raises:
        ValueError: If path is unsafe (absolute or contains path traversal)
    """
    if os.path.isabs(path) or '..' in os.path.normpath(path).split(os.sep):
        raise ValueError(f"Unsafe file path detected: {path}")
    return os.path.normpath(path)


def sanitize_input_path(path: str) -> str:
    """
    Sanitize input file path - allows absolute paths but prevents directory traversal
    
    Args:
        path: File path to sanitize
        
    Returns:
        Normalized safe path
        
    Raises:
        ValueError: If path contains directory traversal attempts
    """
    # Allow absolute paths for input files, but prevent directory traversal
    if '..' in os.path.normpath(path).split(os.sep):
        raise ValueError(f"Unsafe file path detected (directory traversal): {path}")
    return os.path.normpath(path)


def safe_write_json(data: Dict[str, Any], output_path: str, logger=None) -> None:
    """
    Safely write JSON data to file with comprehensive error handling
    Automatically sanitizes the output path for security.
    
    Args:
        data: Dictionary data to write as JSON
        output_path: Output file path (will be sanitized)
        logger: Optional logger for error reporting
        
    Raises:
        SystemExit: On any file writing error
    """
    # Sanitize path for security
    safe_output_path = sanitize_path(output_path)
    
    try:
        with open(safe_output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        success_msg = f"📄 Created file: {safe_output_path}"
        print(success_msg)
        if logger:
            logger.info(success_msg)
            
    except PermissionError:
        error_msg = f"❌ Error: Permission denied writing to {safe_output_path}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    except OSError as e:
        error_msg = f"❌ Error: Failed to write file {safe_output_path}: {e}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"❌ Error: Unexpected error writing file {safe_output_path}: {e}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)


def validate_file_exists(file_path: str, logger=None) -> None:
    """
    Validate that a required file exists
    
    Args:
        file_path: Path to file that must exist
        logger: Optional logger for error reporting
        
    Raises:
        SystemExit: If file doesn't exist
    """
    if not os.path.exists(file_path):
        error_msg = f"❌ Error: File not found: {file_path}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)


def log_error_and_exit(message: str, logger=None, exit_code: int = 1) -> None:
    """
    Log error message and exit with specified code
    
    Args:
        message: Error message to log and print
        logger: Optional logger for error reporting
        exit_code: Exit code (default: 1)
    """
    print(message)
    if logger:
        logger.error(message)
    sys.exit(exit_code)


def validate_positive_integer(value: int, field_name: str, logger=None) -> None:
    """
    Validate that a value is a positive integer
    
    Args:
        value: Value to validate
        field_name: Name of field for error message
        logger: Optional logger for error reporting
        
    Raises:
        SystemExit: If value is not positive
    """
    if value is not None and value <= 0:
        error_msg = f"❌ Error: {field_name} must be a positive integer, got: {value}"
        log_error_and_exit(error_msg, logger)


def validate_non_empty_string(value: str, field_name: str, logger=None) -> None:
    """
    Validate that a string value is not empty
    
    Args:
        value: String value to validate
        field_name: Name of field for error message
        logger: Optional logger for error reporting
        
    Raises:
        SystemExit: If value is empty
    """
    if not value or len(value.strip()) == 0:
        error_msg = f"❌ Error: {field_name} cannot be empty"
        log_error_and_exit(error_msg, logger)
