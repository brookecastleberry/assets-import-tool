#!/usr/bin/env python3
"""
Simplified tests for detection functionality
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch, Mock

# Add root directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from create_targets import SnykTargetMapper


class TestWorkflowDetection:
    """Test workflow detection logic"""
    
    def test_detect_workflow_type_gitlab(self):
        """Test workflow detection identifies GitLab repositories"""
        mapper = SnykTargetMapper("test-group-id")
        
        applications = [
            {'repository_url': 'https://github.com/user/repo1'},
            {'repository_url': 'https://gitlab.com/user/repo2'},  # GitLab repo
            {'repository_url': 'https://github.com/user/repo3'}
        ]
        
        workflow = mapper.detect_workflow_type(applications)
        assert workflow == 'gitlab'
    
    def test_detect_workflow_type_general(self):
        """Test workflow detection defaults to general for non-GitLab"""
        mapper = SnykTargetMapper("test-group-id")
        
        applications = [
            {'repository_url': 'https://github.com/user/repo1'},
            {'repository_url': 'https://dev.azure.com/org/project/_git/repo'}
        ]
        
        workflow = mapper.detect_workflow_type(applications)
        assert workflow == 'general'
    
    def test_detect_workflow_type_self_hosted_gitlab(self):
        """Test workflow detection with self-hosted GitLab"""
        mapper = SnykTargetMapper("test-group-id")
        
        applications = [
            {'repository_url': 'https://gitlab.company.com/team/project'}
        ]
        
        workflow = mapper.detect_workflow_type(applications)
        assert workflow == 'gitlab'
    
    def test_detect_workflow_type_empty_applications(self):
        """Test workflow detection with empty applications list"""
        mapper = SnykTargetMapper("test-group-id")
        
        applications = []
        
        workflow = mapper.detect_workflow_type(applications)
        assert workflow == 'general'


class TestSourceFiltering:
    """Test source filtering logic"""
    
    def test_should_include_application_github_url(self):
        """Test GitHub filtering based on repository URL"""
        mapper = SnykTargetMapper("test-group-id")
        
        github_app = {
            'application_name': 'GitHubApp',
            'repository_url': 'https://github.com/user/repo',
            'asset_source': 'github'
        }
        
        assert mapper.should_include_application(github_app, 'github')
        assert mapper.should_include_application(github_app, 'github-cloud-app')
        assert mapper.should_include_application(github_app, 'github-enterprise')
    
    def test_should_include_application_gitlab_url(self):
        """Test GitLab filtering based on repository URL"""
        mapper = SnykTargetMapper("test-group-id")
        
        gitlab_app = {
            'application_name': 'GitLabApp',
            'repository_url': 'https://gitlab.com/user/repo',
            'asset_source': 'gitlab'
        }
        
        assert mapper.should_include_application(gitlab_app, 'gitlab')
        assert not mapper.should_include_application(gitlab_app, 'github')
    
    def test_should_include_application_azure_source(self):
        """Test Azure filtering based on asset source"""
        mapper = SnykTargetMapper("test-group-id")
        
        azure_app = {
            'application_name': 'AzureApp',
            'repository_url': 'https://dev.azure.com/org/project/_git/repo',
            'asset_source': 'azure devops'
        }
        
        assert mapper.should_include_application(azure_app, 'azure-repos')
        assert not mapper.should_include_application(azure_app, 'github')
        assert not mapper.should_include_application(azure_app, 'gitlab')


class TestBranchDetectionLogic:
    """Test branch detection logic with mocked responses"""
    
    def test_git_url_cleanup(self):
        """Test that .git suffix is properly handled"""
        mapper = SnykTargetMapper("test-group-id")
        
        test_urls = [
            'https://github.com/user/repo.git',
            'https://github.com/user/repo',
            'git@github.com:user/repo.git'
        ]
        
        for url in test_urls:
            # Test that the URL processing doesn't crash
            # The actual API call would be mocked in integration tests
            try:
                # This will likely return 'main' as fallback, but shouldn't crash
                result = mapper.get_default_branch(url)
                assert isinstance(result, str)
                assert len(result) > 0
            except Exception as e:
                # Should handle errors gracefully
                assert False, f"URL processing failed for {url}: {e}"
    
    def test_unsupported_source_fallback(self):
        """Test fallback behavior for unsupported source types"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'unsupported-scm'
        
        branch = mapper.get_default_branch('https://unknown.scm/user/repo')
        assert branch == 'main'  # Should fallback to main


class TestGitLabProjectLogic:
    """Test GitLab project detection logic"""
    
    def test_gitlab_project_info_non_gitlab_source(self):
        """Test GitLab project info when source is not GitLab"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'github'  # Not GitLab
        
        project_info = mapper.get_gitlab_project_info('https://gitlab.com/user/project')
        assert project_info is None
    
    def test_gitlab_project_info_gitlab_source(self):
        """Test GitLab project info when source is GitLab"""
        mapper = SnykTargetMapper("test-group-id")
        mapper.source_type = 'gitlab'
        
        # This will likely return None due to no auth, but shouldn't crash
        project_info = mapper.get_gitlab_project_info('https://gitlab.com/user/project')
        # Should return None or a dict, not crash
        assert project_info is None or isinstance(project_info, dict)


class TestURLPatternMatching:
    """Test URL pattern matching for different services"""
    
    def test_github_url_patterns(self):
        """Test recognition of various GitHub URL patterns"""
        mapper = SnykTargetMapper("test-group-id")
        
        github_urls = [
            'https://github.com/user/repo',
            'https://github.com/user/repo.git',
            'git@github.com:user/repo.git',
            'https://github.enterprise.com/user/repo'
        ]
        
        for url in github_urls:
            app = {
                'application_name': 'TestApp',
                'repository_url': url,
                'asset_source': 'github'
            }
            assert mapper.should_include_application(app, 'github'), f"Failed for URL: {url}"
    
    def test_gitlab_url_patterns(self):
        """Test recognition of various GitLab URL patterns"""
        mapper = SnykTargetMapper("test-group-id")
        
        gitlab_urls = [
            'https://gitlab.com/user/repo',
            'https://gitlab.com/group/subgroup/project',
            'https://gitlab.company.com/team/project'
        ]
        
        for url in gitlab_urls:
            app = {
                'application_name': 'TestApp',
                'repository_url': url,
                'asset_source': 'gitlab'
            }
            assert mapper.should_include_application(app, 'gitlab'), f"Failed for URL: {url}"
    
    def test_azure_url_patterns(self):
        """Test recognition of Azure DevOps URL patterns"""
        mapper = SnykTargetMapper("test-group-id")
        
        azure_app = {
            'application_name': 'AzureApp',
            'repository_url': 'https://dev.azure.com/organization/project/_git/repository',
            'asset_source': 'azure devops'
        }
        
        assert mapper.should_include_application(azure_app, 'azure-repos')


if __name__ == '__main__':
    pytest.main([__file__])

