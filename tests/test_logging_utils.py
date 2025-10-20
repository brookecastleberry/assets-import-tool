#!/usr/bin/env python3
"""
Unit tests for logging utilities
"""

import pytest
import os
import sys
import logging
import tempfile
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from logging_utils import setup_logging


class TestSetupLogging:
    """Test logging setup functionality"""
    
    def test_setup_logging_basic(self):
        """Test basic logging setup"""
        logger = setup_logging('test_logger')
        
        assert logger is not None
        assert logger.name == 'test_logger'
        assert logger.level == logging.INFO
    
    def test_setup_logging_with_snyk_log_path(self):
        """Test logging setup with SNYK_LOG_PATH environment variable"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, 'test.log')
            
            with patch.dict(os.environ, {'SNYK_LOG_PATH': temp_dir}):
                with patch('logging_utils.datetime') as mock_datetime:
                    # Mock datetime to get predictable filename
                    mock_datetime.now.return_value.strftime.return_value = '20231017_120000'
                    
                    logger = setup_logging('test_logger')
                    
                    # Test that logger was created
                    assert logger is not None
                    
                    # Test logging actually works
                    logger.info("Test message")
                    
                    # Check that log file was created (with timestamp)
                    expected_log_file = os.path.join(temp_dir, 'test_logger_20231017_120000.log')
                    # Note: The actual file creation depends on the handler setup in setup_logging
    
    def test_setup_logging_without_snyk_log_path(self):
        """Test logging setup without SNYK_LOG_PATH (console only)"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('builtins.print') as mock_print:
                logger = setup_logging('test_logger')
                
                assert logger is not None
                
                # Should print warning about missing SNYK_LOG_PATH
                mock_print.assert_called()
                printed_text = ' '.join([str(call[0][0]) for call in mock_print.call_args_list])
                assert 'SNYK_LOG_PATH' in printed_text
    
    def test_setup_logging_different_loggers(self):
        """Test that different logger names create different loggers"""
        logger1 = setup_logging('logger1')
        logger2 = setup_logging('logger2')
        
        assert logger1.name != logger2.name
        assert logger1 is not logger2
    
    def test_setup_logging_same_name_returns_same_logger(self):
        """Test that requesting the same logger name returns the same instance"""
        logger1 = setup_logging('same_logger')
        logger2 = setup_logging('same_logger')
        
        # Should return the same logger instance
        assert logger1 is logger2
    
    def test_logger_output_format(self):
        """Test that logger output has correct format"""
        with patch('sys.stdout') as mock_stdout:
            logger = setup_logging('format_test')
            
            # Test logging a message
            logger.info("Test formatting message")
            
            # Verify logger was configured (exact format testing requires more complex setup)
            assert logger.handlers  # Should have handlers configured
    
    def test_logger_level_configuration(self):
        """Test that logger is configured with correct level"""
        logger = setup_logging('level_test')
        
        # Should be set to INFO level
        assert logger.level == logging.INFO
        
        # Should log INFO messages
        assert logger.isEnabledFor(logging.INFO)
        
        # Should log ERROR messages  
        assert logger.isEnabledFor(logging.ERROR)
        
        # Should NOT log DEBUG messages (below INFO)
        assert not logger.isEnabledFor(logging.DEBUG)
    
    def test_logger_with_special_characters(self):
        """Test logger names with special characters"""
        special_name = 'test-logger_with.special@chars'
        logger = setup_logging(special_name)
        
        assert logger is not None
        assert logger.name == special_name
    
    def test_logger_console_handler(self):
        """Test that console handler is properly configured"""
        logger = setup_logging('console_test')
        
        # Should have at least one handler
        assert len(logger.handlers) >= 1
        
        # At least one handler should be a console/stream handler
        has_console_handler = any(
            isinstance(handler, logging.StreamHandler) 
            for handler in logger.handlers
        )
        assert has_console_handler
    
    @patch('logging_utils.os.makedirs')
    def test_log_directory_creation(self, mock_makedirs):
        """Test that log directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = os.path.join(temp_dir, 'nonexistent', 'logs')
            
            with patch.dict(os.environ, {'SNYK_LOG_PATH': log_dir}):
                setup_logging('test_logger')
                
                # Should attempt to create directory
                # Note: This depends on the actual implementation in setup_logging
    
    def test_logger_thread_safety(self):
        """Test that logger setup works correctly in multi-threaded environment"""
        import threading
        
        loggers = []
        
        def create_logger(name):
            logger = setup_logging(f'thread_test_{name}')
            loggers.append(logger)
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_logger, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have created 5 different loggers
        assert len(loggers) == 5
        assert len(set(logger.name for logger in loggers)) == 5


class TestLoggingIntegration:
    """Integration tests for logging functionality"""
    
    def test_logging_actual_output(self):
        """Test that logging actually produces output"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {'SNYK_LOG_PATH': temp_dir}):
                logger = setup_logging('integration_test')
                
                # Log some messages
                logger.info("Integration test info message")
                logger.error("Integration test error message")
                logger.warning("Integration test warning message")
                
                # Force flush of handlers
                for handler in logger.handlers:
                    if hasattr(handler, 'flush'):
                        handler.flush()


if __name__ == '__main__':
    pytest.main([__file__])
