import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def build_output_path_in_logs(filename: str, logger=None) -> str:
    """
    Build an output file path in the SNYK_LOG_PATH directory.
    Validates that the directory exists and sanitizes the filename to prevent path traversal attacks.
    
    Args:
        filename: The filename to create in the logs directory (will be sanitized)
        logger: Optional logger for messages
        
    Returns:
        Full path where the file should be written
        
    Raises:
        SystemExit: If SNYK_LOG_PATH environment variable is not set, directory doesn't exist,
                   or filename contains path traversal attempts
    """
    snyk_log_path = os.environ.get('SNYK_LOG_PATH')
    
    if not snyk_log_path:
        error_msg = "❌ Error: SNYK_LOG_PATH environment variable is required but not set. Please set it to your desired logs directory and re-run."
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    
    # Validate and normalize the log directory path
    try:
        log_dir = Path(snyk_log_path).resolve()
    except Exception as e:
        error_msg = f"❌ Error: Invalid SNYK_LOG_PATH '{snyk_log_path}': {e}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    
    # Check if the directory exists
    if not log_dir.exists():
        error_msg = f"❌ Error: SNYK_LOG_PATH directory '{log_dir}' does not exist. Please create the directory first and re-run."
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    
    if not log_dir.is_dir():
        error_msg = f"❌ Error: SNYK_LOG_PATH '{log_dir}' is not a directory. Please set it to a valid directory path and re-run."
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    
    # Check if directory is writable
    if not os.access(str(log_dir), os.W_OK):
        error_msg = f"❌ Error: SNYK_LOG_PATH directory '{log_dir}' is not writable. Please check permissions and re-run."
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    
    # Sanitize filename to prevent path traversal attacks
    try:
        # Extract only the filename component, removing any path separators
        safe_filename = Path(filename).name
        
        # Additional validation - ensure filename doesn't contain suspicious characters
        if not safe_filename or safe_filename in ('.', '..') or '/' in safe_filename or '\\' in safe_filename:
            raise ValueError(f"Invalid filename: {filename}")
        
        # Build the output path
        output_path = log_dir / safe_filename
        
        # Final security check - ensure the resolved path is still within the log directory
        if not str(output_path.resolve()).startswith(str(log_dir)):
            raise ValueError(f"Path traversal attempt detected in filename: {filename}")
            
    except Exception as e:
        error_msg = f"❌ Error: Invalid filename '{filename}': {e}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    
    if logger:
        logger.info(f"Using SNYK_LOG_PATH for output: {output_path}")
    return str(output_path)


def safe_write_json_to_logs(data: Dict[str, Any], filename: str, logger=None) -> None:
    """
    Safely write JSON data to file in the SNYK_LOG_PATH directory with comprehensive error handling
    
    Args:
        data: Dictionary data to write as JSON
        filename: Filename (without path) to write to
        logger: Optional logger for error reporting
        
    Raises:
        SystemExit: On any file writing error or if SNYK_LOG_PATH is not set
    """
    output_path = build_output_path_in_logs(filename, logger)
    
    try:
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        success_msg = f"📄 Created file: {output_path}"
        print(success_msg)
        if logger:
            logger.info(success_msg)
            
    except PermissionError:
        error_msg = f"❌ Error: Permission denied writing to {output_path}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    except OSError as e:
        error_msg = f"❌ Error: Failed to write file {output_path}: {e}"
        print(error_msg)
        if logger:
            logger.error(error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"❌ Error: Unexpected error writing file {output_path}: {e}"
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
