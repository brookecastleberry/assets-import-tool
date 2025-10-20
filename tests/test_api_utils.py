#!/usr/bin/env python3
"""
Unit tests for API utilities
"""

import pytest
import os
import sys
import time
import threading
from unittest.mock import patch, MagicMock, Mock
import requests

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from api import rate_limit, get_auth_headers, display_auth_status, make_request_with_retry


class TestRateLimit:
    """Test rate limiting functionality"""
    
    def test_rate_limit_enforced(self):
        """Test that rate limiting actually delays execution"""
        # Create rate limit parameters
        request_lock = threading.Lock()
        last_request_time = [0.0]  # Mutable container
        request_interval = 0.5  # 0.5 second interval
        
        start_time = time.time()
        
        # Make two calls
        rate_limit(request_lock, last_request_time, request_interval)
        rate_limit(request_lock, last_request_time, request_interval)
        
        elapsed = time.time() - start_time
        
        # Should have taken at least the request interval
        assert elapsed >= 0.4  # Allow some tolerance for execution time
    
    def test_rate_limit_with_zero_interval(self):
        """Test that zero interval allows rapid requests"""
        request_lock = threading.Lock()
        last_request_time = [0.0]
        request_interval = 0  # No rate limiting
        
        start_time = time.time()
        
        # Multiple calls with zero interval should be fast
        for _ in range(3):
            rate_limit(request_lock, last_request_time, request_interval)
        
        elapsed = time.time() - start_time
        assert elapsed < 0.1  # Should be very fast


class TestGetAuthHeaders:
    """Test authentication header generation"""
    
    def test_get_auth_headers_github_token(self):
        """Test GitHub token authentication"""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test_github_token'}):
            headers = get_auth_headers('github')
            
            assert headers is not None
            assert 'Authorization' in headers
            assert headers['Authorization'] == 'token test_github_token'
    
    def test_get_auth_headers_gitlab_token(self):
        """Test GitLab token authentication"""
        with patch.dict(os.environ, {'GITLAB_TOKEN': 'test_gitlab_token'}):
            headers = get_auth_headers('gitlab')
            
            assert headers is not None
            assert 'PRIVATE-TOKEN' in headers
            assert headers['PRIVATE-TOKEN'] == 'test_gitlab_token'
    
    def test_get_auth_headers_azure_token(self):
        """Test Azure DevOps token authentication"""
        with patch.dict(os.environ, {'AZURE_DEVOPS_TOKEN': 'test_azure_token'}):
            headers = get_auth_headers('azure')
            
            assert headers is not None
            assert 'Authorization' in headers
            # Azure uses Basic auth with base64 encoded token
            assert 'Basic' in headers['Authorization']
    
    def test_get_auth_headers_no_token(self):
        """Test behavior when no token is available for the SCM type"""
        # Clear all relevant environment variables
        with patch.dict(os.environ, {}, clear=True):
            headers = get_auth_headers('github')
            
            # Should return None when no token is available
            assert headers is None
    
    def test_get_auth_headers_unknown_scm(self):
        """Test behavior with unknown SCM type"""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}):
            headers = get_auth_headers('unknown_scm')
            
            # Should return None for unknown SCM types
            assert headers is None


class TestDisplayAuthStatus:
    """Test authentication status display"""
    
    def test_display_auth_status_with_tokens(self):
        """Test authentication status display with tokens present"""
        tokens = {
            'GITHUB_TOKEN': 'github_token',
            'GITLAB_TOKEN': 'gitlab_token'
        }
        
        with patch.dict(os.environ, tokens):
            with patch('builtins.print') as mock_print:
                display_auth_status('github')
                
                # Should print authentication status
                mock_print.assert_called()
                
                # Check that it mentions authentication
                printed_output = ' '.join([str(call[0][0]) for call in mock_print.call_args_list if call[0]])
                assert 'Authentication' in printed_output or 'GitHub' in printed_output
    
    def test_display_auth_status_no_tokens(self):
        """Test authentication status display without tokens"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('builtins.print') as mock_print:
                display_auth_status('github')
                
                # Should still print something
                mock_print.assert_called()


class TestMakeRequestWithRetry:
    """Test request retry functionality"""
    
    def test_make_request_success(self):
        """Test successful request without retry"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        
        # Mock rate limit function
        mock_rate_limit = MagicMock()
        
        with patch('requests.get', return_value=mock_response):
            response = make_request_with_retry(
                url='https://api.example.com/test',
                max_retries=3,
                retry_delay=1, 
                retry_backoff=2,
                rate_limit_fn=mock_rate_limit
            )
            
            assert response.status_code == 200
            assert response.json() == {'success': True}
    
    def test_make_request_retry_on_500(self):
        """Test retry on server error (500)"""
        # First call returns 500, second call succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        
        mock_rate_limit = MagicMock()
        
        with patch('requests.get', side_effect=[mock_response_fail, mock_response_success]):
            with patch('time.sleep'):  # Mock sleep to speed up test
                response = make_request_with_retry(
                    url='https://api.example.com/test',
                    max_retries=3,
                    retry_delay=1,
                    retry_backoff=2, 
                    rate_limit_fn=mock_rate_limit
                )
                
                assert response.status_code == 200
    
    def test_make_request_retry_on_429(self):
        """Test retry on rate limit (429)"""
        mock_response_fail = Mock()
        mock_response_fail.status_code = 429
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        
        mock_rate_limit = MagicMock()
        
        with patch('requests.get', side_effect=[mock_response_fail, mock_response_success]):
            with patch('time.sleep'):  # Mock sleep to speed up test
                response = make_request_with_retry(
                    url='https://api.example.com/test',
                    max_retries=3,
                    retry_delay=1,
                    retry_backoff=2,
                    rate_limit_fn=mock_rate_limit
                )
                
                assert response.status_code == 200
    
    def test_make_request_no_retry_on_404(self):
        """Test no retry on client error (404) - should return None"""
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_rate_limit = MagicMock()
        
        with patch('requests.get', return_value=mock_response):
            response = make_request_with_retry(
                url='https://api.example.com/test',
                max_retries=3,
                retry_delay=1,
                retry_backoff=2,
                rate_limit_fn=mock_rate_limit
            )
            
            # Should return None for client errors
            assert response is None
    
    def test_make_request_max_retries(self):
        """Test that max retries is respected"""
        mock_response = Mock()
        mock_response.status_code = 500
        
        mock_rate_limit = MagicMock()
        
        with patch('requests.get', return_value=mock_response):
            with patch('time.sleep'):  # Mock sleep to speed up test
                response = make_request_with_retry(
                    url='https://api.example.com/test',
                    max_retries=2,
                    retry_delay=1,
                    retry_backoff=2,
                    rate_limit_fn=mock_rate_limit
                )
                
                # Should return None after max retries for server errors
                assert response is None
    
    def test_make_request_with_headers(self):
        """Test request with custom headers"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        custom_headers = {'Authorization': 'token test123'}
        mock_rate_limit = MagicMock()
        
        with patch('requests.get', return_value=mock_response) as mock_get:
            make_request_with_retry(
                url='https://api.example.com/test',
                max_retries=3,
                retry_delay=1,
                retry_backoff=2,
                rate_limit_fn=mock_rate_limit,
                headers=custom_headers
            )
            
            # Verify headers were passed
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert 'headers' in call_kwargs
            assert call_kwargs['headers']['Authorization'] == 'token test123'


if __name__ == '__main__':
    pytest.main([__file__])
