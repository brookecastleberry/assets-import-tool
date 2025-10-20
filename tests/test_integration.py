#!/usr/bin/env python3
"""
Integration tests for the assets import tool

These tests verify that different components work together correctly.
"""

import pytest
import os
import sys
import tempfile
import json
import csv
from unittest.mock import patch, MagicMock, Mock

# Add src and root directory to path for imports  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from csv_utils import read_applications_from_csv
from file_utils import safe_write_json
from api import get_auth_headers


class TestCsvToJsonWorkflow:
    """Test the complete CSV -> JSON workflow"""
    
    def create_test_csv(self, data):
        """Helper to create a test CSV file"""
        tmp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
        
        with tmp_file as f:
            writer = csv.writer(f)
            for row in data:
                writer.writerow(row)
        
        return tmp_file.name
    
    def test_csv_to_json_workflow(self):
        """Test complete workflow from CSV reading to JSON output"""
        # Create test CSV data
        test_data = [
            ['Type', 'Asset', 'Repository URL', 'Application'],
            ['Repository', 'test-repo1', 'https://github.com/user/repo1', 'App1'],
            ['Repository', 'test-repo2', 'https://github.com/user/repo2', 'App2']
        ]
        
        csv_file = self.create_test_csv(test_data)
        
        try:
            # Step 1: Read CSV
            mock_logger = MagicMock()
            applications = read_applications_from_csv(csv_file, logger=mock_logger)
            
            assert len(applications) == 2
            
            # Step 2: Transform data (simulate organization creation)
            org_data = {
                'orgs': [
                    {
                        'name': app['application_name'],
                        'groupId': 'test-group-id'
                    }
                    for app in applications
                ]
            }
            
            # Step 3: Write JSON output
            output_filename = 'test_output.json'
            safe_write_json(org_data, output_filename)
            
            # Step 4: Verify output
            with open(output_filename, 'r') as f:
                written_data = json.load(f)
            
            assert 'orgs' in written_data
            assert len(written_data['orgs']) == 2
            assert written_data['orgs'][0]['name'] == 'App1'
            assert written_data['orgs'][1]['name'] == 'App2'
            
        finally:
            # Cleanup
            for file_path in [csv_file, 'test_output.json']:
                if os.path.exists(file_path):
                    os.unlink(file_path)


class TestAuthenticationIntegration:
    """Test authentication integration with different services"""
    
    def test_github_auth_integration(self):
        """Test GitHub authentication header generation"""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'github_test_token'}):
            headers = get_auth_headers('github')
            
            # Verify GitHub auth header is present
            assert headers is not None
            assert 'Authorization' in headers
            assert 'github_test_token' in headers['Authorization']
    
    def test_multi_service_auth(self):
        """Test authentication with multiple services configured"""
        env_vars = {
            'GITHUB_TOKEN': 'github_token',
            'GITLAB_TOKEN': 'gitlab_token'
        }
        
        with patch.dict(os.environ, env_vars):
            # Test GitHub auth
            github_headers = get_auth_headers('github')
            assert github_headers is not None
            assert 'Authorization' in github_headers
            
            # Test GitLab auth
            gitlab_headers = get_auth_headers('gitlab')
            assert gitlab_headers is not None
            assert 'PRIVATE-TOKEN' in gitlab_headers


class TestErrorHandlingIntegration:
    """Test error handling across multiple components"""
    
    def test_missing_csv_file_error_flow(self):
        """Test error handling when CSV file doesn't exist"""
        mock_logger = MagicMock()
        
        # Function returns empty list for missing files
        applications = read_applications_from_csv('/nonexistent/file.csv', logger=mock_logger)
        assert applications == []
        
        # Verify error was logged
        mock_logger.error.assert_called()
    
    def test_invalid_json_output_path(self):
        """Test error handling for invalid JSON output paths"""
        test_data = {'test': 'data'}
        
        # Try to write to a path that should fail (path traversal)
        with pytest.raises(ValueError):
            safe_write_json(test_data, '../../../etc/passwd')


class TestDataTransformation:
    """Test data transformation between different formats"""
    
    def test_csv_data_normalization(self):
        """Test that CSV data is properly normalized"""
        test_data = [
            ['Type', 'Asset', 'Repository URL', 'Application'],
            ['Repository', '  test-repo  ', 'https://github.com/user/repo', '  TestApp  ']  # With whitespace
        ]
        
        csv_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
        
        with csv_file as f:
            writer = csv.writer(f)
            for row in test_data:
                writer.writerow(row)
        
        try:
            mock_logger = MagicMock()
            applications = read_applications_from_csv(csv_file.name, logger=mock_logger)
            
            # Verify data is normalized (whitespace should be preserved as-is for compatibility)
            assert len(applications) == 1
            app = applications[0]
            assert 'asset_name' in app
            assert 'repository_url' in app
            assert 'application_name' in app
            assert 'asset_type' in app  # Field is 'asset_type' not 'type'
            assert 'row_index' in app
            
        finally:
            os.unlink(csv_file.name)
    
    def test_data_consistency_across_components(self):
        """Test that data structure is consistent across different components"""
        # Create mock application data
        app_data = {
            'application_name': 'TestApp',
            'asset_name': 'test-asset',
            'repository_url': 'https://github.com/user/repo',
            'type': 'Repository',
            'row_index': 2
        }
        
        # Test JSON serialization/deserialization
        json_output = 'consistency_test.json'
        
        try:
            safe_write_json({'apps': [app_data]}, json_output)
            
            with open(json_output, 'r') as f:
                loaded_data = json.load(f)
            
            loaded_app = loaded_data['apps'][0]
            
            # Verify all fields are preserved
            for key, value in app_data.items():
                assert key in loaded_app
                assert loaded_app[key] == value
        
        finally:
            if os.path.exists(json_output):
                os.unlink(json_output)


class TestConfigurationIntegration:
    """Test configuration and environment variable integration"""
    
    def test_environment_variable_precedence(self):
        """Test that environment variables are properly prioritized"""
        # Test with multiple tokens - should use the correct one for each SCM type
        env_vars = {
            'GITHUB_TOKEN': 'github_primary',
            'GITLAB_TOKEN': 'gitlab_primary'
        }
        
        with patch.dict(os.environ, env_vars):
            github_headers = get_auth_headers('github')
            gitlab_headers = get_auth_headers('gitlab')
            
            # Each should use the correct token
            assert github_headers is not None
            assert 'Authorization' in github_headers
            assert 'github_primary' in github_headers['Authorization']
            
            assert gitlab_headers is not None
            assert 'PRIVATE-TOKEN' in gitlab_headers
            assert gitlab_headers['PRIVATE-TOKEN'] == 'gitlab_primary'
    
    def test_missing_configuration_fallback(self):
        """Test behavior when configuration is missing"""
        # Clear all auth-related environment variables
        with patch.dict(os.environ, {}, clear=True):
            headers = get_auth_headers('github')
            
            # Should return None when no token is available
            assert headers is None


if __name__ == '__main__':
    pytest.main([__file__])
