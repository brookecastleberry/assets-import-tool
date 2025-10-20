#!/usr/bin/env python3
"""
Unit tests for file utilities
"""

import pytest
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from file_utils import (
    sanitize_path, 
    sanitize_input_path, 
    safe_write_json, 
    validate_file_exists, 
    validate_positive_integer,
    validate_non_empty_string,
    log_error_and_exit
)


class TestSanitizePath:
    """Test path sanitization functions"""
    
    def test_sanitize_path_normal_relative(self):
        """Test normal relative path sanitization"""
        result = sanitize_path("folder/file.txt")
        assert result == "folder/file.txt"
    
    def test_sanitize_path_rejects_absolute(self):
        """Test that absolute paths are rejected"""
        with pytest.raises(ValueError, match="Unsafe file path detected"):
            sanitize_path("/absolute/path/file.txt")
    
    def test_sanitize_path_rejects_traversal(self):
        """Test that directory traversal is rejected"""
        with pytest.raises(ValueError, match="Unsafe file path detected"):
            sanitize_path("../../../etc/passwd")
    
    def test_sanitize_input_path_allows_absolute(self):
        """Test that input path sanitization allows absolute paths"""
        result = sanitize_input_path("/absolute/path/file.csv")
        assert result == "/absolute/path/file.csv"
    
    def test_sanitize_input_path_rejects_traversal(self):
        """Test that input path sanitization rejects directory traversal"""
        with pytest.raises(ValueError, match="directory traversal"):
            sanitize_input_path("../../../etc/passwd")
    
    def test_sanitize_input_path_normal_relative(self):
        """Test normal relative path with input sanitization"""
        result = sanitize_input_path("data/file.csv")
        assert result == "data/file.csv"


class TestSafeWriteJson:
    """Test safe JSON writing functionality"""
    
    def test_safe_write_json_success(self):
        """Test successful JSON writing"""
        test_data = {"key": "value", "number": 123}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp_file:
            temp_path = tmp_file.name
        
        try:
            # Remove the file so safe_write_json can create it
            os.unlink(temp_path)
            
            # Extract just the filename for sanitize_path
            temp_filename = os.path.basename(temp_path)
            
            safe_write_json(test_data, temp_filename)
            
            # Verify file was created and contains correct data
            with open(temp_filename, 'r') as f:
                written_data = json.load(f)
            
            assert written_data == test_data
            
        finally:
            # Clean up
            for file_path in [temp_path, temp_filename]:
                if os.path.exists(file_path):
                    os.unlink(file_path)
    
    def test_safe_write_json_with_logger(self):
        """Test JSON writing with logger"""
        test_data = {"test": True}
        mock_logger = MagicMock()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp_file:
            temp_filename = os.path.basename(tmp_file.name)
        
        try:
            os.unlink(tmp_file.name)  # Remove so safe_write_json can create it
            
            safe_write_json(test_data, temp_filename, logger=mock_logger)
            
            # Verify logger was called
            mock_logger.info.assert_called()
            
        finally:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)


class TestValidationFunctions:
    """Test validation helper functions"""
    
    def test_validate_positive_integer_valid(self):
        """Test positive integer validation with valid input"""
        # Should not raise any exception
        validate_positive_integer(5, "--test-arg", None)
        validate_positive_integer(1, "--test-arg", None)
    
    def test_validate_positive_integer_invalid(self):
        """Test positive integer validation with invalid input"""
        with pytest.raises(SystemExit):
            validate_positive_integer(-1, "--test-arg", None)
        
        with pytest.raises(SystemExit):
            validate_positive_integer(0, "--test-arg", None)
    
    def test_validate_positive_integer_none(self):
        """Test positive integer validation with None (should pass)"""
        # None should be allowed (optional parameter)
        validate_positive_integer(None, "--test-arg", None)
    
    def test_validate_non_empty_string_valid(self):
        """Test non-empty string validation with valid input"""
        validate_non_empty_string("valid_string", "--test-arg", None)
    
    def test_validate_non_empty_string_empty(self):
        """Test non-empty string validation with empty string"""
        with pytest.raises(SystemExit):
            validate_non_empty_string("", "--test-arg", None)
        
        with pytest.raises(SystemExit):
            validate_non_empty_string("   ", "--test-arg", None)
    
    def test_validate_file_exists_valid(self):
        """Test file existence validation with existing file"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            temp_path = tmp_file.name
        
        try:
            validate_file_exists(temp_path, None)
        finally:
            os.unlink(temp_path)
    
    def test_validate_file_exists_missing(self):
        """Test file existence validation with missing file"""
        with pytest.raises(SystemExit):
            validate_file_exists("/nonexistent/file.txt", None)


if __name__ == '__main__':
    pytest.main([__file__])
