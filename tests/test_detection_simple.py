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


class TestApplicationFiltering:
    """Test application filtering logic"""
    
    def test_should_include_application_gitlab(self):
        """Test GitLab application filtering"""
        mapper = SnykTargetMapper("test-group-id")
        
        # GitLab URL match
        gitlab_app = {'repository_url': 'https://gitlab.com/user/repo', 'asset_source': 'other'}
        assert mapper.should_include_application(gitlab_app, 'gitlab') == True
        
        # Non-GitLab should not match GitLab filter
        github_app = {'repository_url': 'https://github.com/user/repo', 'asset_source': 'other'}
        assert mapper.should_include_application(github_app, 'gitlab') == False
    
    def test_should_include_application_github(self):
        """Test GitHub application filtering"""
        mapper = SnykTargetMapper("test-group-id")
        
        # GitHub URL match
        github_app = {'repository_url': 'https://github.com/user/repo', 'asset_source': 'other'}
        assert mapper.should_include_application(github_app, 'github') == True
        
        # Non-GitHub should not match GitHub filter
        gitlab_app = {'repository_url': 'https://gitlab.com/user/repo', 'asset_source': 'other'}
        assert mapper.should_include_application(gitlab_app, 'github') == False
    
    def test_should_include_application_asset_source_match(self):
        """Test asset source matching"""
        mapper = SnykTargetMapper("test-group-id")
        
        # Asset source match for GitLab
        app = {'repository_url': 'https://example.com/repo', 'asset_source': 'gitlab ci/cd'}
        assert mapper.should_include_application(app, 'gitlab') == True
        
        # Asset source match for GitHub
        app = {'repository_url': 'https://example.com/repo', 'asset_source': 'github actions'}
        assert mapper.should_include_application(app, 'github') == True
    
    def test_should_include_application_empty_values(self):
        """Test filtering with empty/missing values"""
        mapper = SnykTargetMapper("test-group-id")
        
        # Empty values should not match
        app = {'repository_url': '', 'asset_source': ''}
        assert mapper.should_include_application(app, 'github') == False


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
                result = mapper.get_default_branch(url, 'github')
                assert isinstance(result, (str, type(None)))
                if result is not None:
                    assert len(result) > 0
            except Exception as e:
                # Should handle errors gracefully
                assert False, f"URL processing failed for {url}: {e}"
    
    def test_unsupported_source_fallback(self):
        """Test fallback behavior for unsupported source types"""
        mapper = SnykTargetMapper("test-group-id")
        
        branch = mapper.get_default_branch('https://unknown.scm/user/repo', 'unknown')
        assert branch == 'main'  # Should fallback to main


class TestGitLabProjectLogic:
    """Test GitLab project detection logic"""
    
    def test_gitlab_project_info_non_gitlab_source(self):
        """Test GitLab project info when source is not GitLab"""
        mapper = SnykTargetMapper("test-group-id")
        
        project_info = mapper.get_gitlab_project_info('https://gitlab.com/user/project', 'github')
        assert project_info is None
    
    def test_gitlab_project_info_gitlab_source(self):
        """Test GitLab project info when source is GitLab"""
        mapper = SnykTargetMapper("test-group-id")
        
        # This will likely return None due to no auth, but shouldn't crash
        project_info = mapper.get_gitlab_project_info('https://gitlab.com/user/project', 'gitlab')
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

