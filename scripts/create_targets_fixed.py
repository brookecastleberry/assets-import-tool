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
    
    def load_organizations_from_json(self) -> None:
        """
        Load organization data from snyk-created-orgs.json file
        """
        try:
            with open(self.orgs_json_file, 'r') as f:
                data = json.load(f)
                self.org_data = data.get('orgData', [])
                print(f"Loaded {len(self.org_data)} organizations from {self.orgs_json_file}")
        except FileNotFoundError:
            print(f"Error: {self.orgs_json_file} file not found")
            self.org_data = []
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file {self.orgs_json_file}: {e}")
            self.org_data = []
    
    def get_organizations_from_group(self) -> List[Dict]:
        """
        Get organizations from the loaded JSON file
        """
        if self.org_data is None:
            self.load_organizations_from_json()
            
        # Extract relevant information in the expected format
        org_info = []
        for org in self.org_data:
            org_info.append({
                'id': org.get('id'),
                'name': org.get('name'),
                'display_name': org.get('name'),  # Use name as display_name
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
        integrations = self.get_integrations_for_org(org_id)
        
        # Map common integration type names to what's stored in the JSON
        integration_mapping = {
            'github': 'github',
            'github-cloud-app': 'github-cloud-app',
            'gitlab': 'gitlab',
            'bitbucket-cloud': 'bitbucket-cloud',
            'bitbucket-server': 'bitbucket-server',
            'azure-repos': 'azure-repos',
            'github-enterprise': 'github-enterprise'
        }
        
        target_type = integration_mapping.get(integration_type.lower(), integration_type.lower())
        
        # Look up the integration ID directly from the integrations dict
        integration_id = integrations.get(target_type)
        if integration_id:
            return integration_id
        
        print(f"No integration of type '{target_type}' found for org {org_id}")
        print(f"Available integrations: {list(integrations.keys())}")
        return None
    
    def read_applications_from_csv(self, csv_file_path: str) -> List[Dict]:
        """
        Read applications from CSV file with enhanced parsing
        """
        applications = []
        
        try:
            if PANDAS_AVAILABLE:
                # Try reading normally first
                df = pd.read_csv(csv_file_path)
                
                # Check if 'Application' is in columns, if not, try skipping first row
                if 'Application' not in df.columns:
                    print("Application column not found, trying to skip header row...")
                    try:
                        df = pd.read_csv(csv_file_path, skiprows=1)
                    except Exception as e:
                        print(f"Error reading CSV with skiprows=1: {e}")
                        return []
                
                if 'Application' not in df.columns:
                    print("Error: 'Application' column not found in CSV")
                    print(f"Available columns: {list(df.columns)}")
                    return []
                
                if 'Type' not in df.columns:
                    print("Error: 'Type' column not found in CSV")
                    print(f"Available columns: {list(df.columns)}")
                    return []
                
                # Process each row
                for index, row in df.iterrows():
                    # Only process rows where Type = Repository
                    asset_type = str(row.get("Type", "")).strip()
                    if asset_type.lower() != 'repository':
                        continue
                    
                    app_name = str(row.get("Application", "")).strip()
                    if app_name and app_name.lower() not in ['nan', 'n/a', '', 'none', 'null']:
                        # Handle multiple applications separated by commas
                        app_names = [name.strip() for name in app_name.split(',') 
                                    if name.strip() and name.strip().lower() not in ['n/a', 'nan', '', 'none', 'null']]
                        
                        for single_app in app_names:
                            applications.append({
                                'application_name': single_app,
                                'asset_type': str(row.get("Type", "")),
                                'asset_name': str(row.get("Asset", "")),
                                'repository_url': str(row.get("Repository URL", "")),
                                'asset_source': str(row.get("Asset Source", "")),
                                'organizations': str(row.get("Organizations", "")),
                                'row_index': index
                            })
            else:
                # Basic CSV parsing fallback
                with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                    # Try to detect if we need to skip the first row
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    
                    # Check if first line contains "Application" column
                    first_line = csvfile.readline().strip().lower()
                    csvfile.seek(0)
                    
                    start_row = 0
                    if first_line and 'application' not in first_line:
                        # Skip first row (title row)
                        csvfile.readline()
                        start_row = 1
                    
                    reader = csv.DictReader(csvfile)
                    
                    if 'Application' not in reader.fieldnames:
                        print("Error: 'Application' column not found in CSV")
                        print(f"Available columns: {reader.fieldnames}")
                        return []
                    
                    if 'Type' not in reader.fieldnames:
                        print("Error: 'Type' column not found in CSV")
                        print(f"Available columns: {reader.fieldnames}")
                        return []
                    
                    for index, row in enumerate(reader, start=start_row):
                        # Only process rows where Type = Repository
                        asset_type = row.get("Type", "").strip()
                        if asset_type.lower() != 'repository':
                            continue
                        
                        app_name = row.get("Application", "").strip()
                        if app_name and app_name.lower() not in ['nan', 'n/a', '', 'none', 'null']:
                            # Handle multiple applications separated by commas
                            app_names = [name.strip() for name in app_name.split(',') 
                                        if name.strip() and name.strip().lower() not in ['n/a', 'nan', '', 'none', 'null']]
                            
                            for single_app in app_names:
                                applications.append({
                                    'application_name': single_app,
                                    'asset_type': row.get("Type", ""),
                                    'asset_name': row.get("Asset", ""),
                                    'repository_url': row.get("Repository URL", ""),
                                    'asset_source': row.get("Asset Source", ""),
                                    'row_index': index
                                })
        
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return []
        
        print(f"Found {len(applications)} repository entries from CSV (filtered by Type = Repository)")
        return applications
    
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
        Determine if an application should be included based on its Repository URL and the specified source type
        """
        # Get both asset source and repository URL for better filtering
        asset_source = app.get('asset_source', '').lower().strip()
        repository_url = app.get('repository_url', '').lower().strip()
        
        # For GitHub source types, check both Asset Source and Repository URL
        if source_type in ['github', 'github-cloud-app', 'github-enterprise']:
            # Include if repository URL is GitHub or if Asset Source mentions GitHub
            if 'github.com' in repository_url or 'github' in asset_source:
                return True
        
        # For other source types, use the original logic
        source_mapping = {
            'gitlab': ['gitlab'],
            'azure-repos': ['azure', 'devops'],
            'bitbucket-cloud': ['bitbucket'],
            'bitbucket-server': ['bitbucket']
        }
        
        keywords = source_mapping.get(source_type, [])
        
        # Check if any of the keywords appear in the asset source
        for keyword in keywords:
            if keyword in asset_source:
                return True
        
        return False
    
    def _auto_tune_performance(self, repository_count: int, source_type: str, user_max_workers: Optional[int] = None, user_rate_limit: Optional[int] = None):
        """Auto-tune performance settings based on repository count and source type"""
        
        # Auto-tune max workers based on repository count
        if user_max_workers is not None:
            self.max_workers = user_max_workers
            print(f"🔧 Using user-specified max workers: {self.max_workers}")
        else:
            # More aggressive defaults - we're generating import data, not calling SCM APIs heavily
            if repository_count <= 100:
                self.max_workers = 10
            elif repository_count <= 500:
                self.max_workers = 20
            elif repository_count <= 2000:
                self.max_workers = 30
            elif repository_count <= 5000:
                self.max_workers = 40
            else:
                self.max_workers = 50
            print(f"🎯 Auto-tuned max workers for {repository_count} repositories: {self.max_workers}")
        
        # Auto-tune rate limiting based on source type and repository count
        if user_rate_limit is not None:
            self.rate_limit_requests_per_minute = user_rate_limit
            print(f"🔧 Using user-specified rate limit: {self.rate_limit_requests_per_minute} requests/minute")
        else:
            # More aggressive rate limits since we're only making occasional API calls
            if 'github' in source_type:
                # GitHub: 5000 requests/hour = 83/minute, use 80 for aggressive performance
                base_rate = 80
            elif 'gitlab' in source_type:
                # GitLab: 300 requests/minute, use 250 for aggressive performance
                base_rate = 250
            elif 'bitbucket' in source_type:
                # Bitbucket: 1000 requests/hour = 16/minute, use 15 for aggressive performance
                base_rate = 15
            elif 'azure' in source_type:
                # Azure DevOps: Aggressive estimate
                base_rate = 150
            else:
                # Unknown source, still be more aggressive
                base_rate = 60
            
            # Only scale down rate limit for extremely large repository counts
            if repository_count > 10000:
                self.rate_limit_requests_per_minute = int(base_rate * 0.8)  # 20% reduction
            else:
                self.rate_limit_requests_per_minute = base_rate
            
            print(f"🎯 Auto-tuned rate limit for {source_type} with {repository_count} repositories: {self.rate_limit_requests_per_minute} requests/minute")
        
        # Recalculate request interval
        self.request_interval = 60.0 / self.rate_limit_requests_per_minute
        
        # Show performance summary
        estimated_time_minutes = (repository_count / self.max_workers) * 0.1  # Much faster estimate: 0.1 min per repo per worker
        print(f"📊 High-Performance Profile:")
        print(f"   • Repositories: {repository_count}")
        print(f"   • Concurrent Workers: {self.max_workers}")
        print(f"   • Rate Limit: {self.rate_limit_requests_per_minute} requests/minute")
        print(f"   • Estimated Time: {estimated_time_minutes:.0f}-{estimated_time_minutes*2:.0f} minutes")
        
        # Add performance tip
        if repository_count > 1000:
            print(f"💡 Performance Tip: Consider using --branch main to skip API branch detection for maximum speed")

    def _rate_limit(self):
        """Apply rate limiting to API requests"""
        with self.request_lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            
            if time_since_last_request < self.request_interval:
                sleep_time = self.request_interval - time_since_last_request
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
    
    def _get_auth_headers(self, scm_type: str) -> Optional[Dict[str, str]]:
        """Get authentication headers for SCM APIs based on environment variables"""
        if scm_type == 'github':
            token = os.getenv('GITHUB_TOKEN')
            if token:
                return {'Authorization': f'token {token}'}
        elif scm_type == 'gitlab':
            token = os.getenv('GITLAB_TOKEN')
            if token:
                return {'PRIVATE-TOKEN': token}
        elif scm_type == 'bitbucket':
            token = os.getenv('BITBUCKET_TOKEN')
            username = os.getenv('BITBUCKET_USERNAME')
            if token and username:
                import base64
                auth_string = f"{username}:{token}"
                encoded_auth = base64.b64encode(auth_string.encode()).decode()
                return {'Authorization': f'Basic {encoded_auth}'}
            elif token:
                # App password without username - use token as username
                import base64
                auth_string = f"{token}:{token}"
                encoded_auth = base64.b64encode(auth_string.encode()).decode()
                return {'Authorization': f'Basic {encoded_auth}'}
        elif scm_type == 'azure':
            token = os.getenv('AZURE_DEVOPS_TOKEN')
            if token:
                import base64
                auth_string = f":{token}"
                encoded_auth = base64.b64encode(auth_string.encode()).decode()
                return {'Authorization': f'Basic {encoded_auth}'}
        
        return None

    def _display_auth_status(self):
        """Display authentication status for SCM APIs"""
        print("🔐 SCM Authentication Status:")
        
        # Check GitHub
        github_token = os.getenv('GITHUB_TOKEN')
        if github_token:
            print("  ✅ GitHub: Authenticated (GITHUB_TOKEN found)")
        else:
            print("  ⚠️  GitHub: Unauthenticated (60 req/hour limit)")
        
        # Check GitLab
        gitlab_token = os.getenv('GITLAB_TOKEN')
        if gitlab_token:
            print("  ✅ GitLab: Authenticated (GITLAB_TOKEN found)")
        else:
            print("  ⚠️  GitLab: Unauthenticated (10 req/min limit)")
        
        # Check Bitbucket
        bitbucket_token = os.getenv('BITBUCKET_TOKEN')
        if bitbucket_token:
            print("  ✅ Bitbucket: Authenticated (BITBUCKET_TOKEN found)")
        else:
            print("  ⚠️  Bitbucket: Unauthenticated (1000 req/hour limit)")
        
        # Check Azure DevOps
        azure_token = os.getenv('AZURE_DEVOPS_TOKEN')
        if azure_token:
            print("  ✅ Azure DevOps: Authenticated (AZURE_DEVOPS_TOKEN found)")
        else:
            print("  ⚠️  Azure DevOps: No authentication (API calls disabled)")
        
        print()

    def _make_request_with_retry(self, url: str, timeout: int = 10, headers: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
        """Make HTTP request with exponential backoff retry logic"""
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                response = requests.get(url, timeout=timeout, headers=headers, verify=False)
                
                # Success cases
                if response.status_code == 200:
                    return response
                
                # Rate limit hit - wait longer
                elif response.status_code == 429:
                    wait_time = self.retry_delay * (self.retry_backoff ** attempt) * 2  # Extra wait for rate limits
                    print(f"⚠️  Rate limit hit for {url}, waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait_time)
                    continue
                
                # Client errors (4xx) - don't retry
                elif 400 <= response.status_code < 500:
                    print(f"⚠️  Client error {response.status_code} for {url}, not retrying")
                    return None
                
                # Server errors (5xx) - retry
                elif response.status_code >= 500:
                    wait_time = self.retry_delay * (self.retry_backoff ** attempt)
                    print(f"⚠️  Server error {response.status_code} for {url}, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(wait_time)
                    continue
                
            except requests.exceptions.RequestException as e:
                wait_time = self.retry_delay * (self.retry_backoff ** attempt)
                print(f"⚠️  Request exception for {url}: {e}, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)
                continue
        
        print(f"❌ Failed to fetch {url} after {self.max_retries} attempts")
        return None
    
    def _process_repository_batch(self, repositories: List[Dict], org_mapping: Dict[str, str], source_type: str, branch_override: Optional[str], files_override: Optional[str], exclusion_globs_override: Optional[str], max_workers: int = 10) -> List[Dict]:
        """Process repositories concurrently with thread pool"""
        
        def process_single_repository(app):
            """Process a single repository to create target"""
            try:
                app_name = app['application_name']
                repository_url = app.get('repository_url', '').strip()
                
                if not repository_url:
                    print(f"⚠️  Skipping {app_name}: no repository URL")
                    return None
                
                # Find matching org
                org_id = org_mapping.get(app_name)
                if not org_id:
                    print(f"⚠️  No org found for application: {app_name}")
                    return None
                
                # Use the specified source type to find integration ID
                integration_id = self.find_integration_id(org_id, source_type)
                if not integration_id:
                    print(f"⚠️  No {source_type} integration found for org {org_id} (app: {app_name})")
                    return None
                
                # Parse repository URL to extract owner and name
                if repository_url.endswith('.git'):
                    repository_url = repository_url[:-4]
                
                # Handle different URL formats
                if 'github.com' in repository_url:
                    # GitHub: https://github.com/owner/repo
                    parts = repository_url.rstrip('/').split('/')
                    owner = parts[-2]
                    repo_name = parts[-1]
                elif 'gitlab' in repository_url:
                    # GitLab: https://gitlab.com/group/subgroup/project or custom GitLab instance
                    parts = repository_url.rstrip('/').split('/')
                    owner = parts[-2]
                    repo_name = parts[-1]
                elif 'dev.azure.com' in repository_url:
                    # Azure DevOps: https://dev.azure.com/organization/project/_git/repository
                    if '_git' in repository_url:
                        parts = repository_url.split('_git/')
                        repo_name = parts[-1].rstrip('/')
                        # Extract owner from the project part
                        project_parts = parts[0].rstrip('/').split('/')
                        owner = project_parts[-1]  # This would be the project name
                    else:
                        print(f"⚠️  Unsupported Azure DevOps URL format: {repository_url}")
                        return None
                elif 'bitbucket.org' in repository_url:
                    # Bitbucket: https://bitbucket.org/owner/repo
                    parts = repository_url.rstrip('/').split('/')
                    owner = parts[-2]
                    repo_name = parts[-1]
                else:
                    # Generic approach - take last two parts
                    parts = repository_url.rstrip('/').split('/')
                    if len(parts) >= 2:
                        owner = parts[-2]
                        repo_name = parts[-1]
                    else:
                        print(f"⚠️  Cannot parse repository URL: {repository_url}")
                        return None
                
                # Create target object
                target = {
                    "orgId": org_id,
                    "integrationId": integration_id,
                    "target": {
                        "name": repo_name,
                        "owner": owner
                    }
                }
                
                # Add branch - prioritize override, then auto-detect
                if branch_override:
                    # Use the command line override branch for all repositories
                    target["target"]["branch"] = branch_override
                    print(f"📋 Using override branch '{branch_override}' for {app_name}")
                else:
                    # Auto-detect default branch from repository
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
            target["exclusionGlobs"] = "fixtures, tests, __tests__, node_modules"                return target
                
            except Exception as e:
                print(f"❌ Error processing {app.get('application_name', 'Unknown')}: {e}")
                return None
        
        # Process repositories concurrently
        targets = []
        total_repos = len(repositories)
        print(f"🚀 Processing {total_repos} repositories with {max_workers} concurrent workers...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = [executor.submit(process_single_repository, app) for app in repositories]
            
            # Collect results with progress reporting
            completed = 0
            for future in futures:
                try:
                    result = future.result(timeout=60)  # 60 second timeout per repo
                    if result:
                        targets.append(result)
                    completed += 1
                    
                    # Progress reporting
                    if completed % 100 == 0 or completed == total_repos:
                        print(f"📊 Progress: {completed}/{total_repos} repositories processed ({len(targets)} targets created)")
                        
                except Exception as e:
                    print(f"❌ Repository processing failed: {e}")
                    completed += 1
        
        return targets

    def get_default_branch(self, repository_url: str) -> Optional[str]:
        """
        Fetch the default branch for a repository from its API
        Returns None if unable to determine
        """
        try:
            # Remove .git suffix if present
            if repository_url.endswith('.git'):
                repository_url = repository_url[:-4]
            
            # GitHub repositories - only call API if source is GitHub-based
            if 'github.com' in repository_url and self.source_type in ['github', 'github-cloud-app', 'github-enterprise']:
                # Extract owner/repo from URL like https://github.com/owner/repo
                match = re.search(r'github\.com[/:]([^/]+)/([^/]+?)/?$', repository_url)
                if match:
                    owner, repo = match.groups()
                    api_url = f"https://api.github.com/repos/{owner}/{repo}"
                    
                    # Get authentication headers if available
                    auth_headers = self._get_auth_headers('github')
                    
                    response = self._make_request_with_retry(api_url, headers=auth_headers)
                    if response and response.status_code == 200:
                        repo_data = response.json()
                        return repo_data.get('default_branch', 'main')
            
            # GitLab repositories - only call API if source is GitLab
            elif ('gitlab.com' in repository_url or 'gitlab' in repository_url.lower()) and self.source_type == 'gitlab':
                project_path = None
                api_base = None
                
                # Extract project path and API base for different GitLab formats
                if 'gitlab.com' in repository_url:
                    match = re.search(r'gitlab\.com[/:](.+?)/?$', repository_url)
                    if match:
                        project_path = match.group(1)
                        api_base = "https://gitlab.com/api/v4"
                else:
                    # Handle custom GitLab instances
                    match = re.search(r'https?://([^/]*gitlab[^/]*)/(.+?)/?$', repository_url)
                    if match:
                        gitlab_host, project_path = match.groups()
                        api_base = f"https://{gitlab_host}/api/v4"
                    else:
                        # Try SSH format
                        match = re.search(r'git@([^:]*gitlab[^:]*):(.+?)(?:\.git)?/?$', repository_url)
                        if match:
                            gitlab_host, project_path = match.groups()
                            api_base = f"https://{gitlab_host}/api/v4"
                
                if project_path and api_base:
                    # URL encode the project path
                    encoded_path = requests.utils.quote(project_path, safe='')
                    api_url = f"{api_base}/projects/{encoded_path}"
                    
                    # Get authentication headers if available
                    auth_headers = self._get_auth_headers('gitlab')
                    
                    response = self._make_request_with_retry(api_url, headers=auth_headers)
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
            
            # Azure DevOps repositories - call API if source is Azure and token is available
            elif 'dev.azure.com' in repository_url and self.source_type == 'azure-repos':
                # Get authentication headers
                auth_headers = self._get_auth_headers('azure')
                
                if auth_headers:
                    # Extract organization, project, and repo from Azure DevOps URL
                    # Format: https://dev.azure.com/organization/project/_git/repository
                    match = re.search(r'dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)', repository_url)
                    if match:
                        organization, project, repo = match.groups()
                        api_url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo}?api-version=6.0"
                        
                        response = self._make_request_with_retry(api_url, headers=auth_headers)
                        if response and response.status_code == 200:
                            repo_data = response.json()
                            return repo_data.get('defaultBranch', 'refs/heads/main').replace('refs/heads/', '')
                
                # Fallback when no token or API call fails
                return 'main'
            
            # Bitbucket repositories - only call API if source is Bitbucket
            elif 'bitbucket.org' in repository_url and self.source_type in ['bitbucket-cloud', 'bitbucket-server']:
                # Extract owner/repo from URL like https://bitbucket.org/owner/repo
                match = re.search(r'bitbucket\.org[/:]([^/]+)/([^/]+?)/?$', repository_url)
                if match:
                    owner, repo = match.groups()
                    api_url = f"https://api.bitbucket.org/2.0/repositories/{owner}/{repo}"
                    
                    # Get authentication headers if available
                    auth_headers = self._get_auth_headers('bitbucket')
                    
                    response = self._make_request_with_retry(api_url, headers=auth_headers)
                    if response and response.status_code == 200:
                        repo_data = response.json()
                        return repo_data.get('mainbranch', {}).get('name', 'main')
            
            # Default fallback
            return 'main'
            
        except Exception as e:
            print(f"⚠️  Could not determine default branch for {repository_url}: {e}")
            return 'main'  # Fallback to 'main'
    
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
                    auth_headers = self._get_auth_headers('gitlab')
                    
                    if auth_headers:
                        print(f"🔐 Using GitLab authentication for project: {project_path}")
                    else:
                        print(f"⚠️  No GitLab authentication - private projects may fail: {project_path}")
                    
                    response = self._make_request_with_retry(api_url, headers=auth_headers)
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
        Filters repositories based on Asset Source matching the specified source type.
        """
        targets = []
        
        for app in applications:
            app_name = app['application_name']
            org_id = org_mapping.get(app_name)
            
            if not org_id:
                print(f"⚠️  No organization found for application: {app_name}")
                continue
            
            # Check Asset Source to filter repositories
            if not self.should_include_application(app, source_type):
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
    
    def create_general_targets(self, applications: List[Dict], org_mapping: Dict[str, str], source_type: str, branch_override: Optional[str] = None, files_override: Optional[str] = None, exclusion_globs_override: Optional[str] = None) -> List[Dict]:
        """
        Create general targets structure for GitHub, Azure DevOps, etc.
        Filters repositories based on Asset Source matching the specified source type.
        Uses concurrent processing for better performance with large repository lists.
        """
        # Filter applications based on Asset Source and other criteria
        filtered_apps = []
        
        for app in applications:
            app_name = app['application_name']
            org_id = org_mapping.get(app_name)
            
            if not org_id:
                print(f"⚠️  No organization found for application: {app_name}")
                continue
            
            # Check Asset Source to filter repositories
            if not self.should_include_application(app, source_type):
                continue
            
            repository_url = app.get('repository_url', '').strip()
            if not repository_url:
                print(f"⚠️  No repository URL for {app_name}")
                continue
            
            filtered_apps.append(app)
        
        if not filtered_apps:
            print("❌ No applications match the source type filter")
            return []
        
        print(f"🔍 Filtered to {len(filtered_apps)} applications matching {source_type}")
        
        # Use concurrent processing for repository batch
        targets = self._process_repository_batch(
            filtered_apps, 
            org_mapping, 
            source_type, 
            branch_override, 
            files_override, 
            exclusion_globs_override,
            self.max_workers
        )
        
        return targets
    
    def create_targets_json(self, csv_file_path: str, output_json_path: str, source_type: str, empty_org_only: bool = False, branch_override: Optional[str] = None, files_override: Optional[str] = None, exclusion_globs_override: Optional[str] = None, max_workers: Optional[int] = None, rate_limit: Optional[int] = None):
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
        
        # Auto-tune performance settings based on repository count
        self._auto_tune_performance(len(applications), source_type, max_workers, rate_limit)
        
        # Filter applications if empty_org_only flag is set
        if empty_org_only:
            original_count = len(applications)
            # Only include repositories where Organizations column is "N/A" (not imported yet)
            applications = [app for app in applications 
                          if app.get('organizations', '').strip().upper() == 'N/A']
            filtered_count = len(applications)
            print(f"🔍 Filtering for repositories not yet imported (Organizations = 'N/A'): {filtered_count}/{original_count} applications remaining")
            
            if not applications:
                print("✅ All repositories have already been imported to Snyk organizations!")
                return
        
        # Detect workflow type
        workflow_type = self.detect_workflow_type(applications)
        print(f"Detected workflow type: {workflow_type}")
        
        # Create targets based on workflow type
        if workflow_type == 'gitlab':
            targets = self.create_gitlab_targets(applications, org_mapping, source_type, branch_override, files_override, exclusion_globs_override)
        else:
            targets = self.create_general_targets(applications, org_mapping, source_type, branch_override, files_override, exclusion_globs_override)
        
        if not targets:
            print("❌ No targets created")
            return
        
        # Create final JSON structure
        targets_json = {"targets": targets}
        
        # Write to file
        with open(output_json_path, 'w') as f:
            json.dump(targets_json, f, indent=2)
        
        print(f"📄 Created targets file: {output_json_path}")
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
  - Safe API rate limits (based on GitHub/GitLab/Bitbucket limits)
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
  - bitbucket-cloud: For Bitbucket Cloud repositories (auto-tuned: 12 req/min)
  - bitbucket-server: For Bitbucket Server repositories

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
    parser.add_argument('--source', required=True, help='Integration type to use from organizations JSON (github, github-cloud-app, github-enterprise, gitlab, azure-repos, bitbucket-cloud, bitbucket-server)')
    parser.add_argument('--output', help='Output JSON file path (default: import-targets.json)')
    parser.add_argument('--empty-org-only', action='store_true', help='Only process repositories where Organizations column is "N/A" (repositories not yet imported to Snyk)')
    parser.add_argument('--branch', help='Override branch for all repositories (default: auto-detect from CSV or repository API)')
    parser.add_argument('--files', help='Override files for all repositories - comma-separated list of file paths to scan (if not specified, files field is omitted from import data)')
    parser.add_argument('--exclusion-globs', help='Override exclusionGlobs for all repositories (default: "fixtures, tests, __tests__, node_modules")')
    
    # Performance and scaling options (optional - auto-tuned by default)
    parser.add_argument('--max-workers', type=int, help='Maximum number of concurrent workers for API requests (default: auto-tuned based on repository count)')
    parser.add_argument('--rate-limit', type=int, help='Maximum requests per minute for API calls (default: auto-tuned based on source type and repository count)')
    
    args = parser.parse_args()
    
    # Snyk token is no longer required since we're reading from JSON file
    # Check if organizations JSON file exists
    if not os.path.exists(args.orgs_json):
        print(f"Error: {args.orgs_json} file not found")
        print(f"Make sure the organizations JSON file exists at {args.orgs_json}")
        sys.exit(1)
    
    # Use the specified source type
    source_type = args.source
    print(f"Using integration type: {source_type}")
    
    # Generate automatic filename if not provided
    if not args.output:
        output_path = "import-targets.json"
    else:
        output_path = args.output
    
    mapper = SnykTargetMapper(args.group_id, args.orgs_json)
    
    print(f"Creating targets file: {output_path}")
    if args.max_workers or args.rate_limit:
        print(f"⚙️  Using custom performance settings...")
    else:
        print(f"🎯 Using auto-tuned performance settings (optimal for your repository count)")
    
    mapper.create_targets_json(args.csv_file, output_path, source_type, args.empty_org_only, args.branch, args.files, args.exclusion_globs, args.max_workers, args.rate_limit)
    
    print(f"\n✅ Phase 2 complete! Use this file to import repositories:")
    print(f"   {output_path}")


if __name__ == '__main__':
    main()
