"""
Snyk Targets Creator - Phase 2

This script creates import targets JSON from CSV file, mapping to existing Snyk organizations
and automatically detecting the appropriate integration types.
"""

import json
import csv
import io
from typing import Dict, List, Optional
import argparse
import sys
import os
import requests
import re
import time
from concurrent.futures import ThreadPoolExecutor
import threading
import logging
from datetime import datetime
from src.logging_utils import setup_logging, log_progress, log_error_with_context
from src.csv_utils import read_applications_from_csv
from src.api import rate_limit, get_auth_headers, display_auth_status, make_request_with_retry
from src.file_utils import sanitize_path, sanitize_input_path, safe_write_json, validate_file_exists, log_error_and_exit, validate_positive_integer

# Disable SSL warnings for corporate networks/proxies
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not available, using basic CSV parsing")


class SnykTargetMapper:
    def __init__(self, group_id: str, orgs_json_file: str = "snyk-created-orgs.json"):
        self.group_id = group_id
        self.orgs_json_file = orgs_json_file
        self.org_data = None
        self.logger = setup_logging('create_targets')
        # Rate limiting configuration - auto-tune based on repository count
        self.rate_limit_requests_per_minute = 1000  # Will be auto-tuned
        self.request_interval = 60.0 / self.rate_limit_requests_per_minute  # Will be recalculated
        self.last_request_time = 0
        self.request_lock = threading.Lock()
        # Concurrent processing configuration - auto-tune based on repository count  
        self.max_workers = 10  # Will be auto-tuned
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1  # Initial delay in seconds
        self.retry_backoff = 2  # Exponential backoff multiplier
    
    def detect_workflow_type(self, applications: List[Dict]) -> str:
        """
        Detect which workflow to use based on CSV content
        """
        # Check for GitLab repository URLs
        has_gitlab_repos = any(
            app.get('repository_url') and 
            'gitlab' in str(app.get('repository_url', '')).lower()
            for app in applications
        )
        
        if has_gitlab_repos:
            return 'gitlab'
        else:
            return 'general'
    
    def should_include_application(self, app: Dict, source_type: str) -> bool:
        """
        Determine if an application should be included based on its Repository URL and Asset Source
        Uses consistent URL OR Asset Source matching for all SCM types
        """
        asset_source = app.get('asset_source', '').lower().strip()
        repository_url = app.get('repository_url', '').lower().strip()
        
        # Unified SCM pattern definitions - consistent for all SCM types
        scm_patterns = {
            # GitHub variants (all use same patterns)
            'github': {
                'url_patterns': ['github.com'],
                'source_keywords': ['github']
            },
            'github-cloud-app': {
                'url_patterns': ['github.com'],
                'source_keywords': ['github']
            },
            'github-enterprise': {
                'url_patterns': ['github.com', 'github.'],  # Handles enterprise domains
                'source_keywords': ['github']
            },
            # GitLab (now checks both URL and source)
            'gitlab': {
                'url_patterns': ['gitlab.com', 'gitlab.'],  # Handles self-hosted GitLab
                'source_keywords': ['gitlab']
            },
            # Azure DevOps (now checks both URL and source)
            'azure-repos': {
                'url_patterns': ['dev.azure.com', 'visualstudio.com'],  # TFS/VSTS legacy
                'source_keywords': ['azure', 'devops']
            }
        }
        
        # Get patterns for the specified source type
        patterns = scm_patterns.get(source_type)
        if not patterns:
            return False
        
        # Check URL patterns - consistent for all SCM types
        url_match = any(
            pattern in repository_url 
            for pattern in patterns.get('url_patterns', [])
        )
        
        # Check Asset Source keywords - consistent for all SCM types  
        source_match = any(
            keyword in asset_source
            for keyword in patterns.get('source_keywords', [])
        )
        
        # Unified logic: URL OR Asset Source match (consistent across all SCMs)
        return url_match or source_match
    
    def _auto_tune_performance(self, repository_count: int, source_type: str, user_max_workers: Optional[int] = None, user_rate_limit: Optional[int] = None):
        """Auto-tune performance settings based on repository count and source type with detailed logging"""
        
        if self.logger:
            self.logger.debug(f"🔧 Starting auto-tuning for {repository_count} repositories, source: {source_type}")
            self.logger.debug(f"   User overrides - max_workers: {user_max_workers}, rate_limit: {user_rate_limit}")
        
        # Auto-tune max workers based on repository count
        if user_max_workers is not None:
            self.max_workers = user_max_workers
            print(f"🔧 Using user-specified max workers: {self.max_workers}")
            if self.logger:
                self.logger.info(f"Using user-specified max workers: {self.max_workers}")
        else:
            # More aggressive defaults - we're generating import data, not calling SCM APIs heavily
            if repository_count <= 100:
                self.max_workers = 10
                tuning_reason = "Small dataset (≤100 repos)"
            elif repository_count <= 500:
                self.max_workers = 20
                tuning_reason = "Medium dataset (≤500 repos)"
            elif repository_count <= 2000:
                self.max_workers = 30
                tuning_reason = "Large dataset (≤2000 repos)"
            elif repository_count <= 5000:
                self.max_workers = 40
                tuning_reason = "Very large dataset (≤5000 repos)"
            else:
                self.max_workers = 50
                tuning_reason = "Extremely large dataset (>5000 repos)"
            
            print(f"🎯 Auto-tuned max workers for {repository_count} repositories: {self.max_workers}")
            if self.logger:
                self.logger.info(f"Auto-tuned max workers: {self.max_workers} ({tuning_reason})")
                self.logger.debug(f"   Worker tuning logic: {repository_count} repos → {self.max_workers} workers")
        
        # Auto-tune rate limiting based on source type and repository count
        if user_rate_limit is not None:
            self.rate_limit_requests_per_minute = user_rate_limit
            print(f"🔧 Using user-specified rate limit: {self.rate_limit_requests_per_minute} requests/minute")
            if self.logger:
                self.logger.info(f"Using user-specified rate limit: {self.rate_limit_requests_per_minute} requests/minute")
        else:
            # More aggressive rate limits since we're only making occasional API calls
            if 'github' in source_type:
                # GitHub: 5000 requests/hour = 83/minute, use 80 for aggressive performance
                base_rate = 80
                rate_reason = "GitHub API limits (5000/hour, using 80/min for safety)"
            elif 'gitlab' in source_type:
                # GitLab: 300 requests/minute, use 250 for aggressive performance
                base_rate = 250
                rate_reason = "GitLab API limits (300/min, using 250/min for safety)"
            elif 'azure' in source_type:
                # Azure DevOps: Aggressive estimate
                base_rate = 150
                rate_reason = "Azure DevOps estimated limits (using 150/min)"
            else:
                # Unknown source, still be more aggressive
                base_rate = 60
                rate_reason = "Unknown source type (conservative 60/min)"
            
            # Only scale down rate limit for extremely large repository counts
            if repository_count > 10000:
                self.rate_limit_requests_per_minute = int(base_rate * 0.8)  # 20% reduction
                scale_reason = "Scaled down 20% for >10k repositories"
            else:
                self.rate_limit_requests_per_minute = base_rate
                scale_reason = "No scaling needed"
            
            print(f"🎯 Auto-tuned rate limit for {source_type} with {repository_count} repositories: {self.rate_limit_requests_per_minute} requests/minute")
            if self.logger:
                self.logger.info(f"Auto-tuned rate limit: {self.rate_limit_requests_per_minute} requests/minute")
                self.logger.debug(f"   Rate limit reasoning: {rate_reason}")
                self.logger.debug(f"   Scaling applied: {scale_reason}")
        
        # Recalculate request interval
        self.request_interval = 60.0 / self.rate_limit_requests_per_minute
        if self.logger:
            self.logger.debug(f"   Calculated request interval: {self.request_interval:.3f} seconds between requests")
        
        # Show performance summary
        estimated_time_minutes = (repository_count / self.max_workers) * 0.1  # Much faster estimate: 0.1 min per repo per worker
        print(f"📊 High-Performance Profile:")
        print(f"   • Repositories: {repository_count}")
        print(f"   • Concurrent Workers: {self.max_workers}")
        print(f"   • Rate Limit: {self.rate_limit_requests_per_minute} requests/minute")
        print(f"   • Estimated Time: {estimated_time_minutes:.0f}-{estimated_time_minutes*2:.0f} minutes")
        
        if self.logger:
            self.logger.info(f"Performance auto-tuning completed: {self.max_workers} workers, {self.rate_limit_requests_per_minute} req/min")
            self.logger.debug(f"   Performance metrics - Est. time: {estimated_time_minutes:.1f}-{estimated_time_minutes*2:.1f} min, Request interval: {self.request_interval:.3f}s")
        
        # Add performance tip
        if repository_count > 1000:
            print(f"💡 Performance Tip: Consider using --branch main to skip API branch detection for maximum speed")

    def load_organizations_from_json(self) -> None:
        """
        Load organization data from snyk-created-orgs.json file
        """
        try:
            with open(self.orgs_json_file, 'r') as f:
                data = json.load(f)
                self.org_data = data.get('orgData', [])
                if self.logger:
                    self.logger.info(f"Loaded {len(self.org_data)} organizations from {self.orgs_json_file}")
                print(f"Loaded {len(self.org_data)} organizations from {self.orgs_json_file}")
        except FileNotFoundError:
            msg = f"Error: {self.orgs_json_file} file not found"
            print(msg)
            if self.logger:
                self.logger.error(msg)
            self.org_data = []
        except json.JSONDecodeError as e:
            msg = f"Error parsing JSON file {self.orgs_json_file}: {e}"
            print(msg)
            if self.logger:
                self.logger.error(msg)
            self.org_data = []
    
    def get_organizations_from_group(self) -> List[Dict]:
        """
        Get organizations from the loaded JSON file
        """
        if self.org_data is None:
            self.load_organizations_from_json()
        
        org_info = []
        for org in self.org_data:
            org_info.append({
                'id': org.get('id'),
                'name': org.get('name'),
                'display_name': org.get('name'),
                'slug': org.get('slug')
            })
        
        print(f"Found {len(org_info)} organizations in group {self.group_id}")
        return org_info
    
    def get_integrations_for_org(self, org_id: str) -> Dict[str, str]:
        """
        Get integrations for a specific organization from loaded JSON data
        """
        if self.org_data is None:
            self.load_organizations_from_json()
        
        for org in self.org_data:
            if org.get('id') == org_id:
                integrations = org.get('integrations', {})
                print(f"Found {len(integrations)} integrations for org {org_id}")
                return integrations
                
        print(f"No organization found with ID {org_id}")
        return {}
    
    def find_integration_id(self, org_id: str, integration_type: str) -> Optional[str]:
        """
        Find the integration ID for a specific integration type in an organization
        """
        if self.org_data is None:
            self.load_organizations_from_json()
        
        integrations = self.get_integrations_for_org(org_id)
        
        # Map common integration type names to what's stored in the JSON
        integration_mapping = {
            'github': 'github',
            'github-cloud-app': 'github-cloud-app',
            'gitlab': 'gitlab',
            'azure-repos': 'azure-repos',
            'github-enterprise': 'github-enterprise'
        }
        
        target_type = integration_mapping.get(integration_type.lower(), integration_type.lower())
        integration_id = integrations.get(target_type)
        
        if not integration_id:
            print(f"No integration of type '{integration_type}' found for org {org_id}")
            print(f"Available integrations: {list(integrations.keys())}")
        
        return integration_id
    
    def read_applications_from_csv(self, csv_file_path: str) -> List[Dict]:
        """
        Read applications from CSV file with enhanced parsing
        """
        applications = read_applications_from_csv(csv_file_path, self.logger)
        print(f"Found {len(applications)} repository entries from CSV (filtered by Type = Repository)")
        return applications
    
    def _display_auth_status(self):
        """
        Display authentication status for SCM APIs
        """
        display_auth_status(getattr(self, 'source_type', 'github'))

    def get_default_branch(self, repository_url: str) -> Optional[str]:
        """
        Fetch the default branch for a repository from its API
        Returns None if unable to determine
        """
        try:
            if repository_url.endswith('.git'):
                repository_url = repository_url[:-4]
            if 'github.com' in repository_url and self.source_type in ['github', 'github-cloud-app', 'github-enterprise']:
                match = re.search(r'github\.com[/:]([^/]+)/([^/]+?)/?$', repository_url)
                if match:
                    owner, repo = match.groups()
                    api_url = f"https://api.github.com/repos/{owner}/{repo}"
                    auth_headers = get_auth_headers('github', self.source_type, self.logger)
                    response = make_request_with_retry(api_url, self.max_retries, self.retry_delay, self.retry_backoff, lambda: self._rate_limit_wrapper(), headers=auth_headers, logger=self.logger)
                    if response and response.status_code == 200:
                        repo_data = response.json()
                        return repo_data.get('default_branch', 'main')
            elif ('gitlab.com' in repository_url or 'gitlab' in repository_url.lower()) and self.source_type == 'gitlab':
                project_path = None
                api_base = None
                if 'gitlab.com' in repository_url:
                    match = re.search(r'gitlab\.com[/:](.+?)/?$', repository_url)
                    if match:
                        project_path = match.group(1)
                        api_base = "https://gitlab.com/api/v4"
                else:
                    match = re.search(r'https?://([^/]*gitlab[^/]*)/(.+?)/?$', repository_url)
                    if match:
                        gitlab_host, project_path = match.groups()
                        api_base = f"https://{gitlab_host}/api/v4"
                    else:
                        match = re.search(r'git@([^:]*gitlab[^:]*):(.+?)(?:\.git)?/?$', repository_url)
                        if match:
                            gitlab_host, project_path = match.groups()
                            api_base = f"https://{gitlab_host}/api/v4"
                if project_path and api_base:
                    encoded_path = requests.utils.quote(project_path, safe='')
                    api_url = f"{api_base}/projects/{encoded_path}"
                    auth_headers = get_auth_headers('gitlab', self.source_type, self.logger)
                    response = make_request_with_retry(api_url, self.max_retries, self.retry_delay, self.retry_backoff, lambda: self._rate_limit_wrapper(), headers=auth_headers, logger=self.logger)
                    if response and response.status_code == 200:
                        project_data = response.json()
                        return project_data.get('default_branch', 'main')
                    elif response and response.status_code == 404:
                        if auth_headers:
                            print(f"⚠️  GitLab project not found or no access: {repository_url}")
                        else:
                            print(f"⚠️  GitLab project not found or private: {repository_url} (set GITLAB_TOKEN)")
                        return 'main'
                    elif response and response.status_code in [401, 403]:
                        print(f"⚠️  GitLab authentication issue for {repository_url} (check GITLAB_TOKEN)")
                        return 'main'
            elif 'dev.azure.com' in repository_url and self.source_type == 'azure-repos':
                auth_headers = get_auth_headers('azure', self.source_type, self.logger)
                if auth_headers:
                    match = re.search(r'dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)', repository_url)
                    if match:
                        organization, project, repo = match.groups()
                        api_url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo}?api-version=6.0"
                        response = make_request_with_retry(api_url, self.max_retries, self.retry_delay, self.retry_backoff, lambda: self._rate_limit_wrapper(), headers=auth_headers, logger=self.logger)
                        if response and response.status_code == 200:
                            repo_data = response.json()
                            return repo_data.get('defaultBranch', 'refs/heads/main').replace('refs/heads/', '')
                return 'main'
            return 'main'
        except Exception as e:
            print(f"⚠️  Could not determine default branch for {repository_url}: {e}")
            return 'main'

    def _rate_limit_wrapper(self):
        # Wrapper to use api.py's rate_limit with instance state
        # Use a list for last_request_time to allow mutation in api.py
        if not hasattr(self, '_last_request_time_ref'):
            self._last_request_time_ref = [self.last_request_time]
        rate_limit(self.request_lock, self._last_request_time_ref, self.request_interval)
    
    def get_gitlab_project_info(self, repository_url: str) -> Optional[Dict]:
        """
        Fetch GitLab project information including project ID and default branch
        Returns dict with 'id' and 'default_branch' or None if unable to determine
        """
        try:
            # Only make API calls if source is GitLab
            if not hasattr(self, 'source_type') or self.source_type != 'gitlab':
                return None
                
            # Remove .git suffix if present
            if repository_url.endswith('.git'):
                repository_url = repository_url[:-4]
            
            # Check if this is a GitLab repository
            if 'gitlab.com' in repository_url or 'gitlab' in repository_url.lower():
                project_path = None
                api_base = None
                
                # Extract project path from URL like https://gitlab.com/group/project
                if 'gitlab.com' in repository_url:
                    match = re.search(r'gitlab\.com[/:](.+?)/?$', repository_url)
                    if match:
                        project_path = match.group(1)
                        api_base = "https://gitlab.com/api/v4"
                else:
                    # Try custom GitLab instance pattern
                    # Handle formats like: https://gitlab.company.com/group/project
                    match = re.search(r'https?://([^/]*gitlab[^/]*)/(.+?)/?$', repository_url)
                    if match:
                        gitlab_host, project_path = match.groups()
                        api_base = f"https://{gitlab_host}/api/v4"
                    else:
                        # Try SSH format: git@gitlab.company.com:group/project.git
                        match = re.search(r'git@([^:]*gitlab[^:]*):(.+?)(?:\.git)?/?$', repository_url)
                        if match:
                            gitlab_host, project_path = match.groups()
                            api_base = f"https://{gitlab_host}/api/v4"
                
                if project_path and api_base:
                    # URL encode the project path
                    encoded_path = requests.utils.quote(project_path, safe='')
                    
                    api_url = f"{api_base}/projects/{encoded_path}"
                    
                    # Get authentication headers if available
                    auth_headers = get_auth_headers('gitlab', self.source_type, self.logger)
                    
                    if auth_headers:
                        print(f"🔐 Using GitLab authentication for project: {project_path}")
                    else:
                        print(f"⚠️  No GitLab authentication - private projects may fail: {project_path}")
                    
                    response = make_request_with_retry(api_url, self.max_retries, self.retry_delay, self.retry_backoff, lambda: self._rate_limit_wrapper(), headers=auth_headers, logger=self.logger)
                    if response and response.status_code == 200:
                        project_data = response.json()
                        return {
                            'id': project_data.get('id'),
                            'default_branch': project_data.get('default_branch', 'main')
                        }
                    elif response and response.status_code == 404:
                        if auth_headers:
                            print(f"⚠️  GitLab project not found or no access: {repository_url} (check project path and token permissions)")
                        else:
                            print(f"⚠️  GitLab project not found or private: {repository_url} (set GITLAB_TOKEN for private projects)")
                        return None
                    elif response and response.status_code == 401:
                        print(f"⚠️  GitLab authentication failed for {repository_url} (check GITLAB_TOKEN)")
                        return None
                    elif response and response.status_code == 403:
                        print(f"⚠️  GitLab access forbidden for {repository_url} (check token permissions)")
                        return None
                    elif response:
                        print(f"⚠️  GitLab API returned {response.status_code} for {repository_url}")
                        return None
                    else:
                        print(f"⚠️  Failed to get GitLab project info for {repository_url}")
                        return None
            
            return None
            
        except Exception as e:
            print(f"⚠️  Could not fetch GitLab project info for {repository_url}: {e}")
            return None
    
    def create_gitlab_targets(self, applications: List[Dict], org_mapping: Dict[str, str], source_type: str, branch_override: Optional[str] = None, files_override: Optional[str] = None, exclusion_globs_override: Optional[str] = None) -> List[Dict]:
        """
        Create GitLab targets structure
        Applications are already filtered by source type and limit in create_targets_json().
        """
        targets = []
        
        for app in applications:
            app_name = app['application_name']
            org_id = org_mapping.get(app_name)
            
            if not org_id:
                print(f"⚠️  No organization found for application: {app_name}")
                continue
            
            # Find integration using the specified source type
            integration_id = self.find_integration_id(org_id, source_type)
            if not integration_id:
                print(f"⚠️  No {source_type} integration found for org {org_id} (app: {app_name})")
                continue
            
            # Get GitLab project ID and default branch from repository URL
            repository_url = app.get('repository_url', '').strip()
            
            if not repository_url:
                print(f"⚠️  No repository URL for {app_name}")
                continue
            
            # Fetch project info from GitLab API
            project_id = None
            detected_default_branch = None
            
            gitlab_info = self.get_gitlab_project_info(repository_url)
            if gitlab_info and gitlab_info.get('id'):
                project_id = gitlab_info['id']
                detected_default_branch = gitlab_info.get('default_branch')
                print(f"📋 Auto-detected GitLab project ID for {app_name}: {project_id}")
            else:
                print(f"⚠️  Could not determine GitLab project ID for {app_name} from URL: {repository_url}")
                continue
            
            # Create target object
            target = {
                "orgId": org_id,
                "integrationId": integration_id,
                "target": {
                    "id": project_id
                }
            }
            
            # Add branch - prioritize override, then auto-detected from API
            if branch_override:
                # Use the command line override branch for all repositories
                target["target"]["branch"] = branch_override
                print(f"📋 Using override branch '{branch_override}' for {app_name}")
            elif detected_default_branch:
                # Use the default branch detected from GitLab API
                target["target"]["branch"] = detected_default_branch
                print(f"📋 Using GitLab default branch '{detected_default_branch}' for {app_name}")
            else:
                # Fallback to detecting branch separately
                default_branch = self.get_default_branch(repository_url)
                if default_branch:
                    target["target"]["branch"] = default_branch
                    print(f"📋 Auto-detected default branch '{default_branch}' for {app_name}")
            
            # Add files if specified from override
            if files_override:
                # Convert comma-separated string to array of objects
                file_paths = [path.strip() for path in files_override.split(',') if path.strip()]
                if file_paths:
                    target["files"] = [{"path": path} for path in file_paths]
                    print(f"📄 Using override files for {app_name}: {len(file_paths)} files")
            
            # Add exclusionGlobs - use override or default
            if exclusion_globs_override is not None:
                # Use override (even if empty string)
                target["exclusionGlobs"] = exclusion_globs_override
                if exclusion_globs_override:
                    print(f"🚫 Using override exclusionGlobs for {app_name}: {exclusion_globs_override}")
                else:
                    print(f"🚫 Using empty exclusionGlobs for {app_name} (no exclusions)")
            else:
                # Use default exclusionGlobs
                target["exclusionGlobs"] = "fixtures, tests, __tests__, node_modules"
            
            targets.append(target)
        
        return targets
    

    def _process_repository_batch(self, repositories: List[Dict], org_mapping: Dict[str, str], source_type: str, branch_override: Optional[str], files_override: Optional[str], exclusion_globs_override: Optional[str], max_workers: int = 10) -> List[Dict]:
        """Process repositories concurrently with thread pool"""
        def process_single_repository(app):
            try:
                app_name = app['application_name']
                repository_url = app.get('repository_url', '').strip()
                if not repository_url:
                    print(f"⚠️  Skipping {app_name}: no repository URL")
                    return None
                org_id = org_mapping.get(app_name)
                if not org_id:
                    print(f"⚠️  No org found for application: {app_name}")
                    return None
                integration_id = self.find_integration_id(org_id, source_type)
                if not integration_id:
                    print(f"⚠️  No {source_type} integration found for org {org_id} (app: {app_name})")
                    return None
                if repository_url.endswith('.git'):
                    repository_url = repository_url[:-4]
                # Parse owner/repo
                if 'github.com' in repository_url or 'gitlab' in repository_url:
                    parts = repository_url.rstrip('/').split('/')
                    owner = parts[-2]
                    repo_name = parts[-1]
                elif 'dev.azure.com' in repository_url:
                    if '_git' in repository_url:
                        parts = repository_url.split('_git/')
                        repo_name = parts[-1].rstrip('/')
                        project_parts = parts[0].rstrip('/').split('/')
                        owner = project_parts[-1]
                    else:
                        print(f"⚠️  Unsupported Azure DevOps URL format: {repository_url}")
                        return None
                else:
                    parts = repository_url.rstrip('/').split('/')
                    if len(parts) >= 2:
                        owner = parts[-2]
                        repo_name = parts[-1]
                    else:
                        print(f"⚠️  Cannot parse repository URL: {repository_url}")
                        return None
                target = {
                    "orgId": org_id,
                    "integrationId": integration_id,
                    "target": {
                        "name": repo_name,
                        "owner": owner
                    }
                }
                if branch_override:
                    target["target"]["branch"] = branch_override
                    print(f"📋 Using override branch '{branch_override}' for {app_name}")
                else:
                    default_branch = self.get_default_branch(repository_url)
                    if default_branch:
                        target["target"]["branch"] = default_branch
                        print(f"📋 Auto-detected default branch '{default_branch}' for {app_name}")
                if files_override:
                    file_paths = [path.strip() for path in files_override.split(',') if path.strip()]
                    if file_paths:
                        target["files"] = [{"path": path} for path in file_paths]
                        print(f"📄 Using override files for {app_name}: {len(file_paths)} files")
                if exclusion_globs_override is not None:
                    target["exclusionGlobs"] = exclusion_globs_override
                    if exclusion_globs_override:
                        print(f"🚫 Using override exclusionGlobs for {app_name}: {exclusion_globs_override}")
                    else:
                        print(f"🚫 Using empty exclusionGlobs for {app_name} (no exclusions)")
                else:
                    target["exclusionGlobs"] = "fixtures, tests, __tests__, node_modules"
                return target
            except Exception as e:
                print(f"❌ Error processing {app.get('application_name', 'Unknown')}: {e}")
                return None
        targets = []
        total_repos = len(repositories)
        print(f"🚀 Processing {total_repos} repositories with {max_workers} concurrent workers...")
        
        if self.logger:
            self.logger.info(f"Starting parallel processing: {total_repos} repositories, {max_workers} workers")
            self.logger.debug(f"Processing configuration: timeout=60s, rate_limit={self.rate_limit_requests_per_minute}/min")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_single_repository, app) for app in repositories]
            completed = 0
            errors = 0
            
            for i, future in enumerate(futures):
                try:
                    result = future.result(timeout=60)
                    if result:
                        targets.append(result)
                        if self.logger:
                            app_name = repositories[i].get('application_name', f'repo-{i+1}')
                            self.logger.debug(f"✅ Successfully processed {app_name} (target created)")
                    else:
                        if self.logger:
                            app_name = repositories[i].get('application_name', f'repo-{i+1}')
                            self.logger.debug(f"⚪ Processed {app_name} (no target created - filtered or error)")
                    
                    completed += 1
                    
                    # Progress logging - more frequent in debug mode
                    if completed % 100 == 0 or completed == total_repos:
                        print(f"📊 Progress: {completed}/{total_repos} repositories processed ({len(targets)} targets created)")
                        if self.logger:
                            log_progress(self.logger, completed, total_repos, "repository")
                    elif completed % 25 == 0 and self.logger:
                        # Debug-only frequent progress updates
                        log_progress(self.logger, completed, total_repos, "repository")
                        
                except Exception as e:
                    errors += 1
                    completed += 1
                    error_msg = f"Repository processing failed: {e}"
                    print(f"❌ {error_msg}")
                    
                    if self.logger:
                        app_name = repositories[i].get('application_name', f'repo-{i+1}') if i < len(repositories) else 'unknown'
                        log_error_with_context(self.logger, f"Processing failed for {app_name}", e)
        
        if self.logger:
            self.logger.info(f"Parallel processing completed: {len(targets)} targets created, {errors} errors")
            if errors > 0:
                self.logger.warning(f"Processing completed with {errors} errors out of {total_repos} repositories")
        
        return targets

    def create_general_targets(self, applications: List[Dict], org_mapping: Dict[str, str], source_type: str, branch_override: Optional[str], files_override: Optional[str], exclusion_globs_override: Optional[str], max_workers: int) -> List[Dict]:
        """Create general targets structure for GitHub, Azure DevOps, etc."""
        # Applications are already filtered by source type and limit in create_targets_json()
        return self._process_repository_batch(
            applications,
            org_mapping,
            source_type,
            branch_override,
            files_override,
            exclusion_globs_override,
            max_workers
        )
    
    def create_targets_json(self, csv_file_path: str, output_json_path: str, source_type: str, empty_org_only: bool = False, limit: Optional[int] = None, rows: Optional[str] = None, branch_override: Optional[str] = None, files_override: Optional[str] = None, exclusion_globs_override: Optional[str] = None, max_workers: Optional[int] = None, rate_limit: Optional[int] = None):
        # Sanitize CSV path for safety (output path sanitized in safe_write_json)
        csv_file_path = sanitize_input_path(csv_file_path)
        self.logger.info(f"Sanitized CSV path: {csv_file_path}")
        """
        Create import-targets.json file with proper org mapping
        """
        # Store source_type for use throughout the process
        self.source_type = source_type
        
        # Check and display authentication status
        self._display_auth_status()
        
        # Get existing organizations
        existing_orgs = self.get_organizations_from_group()
        
        # Create mapping from application name to org ID
        org_mapping = {}
        for org in existing_orgs:
            org_mapping[org['display_name']] = org['id']
        
        print(f"Organization mapping:")
        for app_name, org_id in org_mapping.items():
            print(f"  {app_name} -> {org_id}")
        
        # Read applications from CSV
        applications = self.read_applications_from_csv(csv_file_path)
        
        if not applications:
            print("❌ No applications found in CSV")
            return
        
        # Filter by specific row numbers FIRST (highest precedence)
        if rows:
            try:
                # Parse row numbers supporting both individual (2,5,8) and ranges (2-5)
                row_numbers = []
                for part in rows.split(','):
                    part = part.strip()
                    if '-' in part:
                        # Handle range like "2-5"
                        start, end = part.split('-', 1)
                        start, end = int(start.strip()), int(end.strip())
                        if start > end:
                            print(f"❌ Error: Invalid range '{part}' - start ({start}) must be <= end ({end})")
                            return
                        row_numbers.extend(range(start, end + 1))
                    else:
                        # Handle individual row number
                        row_numbers.append(int(part))
                
                # Remove duplicates and sort
                row_numbers = sorted(set(row_numbers))
                row_indices = [row - 1 for row in row_numbers]  # Convert to 0-based
                
                # Validate row numbers
                max_rows = len(applications)
                invalid_rows = [row for row in row_numbers if row < 1 or row > max_rows]
                if invalid_rows:
                    print(f"❌ Error: Invalid row numbers {invalid_rows}. CSV has {max_rows} data rows (valid range: 1-{max_rows})")
                    return
                
                # Filter to specific rows
                original_count = len(applications)
                applications = [applications[i] for i in row_indices if i < len(applications)]
                filtered_count = len(applications)
                
                # Show expanded row numbers for clarity
                if len(row_numbers) <= 10:
                    expanded_rows = ','.join(map(str, row_numbers))
                else:
                    expanded_rows = f"{','.join(map(str, row_numbers[:5]))}...{','.join(map(str, row_numbers[-2:]))} ({len(row_numbers)} total)"
                
                print(f"🔍 Filtering by specific row numbers: {rows}")
                if rows != expanded_rows:
                    print(f"🔍 Expanded to rows: {expanded_rows}")
                print(f"📊 Selected {filtered_count}/{original_count} applications from specified rows")
                
                if not applications:
                    print("❌ No applications found for specified row numbers")
                    return
                    
            except ValueError as e:
                print(f"❌ Error parsing row numbers '{rows}': {e}")
                print("   Examples: --rows 2,5,8 (individual) or --rows 2-5 (range) or --rows 2,5-8,10 (mixed)")
                return
        
        # Auto-tune performance settings based on repository count
        self._auto_tune_performance(len(applications), source_type, max_workers, rate_limit)
        
        # Filter applications if empty_org_only flag is set
        if empty_org_only:
            original_count = len(applications)
            # Only include repositories where Organizations column is "N/A" (not imported yet)
            # Handle both string "N/A" and pandas NaN values
            def is_not_imported(app):
                orgs_value = app.get('organizations', '')
                
                # Handle pandas NaN values (which show up as float nan)
                if str(orgs_value).lower() in ['nan', 'n/a'] or orgs_value == '' or orgs_value is None:
                    return True
                    
                # Handle string values
                orgs_str = str(orgs_value).strip().upper()
                return orgs_str in ['N/A', 'NAN'] or orgs_str == ''
            
            applications = [app for app in applications if is_not_imported(app)]
            filtered_count = len(applications)
            print(f"🔍 Filtering for repositories not yet imported (Organizations = 'N/A'): {filtered_count}/{original_count} applications remaining")
            
            if not applications:
                print("✅ All repositories have already been imported to Snyk organizations!")
                return
        
        # Filter by source type FIRST (before applying limit)
        print(f"🔍 Filtering applications by source type: {source_type}")
        original_count = len(applications)
        filtered_applications = []
        for app in applications:
            app_name = app['application_name']
            org_id = org_mapping.get(app_name)
            if not org_id:
                print(f"⚠️  No organization found for application: {app_name}")
                continue
            if not self.should_include_application(app, source_type):
                continue
            repository_url = app.get('repository_url', '').strip()
            if not repository_url:
                print(f"⚠️  No repository URL for {app_name}")
                continue
            filtered_applications.append(app)
        
        if not filtered_applications:
            print("❌ No applications match the source type filter")
            return
            
        filtered_count = len(filtered_applications)
        print(f"🔍 Filtered to {filtered_count}/{original_count} applications matching {source_type}")
        
        # Apply limit AFTER filtering by source type
        if limit and limit > 0:
            pre_limit_count = len(filtered_applications)
            filtered_applications = filtered_applications[:limit]
            limited_count = len(filtered_applications)
            print(f"📊 Applying limit: processing {limited_count}/{pre_limit_count} repositories (--limit {limit})")
        
        # Detect workflow type
        workflow_type = self.detect_workflow_type(filtered_applications)
        print(f"Detected workflow type: {workflow_type}")
        
        # Create targets based on workflow type
        if workflow_type == 'gitlab':
            targets = self.create_gitlab_targets(filtered_applications, org_mapping, source_type, branch_override, files_override, exclusion_globs_override)
        else:
            targets = self.create_general_targets(
                filtered_applications,
                org_mapping,
                source_type,
                branch_override,
                files_override,
                exclusion_globs_override,
                self.max_workers
            )
        
        if not targets:
            print("❌ No targets created")
            return
        
        # Create final JSON structure
        targets_json = {"targets": targets}
        
        # Write to file with error handling
        safe_write_json(targets_json, output_json_path, self.logger)
        print(f"   Targets created: {len(targets)}")
        
        # Summary by organization
        org_counts = {}
        for target in targets:
            org_id = target['orgId']
            org_name = next((org['display_name'] for org in existing_orgs if org['id'] == org_id), org_id)
            org_counts[org_name] = org_counts.get(org_name, 0) + 1
        
        print(f"\n📊 Targets by organization:")
        for org_name, count in sorted(org_counts.items()):
            print(f"   {org_name}: {count} targets")


