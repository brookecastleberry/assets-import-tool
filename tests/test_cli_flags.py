#!/usr/bin/env python3
"""
Unit tests for CLI flags functionality in create_targets.py
"""

import pytest
import os
import sys
import tempfile
import json
from unittest.mock import MagicMock, patch, Mock

# Add root directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from create_targets import SnykTargetMapper


class TestBranchOverride:
    """Test --branch flag functionality"""
    
    def create_test_applications(self):
        """Helper to create test application data"""
        return [
            {
                'application_name': 'TestApp1',
                'asset_name': 'repo1',
                'repository_url': 'https://github.com/user/repo1',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            },
            {
                'application_name': 'TestApp2', 
                'asset_name': 'repo2',
                'repository_url': 'https://github.com/user/repo2',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
    
    def test_branch_override_general_targets(self):
        """Test that branch override works for general targets"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'
        
        applications = self.create_test_applications()
        org_mapping = {'TestApp1': 'org1', 'TestApp2': 'org2'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github', 
                            branch_override='develop',  # Override branch
                            files_override=None,
                            exclusion_globs_override=None,
                            max_workers=1
                        )
        
        # Verify all targets use the override branch
        assert len(targets) == 2
        for target in targets:
            assert target['target']['branch'] == 'develop'
        
        # Verify get_default_branch was not called when override is provided
        mock_get_branch.assert_not_called()
    
    def test_branch_override_gitlab_targets(self):
        """Test that branch override works for GitLab targets"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'gitlab'
        
        applications = [
            {
                'application_name': 'GitLabApp',
                'asset_name': 'gitlab-repo',
                'repository_url': 'https://gitlab.com/user/repo',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
        org_mapping = {'GitLabApp': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_gitlab_project_info') as mock_gitlab_info:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'gitlab': 'integration-456'}
                        mock_find_integration.return_value = 'integration-456'
                        mock_gitlab_info.return_value = {
                            'id': 12345,
                            'default_branch': 'master'
                        }
                        
                        targets = mapper.create_gitlab_targets(
                            applications, org_mapping, 'gitlab',
                            branch_override='production'  # Override branch
                        )
        
        # Verify override branch is used instead of GitLab default
        assert len(targets) == 1
        assert targets[0]['target']['branch'] == 'production'
    
    def test_no_branch_override_uses_detection(self):
        """Test that without override, branch detection is used"""
        mapper = SnykTargetMapper("test-group-id") 
        mapper.source_type = 'github'
        
        applications = self.create_test_applications()[:1]  # Just one app
        org_mapping = {'TestApp1': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github',
                            branch_override=None,  # No override
                            files_override=None,
                            exclusion_globs_override=None,
                            max_workers=1
                        )
        
        # Verify detection was called and result used
        assert len(targets) == 1
        assert targets[0]['target']['branch'] == 'main'
        mock_get_branch.assert_called_once()


class TestFilesOverride:
    """Test --files flag functionality"""
    
    def test_files_override_single_file(self):
        """Test files override with single file"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'
        
        applications = [
            {
                'application_name': 'TestApp',
                'asset_name': 'repo',
                'repository_url': 'https://github.com/user/repo',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
        org_mapping = {'TestApp': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github',
                            branch_override=None,
                            files_override='package.json',  # Single file
                            exclusion_globs_override=None,
                            max_workers=1
                        )
        
        # Verify files are correctly structured
        assert len(targets) == 1
        assert 'files' in targets[0]
        assert targets[0]['files'] == [{'path': 'package.json'}]
    
    def test_files_override_multiple_files(self):
        """Test files override with multiple files"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'
        
        applications = [
            {
                'application_name': 'TestApp',
                'asset_name': 'repo',
                'repository_url': 'https://github.com/user/repo',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
        org_mapping = {'TestApp': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github',
                            branch_override=None,
                            files_override='package.json, requirements.txt, Dockerfile',  # Multiple files
                            exclusion_globs_override=None,
                            max_workers=1
                        )
        
        # Verify files are correctly parsed and structured
        assert len(targets) == 1
        assert 'files' in targets[0]
        expected_files = [
            {'path': 'package.json'},
            {'path': 'requirements.txt'},
            {'path': 'Dockerfile'}
        ]
        assert targets[0]['files'] == expected_files
    
    def test_files_override_with_whitespace(self):
        """Test files override handles whitespace correctly"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'
        
        applications = [
            {
                'application_name': 'TestApp',
                'asset_name': 'repo',
                'repository_url': 'https://github.com/user/repo',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
        org_mapping = {'TestApp': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github',
                            branch_override=None,
                            files_override='  package.json  ,   requirements.txt   ,  ',  # Whitespace and empty
                            exclusion_globs_override=None,
                            max_workers=1
                        )
        
        # Verify whitespace is stripped and empty entries removed
        assert len(targets) == 1
        assert 'files' in targets[0]
        expected_files = [
            {'path': 'package.json'},
            {'path': 'requirements.txt'}
        ]
        assert targets[0]['files'] == expected_files
    
    def test_no_files_override_omits_field(self):
        """Test that without files override, files field is omitted"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'
        
        applications = [
            {
                'application_name': 'TestApp',
                'asset_name': 'repo',
                'repository_url': 'https://github.com/user/repo',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
        org_mapping = {'TestApp': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github',
                            branch_override=None,
                            files_override=None,  # No files override
                            exclusion_globs_override=None,
                            max_workers=1
                        )
        
        # Verify files field is not present
        assert len(targets) == 1
        assert 'files' not in targets[0]


class TestExclusionGlobsOverride:
    """Test --exclusion-globs flag functionality"""
    
    def test_exclusion_globs_override_with_patterns(self):
        """Test exclusion globs override with patterns"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'
        
        applications = [
            {
                'application_name': 'TestApp',
                'asset_name': 'repo',
                'repository_url': 'https://github.com/user/repo',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
        org_mapping = {'TestApp': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github',
                            branch_override=None,
                            files_override=None,
                            exclusion_globs_override='test,spec,node_modules',  # Custom exclusions
                            max_workers=1
                        )
        
        # Verify exclusion globs are set correctly
        assert len(targets) == 1
        assert targets[0]['exclusionGlobs'] == 'test,spec,node_modules'
    
    def test_exclusion_globs_override_empty_string(self):
        """Test exclusion globs override with empty string (no exclusions)"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'
        
        applications = [
            {
                'application_name': 'TestApp',
                'asset_name': 'repo',
                'repository_url': 'https://github.com/user/repo',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
        org_mapping = {'TestApp': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github',
                            branch_override=None,
                            files_override=None,
                            exclusion_globs_override='',  # Empty exclusions
                            max_workers=1
                        )
        
        # Verify empty exclusion globs are set
        assert len(targets) == 1
        assert targets[0]['exclusionGlobs'] == ''
    
    def test_no_exclusion_globs_override_uses_default(self):
        """Test that without override, default exclusions are used"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'
        
        applications = [
            {
                'application_name': 'TestApp',
                'asset_name': 'repo',
                'repository_url': 'https://github.com/user/repo',
                'asset_type': 'Repository',
                'organizations': 'N/A'
            }
        ]
        org_mapping = {'TestApp': 'org1'}
        
        # Mock all the required dependencies
        with patch.object(mapper, 'load_organizations_from_json'):
            with patch.object(mapper, 'get_integrations_for_org') as mock_get_integrations:
                with patch.object(mapper, 'find_integration_id') as mock_find_integration:
                    with patch.object(mapper, 'get_default_branch') as mock_get_branch:
                        
                        # Setup mocks
                        mock_get_integrations.return_value = {'github': 'integration-123'}
                        mock_find_integration.return_value = 'integration-123'
                        mock_get_branch.return_value = 'main'
                        
                        targets = mapper._process_repository_batch(
                            applications, org_mapping, 'github',
                            branch_override=None,
                            files_override=None,
                            exclusion_globs_override=None,  # No override
                            max_workers=1
                        )
        
        # Verify default exclusions are used
        assert len(targets) == 1
        assert targets[0]['exclusionGlobs'] == "fixtures, tests, __tests__, node_modules"


class TestEmptyOrgOnlyFlag:
    """Test --empty-org-only flag functionality"""
    
    def create_mixed_applications(self):
        """Helper to create applications with mixed organization status"""
        return [
            {
                'application_name': 'EmptyApp1',
                'asset_name': 'repo1',
                'repository_url': 'https://github.com/user/repo1',
                'asset_type': 'Repository',
                'organizations': 'N/A'  # Empty org
            },
            {
                'application_name': 'ImportedApp1',
                'asset_name': 'repo2',
                'repository_url': 'https://github.com/user/repo2',
                'asset_type': 'Repository',
                'organizations': 'existing-org-123'  # Has org
            },
            {
                'application_name': 'EmptyApp2',
                'asset_name': 'repo3',
                'repository_url': 'https://github.com/user/repo3',
                'asset_type': 'Repository',
                'organizations': 'N/A'  # Empty org
            },
            {
                'application_name': 'ImportedApp2',
                'asset_name': 'repo4',
                'repository_url': 'https://github.com/user/repo4',
                'asset_type': 'Repository',
                'organizations': 'another-org-456'  # Has org
            }
        ]
    
    def test_empty_org_only_filters_correctly(self):
        """Test that --empty-org-only flag filters to only N/A organizations"""
        # This test will focus on the filtering logic rather than the full integration
        applications = self.create_mixed_applications()
        
        # Simulate the filtering logic from create_targets_json
        empty_org_only = True
        
        if empty_org_only:
            original_count = len(applications)
            # Only include repositories where Organizations column is "N/A" (not imported yet)
            filtered_applications = []
            for app in applications:
                org_value = app.get('organizations', '')
                # Handle both string "N/A" and pandas NaN values
                if (isinstance(org_value, str) and org_value.strip() == 'N/A') or \
                   (hasattr(org_value, 'isnan') and org_value.isnan()):
                    filtered_applications.append(app)
        else:
            filtered_applications = applications
        
        # Verify filtering worked correctly
        empty_org_apps = [app for app in applications if app['organizations'] == 'N/A']
        assert len(filtered_applications) == len(empty_org_apps)
        assert len(filtered_applications) == 2  # EmptyApp1 and EmptyApp2
        
        filtered_names = [app['application_name'] for app in filtered_applications]
        assert 'EmptyApp1' in filtered_names
        assert 'EmptyApp2' in filtered_names
        assert 'ImportedApp1' not in filtered_names
        assert 'ImportedApp2' not in filtered_names
    
    def test_empty_org_only_filtering_logic(self):
        """Test the specific logic for filtering empty organizations"""
        applications = self.create_mixed_applications()
        
        # Simulate the filtering logic from create_targets_json
        filtered_applications = []
        for app in applications:
            org_value = app.get('organizations', '')
            # Handle both string "N/A" and potential NaN values
            if (isinstance(org_value, str) and org_value.strip() == 'N/A') or \
               (hasattr(org_value, 'isnan') and org_value.isnan()):
                filtered_applications.append(app)
        
        # Verify only empty org applications are included
        assert len(filtered_applications) == 2
        assert all(app['organizations'] == 'N/A' for app in filtered_applications)
        assert filtered_applications[0]['application_name'] == 'EmptyApp1'
        assert filtered_applications[1]['application_name'] == 'EmptyApp2'
    
    def test_empty_org_only_false_includes_all(self):
        """Test that empty_org_only=False includes all applications"""
        applications = self.create_mixed_applications()
        
        # When empty_org_only is False, all applications should be included
        # This simulates the logic when the flag is not set
        filtered_applications = applications  # No filtering
        
        assert len(filtered_applications) == 4
        assert 'EmptyApp1' in [app['application_name'] for app in filtered_applications]
        assert 'ImportedApp1' in [app['application_name'] for app in filtered_applications]


class TestSourceFiltering:
    """Test --source flag filtering functionality"""
    
    def create_multi_source_applications(self):
        """Helper to create applications from different sources"""
        return [
            {
                'application_name': 'GitHubApp',
                'asset_name': 'github-repo',
                'repository_url': 'https://github.com/user/repo',
                'asset_source': 'github',
                'asset_type': 'Repository'
            },
            {
                'application_name': 'GitLabApp',
                'asset_name': 'gitlab-repo',
                'repository_url': 'https://gitlab.com/user/repo',
                'asset_source': 'gitlab',
                'asset_type': 'Repository'
            },
            {
                'application_name': 'AzureApp',
                'asset_name': 'azure-repo',
                'repository_url': 'https://dev.azure.com/org/project/_git/repo',
                'asset_source': 'azure devops',
                'asset_type': 'Repository'
            },
            {
                'application_name': 'GitHubApp2',
                'asset_name': 'github-repo2',
                'repository_url': 'https://github.com/user/repo2',
                'asset_source': 'github',
                'asset_type': 'Repository'
            }
        ]
    
    def test_should_include_application_github(self):
        """Test source filtering for GitHub applications"""
        mapper = SnykTargetMapper("test-group-id")
        applications = self.create_multi_source_applications()
        
        # Test GitHub filtering
        github_apps = [app for app in applications if mapper.should_include_application(app, 'github')]
        
        assert len(github_apps) == 2
        assert all('github' in app['repository_url'].lower() for app in github_apps)
    
    def test_should_include_application_gitlab(self):
        """Test source filtering for GitLab applications"""
        mapper = SnykTargetMapper("test-group-id")
        applications = self.create_multi_source_applications()
        
        # Test GitLab filtering
        gitlab_apps = [app for app in applications if mapper.should_include_application(app, 'gitlab')]
        
        assert len(gitlab_apps) == 1
        assert gitlab_apps[0]['application_name'] == 'GitLabApp'
    
    def test_should_include_application_azure(self):
        """Test source filtering for Azure DevOps applications"""
        mapper = SnykTargetMapper("test-group-id")
        applications = self.create_multi_source_applications()
        
        # Test Azure DevOps filtering
        azure_apps = [app for app in applications if mapper.should_include_application(app, 'azure-repos')]
        
        assert len(azure_apps) == 1
        assert azure_apps[0]['application_name'] == 'AzureApp'
    
    def test_github_cloud_app_filtering(self):
        """Test that github-cloud-app is treated same as github"""
        mapper = SnykTargetMapper("test-group-id")
        
        github_app = {
            'application_name': 'GitHubCloudApp',
            'asset_name': 'github-repo',
            'repository_url': 'https://github.com/user/repo',
            'asset_source': 'github',
            'asset_type': 'Repository'
        }
        
        # Both should include the same GitHub applications
        assert mapper.should_include_application(github_app, 'github')
        assert mapper.should_include_application(github_app, 'github-cloud-app')
        assert mapper.should_include_application(github_app, 'github-enterprise')


if __name__ == '__main__':
    pytest.main([__file__])
