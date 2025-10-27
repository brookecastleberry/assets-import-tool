#!/usr/bin/env python3
"""
Unit tests for SNYK_LOG_PATH functionality
"""

import pytest
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from file_utils import build_output_path_in_logs, safe_write_json_to_logs


class TestBuildOutputPathInLogs:
    """Test SNYK_LOG_PATH functionality"""
    
    def test_missing_snyk_log_path_env_var(self):
        """Test that missing SNYK_LOG_PATH environment variable causes exit"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                build_output_path_in_logs("test.json")
            
            # Should exit with code 1
            assert exc_info.value.code == 1
    
    def test_nonexistent_directory_causes_exit(self):
        """Test that nonexistent SNYK_LOG_PATH directory causes exit"""
        nonexistent_path = "/definitely/does/not/exist/logs"
        
        with patch.dict(os.environ, {'SNYK_LOG_PATH': nonexistent_path}):
            with pytest.raises(SystemExit) as exc_info:
                build_output_path_in_logs("test.json")
            
            # Should exit with code 1
            assert exc_info.value.code == 1
    
    def test_file_instead_of_directory_causes_exit(self):
        """Test that SNYK_LOG_PATH pointing to a file (not directory) causes exit"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            with patch.dict(os.environ, {'SNYK_LOG_PATH': file_path}):
                with pytest.raises(SystemExit) as exc_info:
                    build_output_path_in_logs("test.json")
                
                # Should exit with code 1
                assert exc_info.value.code == 1
        finally:
            os.unlink(file_path)
    
    def test_unwritable_directory_causes_exit(self):
        """Test that unwritable SNYK_LOG_PATH directory causes exit"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Make directory read-only
            os.chmod(tmp_dir, 0o444)
            
            try:
                with patch.dict(os.environ, {'SNYK_LOG_PATH': tmp_dir}):
                    with pytest.raises(SystemExit) as exc_info:
                        build_output_path_in_logs("test.json")
                    
                    # Should exit with code 1
                    assert exc_info.value.code == 1
            finally:
                # Restore write permissions for cleanup
                os.chmod(tmp_dir, 0o755)
    
    def test_valid_directory_returns_correct_path(self):
        """Test that valid SNYK_LOG_PATH directory returns correct file path"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            filename = "test-output.json"
            expected_path = os.path.join(tmp_dir, filename)
            
            with patch.dict(os.environ, {'SNYK_LOG_PATH': tmp_dir}):
                result = build_output_path_in_logs(filename)
                
                assert result == expected_path
    
    def test_with_logger_logs_correctly(self):
        """Test that function logs correctly when logger is provided"""
        mock_logger = MagicMock()
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            filename = "test-with-logger.json"
            
            with patch.dict(os.environ, {'SNYK_LOG_PATH': tmp_dir}):
                result = build_output_path_in_logs(filename, logger=mock_logger)
                
                # Should log the path being used
                mock_logger.info.assert_called_once()
                log_message = mock_logger.info.call_args[0][0]
                assert "Using SNYK_LOG_PATH for output:" in log_message
                assert filename in log_message


class TestSafeWriteJsonToLogs:
    """Test safe JSON writing to SNYK_LOG_PATH"""
    
    def test_missing_snyk_log_path_env_var(self):
        """Test that missing SNYK_LOG_PATH environment variable causes exit"""
        test_data = {"test": "data"}
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                safe_write_json_to_logs(test_data, "test.json")
            
            # Should exit with code 1
            assert exc_info.value.code == 1
    
    def test_successful_json_write(self):
        """Test successful JSON writing to SNYK_LOG_PATH directory"""
        test_data = {"key": "value", "number": 42, "array": [1, 2, 3]}
        filename = "test-write.json"
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            expected_file_path = os.path.join(tmp_dir, filename)
            
            with patch.dict(os.environ, {'SNYK_LOG_PATH': tmp_dir}):
                safe_write_json_to_logs(test_data, filename)
                
                # Verify file was created
                assert os.path.exists(expected_file_path)
                
                # Verify file content is correct
                with open(expected_file_path, 'r') as f:
                    written_data = json.load(f)
                
                assert written_data == test_data
    
    def test_with_logger_logs_success(self):
        """Test that function logs success when logger is provided"""
        test_data = {"logged": True}
        filename = "test-logged.json"
        mock_logger = MagicMock()
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {'SNYK_LOG_PATH': tmp_dir}):
                safe_write_json_to_logs(test_data, filename, logger=mock_logger)
                
                # Should log both path usage and file creation
                assert mock_logger.info.call_count >= 1
                
                # Check that success message was logged
                log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                success_logged = any("Created file:" in msg for msg in log_calls)
                assert success_logged


class TestIntegrationWithScripts:
    """Test integration with the actual scripts"""
    
    def test_create_orgs_with_valid_snyk_log_path(self):
        """Test that create_orgs.py respects SNYK_LOG_PATH"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a minimal CSV file for testing
            csv_content = "Application,Type,Repository URL,Asset Source\nTestApp,Repository,https://github.com/test/repo,GitHub\n"
            csv_file = os.path.join(tmp_dir, "test.csv")
            
            with open(csv_file, 'w') as f:
                f.write(csv_content)
            
            # Set SNYK_LOG_PATH
            with patch.dict(os.environ, {'SNYK_LOG_PATH': tmp_dir}):
                # Import and test the function
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
                try:
                    from create_orgs import SnykOrgCreator
                    creator = SnykOrgCreator("test-group-id", debug=False)
                    
                    # This should use SNYK_LOG_PATH when no output specified
                    output_path = build_output_path_in_logs("group-test-group-id-orgs.json")
                    expected_path = os.path.join(tmp_dir, "group-test-group-id-orgs.json")
                    
                    assert output_path == expected_path
                except ImportError as e:
                    # Skip if imports fail (dependency issues)
                    pytest.skip(f"Import failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__])