def main():
    parser = argparse.ArgumentParser(
        description="Create Snyk import targets from CSV file (Phase 2) - Enterprise optimized with auto-tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🚀 Enterprise Auto-Tuning:
  Performance settings are automatically optimized based on your repository count
  and source type. No manual tuning required for optimal performance!
  
  Auto-tuning provides:
  - Optimal concurrent workers (5-20 based on repository count)
  - Safe API rate limits (based on GitHub/GitLab/Azure limits)
  - Progress reporting and error handling
  
Integration Type Strategy:
  The --source parameter specifies which integration type to use from your 
  organizations JSON file. This must match an integration type that exists 
  in your snyk-created-orgs.json file.
  
  Common integration types:
  - github: For GitHub.com repositories (auto-tuned: 60 req/min)
  - github-cloud-app: For GitHub Cloud App integration  
  - github-enterprise: For GitHub Enterprise repositories  
  - gitlab: For GitLab repositories (auto-tuned: 200 req/min)
  - azure-repos: For Azure DevOps repositories (auto-tuned: 100 req/min)

Examples:
  # Basic usage - auto-tuned for optimal performance
  python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github
  
  # Enterprise scale (10,000+ repos) - still auto-tuned
  python create_targets.py --group-id abc123 --csv-file large-dataset.csv --orgs-json snyk-created-orgs.json --source github
  
  # Custom performance tuning (optional)
  python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github --max-workers 25 --rate-limit 30
  
  # Override files for all repositories (scan only specific files)
  python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github --files "package.json,requirements.txt"
  
  # Override exclusionGlobs for all repositories  
  python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github --exclusion-globs "test,spec,node_modules"
  
  # No exclusions (empty string)
  python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github --exclusion-globs ""
        """
    )
    
    parser.add_argument('--group-id', required=True, help='Snyk Group ID')
    parser.add_argument('--csv-file', required=True, help='CSV file path')
    parser.add_argument('--orgs-json', required=True, help='Path to organizations JSON file containing org data and integration IDs')
    parser.add_argument('--source', required=True, help='Integration type to use from organizations JSON (github, github-cloud-app, github-enterprise, gitlab, azure-repos)')
    parser.add_argument('--rows', help='Specific CSV row numbers to process (1-based indexing). Takes precedence over all other filters. Supports individual rows (2,5,8) and ranges (2-5). Example: --rows 2,5-8,10')
    parser.add_argument('--output', help='Output JSON file path (default: import-targets.json)')
    parser.add_argument('--empty-org-only', action='store_true', help='Only process repositories where Organizations column is "N/A" (repositories not yet imported to Snyk)')
    parser.add_argument('--limit', type=int, help='Maximum number of repository targets to process (useful for batching large datasets)')
    parser.add_argument('--branch', help='Override branch for all repositories (default: auto-detect from CSV or repository API)')
    parser.add_argument('--files', help='Override files for all repositories - comma-separated list of file paths to scan (if not specified, files field is omitted from import data)')
    parser.add_argument('--exclusion-globs', help='Override exclusionGlobs for all repositories (default: "fixtures, tests, __tests__, node_modules")')
    
    # Performance and scaling options (optional - auto-tuned by default)
    parser.add_argument('--max-workers', type=int, help='Maximum number of concurrent workers for API requests (default: auto-tuned based on repository count)')
    parser.add_argument('--rate-limit', type=int, help='Maximum requests per minute for API calls (default: auto-tuned based on source type and repository count)')
    
    # Debugging options
    parser.add_argument('--debug', action='store_true', help='Enable detailed debug logging (API requests, responses, timing, and error traces)')
    
    args = parser.parse_args()

    # Setup logging with debug support
    logger = setup_logging('create_targets', debug=args.debug)
    logger.info("=== Starting create_targets ===")
    logger.info(f"Command line arguments: {vars(args)}")

    # Input validation
    # Sanitize input paths (output path sanitized in safe_write_json)
    try:
        args.csv_file = sanitize_input_path(args.csv_file)
        args.orgs_json = sanitize_input_path(args.orgs_json)
    except ValueError as ve:
        log_error_and_exit(f"❌ Error: {ve}", logger)

    validate_file_exists(args.csv_file, logger)
    validate_positive_integer(args.limit, "--limit", logger)
    validate_positive_integer(args.max_workers, "--max-workers", logger)
    validate_positive_integer(args.rate_limit, "--rate-limit", logger)
        
    valid_sources = ['github', 'github-cloud-app', 'github-enterprise', 'gitlab', 'azure-repos']
    if args.source not in valid_sources:
        log_error_and_exit(f"❌ Error: Invalid source type '{args.source}'. Valid options: {', '.join(valid_sources)}", logger)
        
    validate_file_exists(args.orgs_json, logger)

    source_type = args.source
    message = f"Using integration type: {source_type}"
    print(message)
    logger.info(message)
    
    # Generate automatic filename if not provided
    if not args.output:
        output_path = "import-targets.json"
    else:
        # Sanitize output path for safety
        try:
            output_path = sanitize_path(args.output)
        except ValueError as ve:
            log_error_and_exit(f"❌ Error: {ve}", logger)
    
    mapper = SnykTargetMapper(args.group_id, args.orgs_json)
    
    message = f"Creating targets file: {output_path}"
    print(message)
    logger.info(message)
    
    if args.max_workers or args.rate_limit:
        perf_msg = f"⚙️  Using custom performance settings..."
        print(perf_msg)
        logger.info(perf_msg)
    else:
        perf_msg = f"🎯 Using auto-tuned performance settings (optimal for your repository count)"
        print(perf_msg)
        logger.info(perf_msg)
    
    try:
        mapper.create_targets_json(args.csv_file, output_path, source_type, args.empty_org_only, args.limit, args.rows, args.branch, args.files, args.exclusion_globs, args.max_workers, args.rate_limit)
        
        success_msg = f"✅ Phase 2 complete! Use this file to import repositories: {output_path}"
        print(f"\n{success_msg}")
        logger.info(success_msg)
        logger.info("=== create_targets completed successfully ===")
        
    except Exception as e:
        error_msg = f"❌ Fatal error during target creation: {e}"
        print(f"\n{error_msg}")
        logger.error(error_msg)
        logger.error("=== create_targets failed ===")
        sys.exit(1)


if __name__ == '__main__':
    main()

