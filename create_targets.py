#!/usr/bin/env python3
"""
Snyk Targets Creator - Phase 2

This script creates import targets JSON from CSV file, mapping to existing Snyk organizations
and automatically detecting the appropriate integration types.
"""

import json
import csv
import io
import requests
from typing import Dict, List, Optional
import argparse
import sys
import os

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not available, using basic CSV parsing")


class SnykTargetMapper:
    def __init__(self, snyk_token: str, group_id: str):
        self.snyk_token = snyk_token
        self.group_id = group_id
        self.base_url = "https://api.snyk.io"
        self.headers = {
            "Authorization": snyk_token,
            "Accept": "*/*"
        }
    
    def get_organizations_from_group(self) -> List[Dict]:
        """
        Fetch all organizations from a Snyk group using the API
        GET /rest/groups/{group_id}/orgs
        """
        url = f"{self.base_url}/rest/groups/{self.group_id}/orgs?version=2024-06-21"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            # REST API returns data in 'data' field
            orgs = data.get('data', [])
            
            print(f"Found {len(orgs)} organizations in group {self.group_id}")
            
            # Extract relevant information
            org_info = []
            for org in orgs:
                # REST API response structure
                attributes = org.get('attributes', {})
                org_info.append({
                    'id': org.get('id'),
                    'name': attributes.get('name'),
                    'display_name': attributes.get('display_name', attributes.get('name')),
                    'slug': attributes.get('slug')
                })
            
            return org_info
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching organizations: {e}")
            return []
    
    def get_integrations_for_org(self, org_id: str) -> List[Dict]:
        """
        Fetch integrations for a specific organization
        GET /v1/org/{orgId}/integrations
        """
        url = f"{self.base_url}/v1/org/{org_id}/integrations"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            integrations = data.get('integrations', [])
            
            print(f"Found {len(integrations)} integrations for org {org_id}")
            return integrations
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching integrations for org {org_id}: {e}")
            return []
    
    def find_integration_id(self, org_id: str, integration_type: str) -> Optional[str]:
        """
        Find the integration ID for a specific integration type in an organization
        """
        integrations = self.get_integrations_for_org(org_id)
        
        # Map common integration type names to what Snyk API returns
        integration_mapping = {
            'github': 'github',
            'gitlab': 'gitlab',
            'bitbucket-cloud': 'bitbucket-cloud',
            'bitbucket-server': 'bitbucket-server',
            'azure-repos': 'azure-repos',
            'github-enterprise': 'github-enterprise'
        }
        
        target_type = integration_mapping.get(integration_type.lower(), integration_type.lower())
        
        for integration in integrations:
            if integration.get('type', '').lower() == target_type:
                return integration.get('id')
        
        return None
    
    def read_applications_from_csv(self, csv_file_path: str) -> List[Dict]:
        """
        Read applications from CSV file with enhanced parsing
        """
        applications = []
        
        try:
            if PANDAS_AVAILABLE:
                try:
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
                    
                    # Process each row
                    for index, row in df.iterrows():
                        app_name = str(row.get("Application", "")).strip()
                        if app_name and app_name.lower() not in ['nan', 'n/a', '']:
                            # Handle multiple applications separated by commas
                            app_names = [name.strip() for name in app_name.split(',') 
                                        if name.strip() and name.strip().lower() not in ['n/a', 'nan']]
                            
                            for single_app in app_names:
                                applications.append({
                                    'application_name': single_app,
                                    'asset_type': str(row.get("Type", "")),
                                    'asset_name': str(row.get("Asset", "")),
                                    'repository_url': str(row.get("Repository URL", "")),
                                    'asset_source': str(row.get("Asset Source", "")),
                                    'gitlab_project_id': str(row.get("Gitlab Project ID", "")),
                                    'branch': str(row.get("Branch", "")),
                                    'exclusion_globs': str(row.get("exclusionGlobs", "")),
                                    'files': str(row.get("Files", "")),
                                    'row_index': index
                                })
                
                except ImportError:
                    # Fallback to basic CSV parsing
                    PANDAS_AVAILABLE = False
            
            if not PANDAS_AVAILABLE:
                # Fallback to basic CSV parsing
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
                    
                    for index, row in enumerate(reader, start=start_row):
                        app_name = row.get("Application", "").strip()
                        if app_name and app_name.lower() not in ['nan', 'n/a', '']:
                            # Handle multiple applications separated by commas
                            app_names = [name.strip() for name in app_name.split(',') 
                                        if name.strip() and name.strip().lower() not in ['n/a', 'nan']]
                            
                            for single_app in app_names:
                                applications.append({
                                    'application_name': single_app,
                                    'asset_type': row.get("Type", ""),
                                    'asset_name': row.get("Asset", ""),
                                    'repository_url': row.get("Repository URL", ""),
                                    'asset_source': row.get("Asset Source", ""),
                                    'gitlab_project_id': row.get("Gitlab Project ID", ""),
                                    'branch': row.get("Branch", ""),
                                    'exclusion_globs': row.get("exclusionGlobs", ""),
                                    'files': row.get("Files", ""),
                                    'row_index': index
                                })
        
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return []
        
        print(f"Found {len(applications)} application entries from CSV")
        return applications
    
    def detect_workflow_type(self, applications: List[Dict]) -> str:
        """
        Detect which workflow to use based on CSV content
        """
        # Check for GitLab specific fields
        has_gitlab_fields = any(
            app.get('gitlab_project_id') and 
            str(app.get('gitlab_project_id')).strip() not in ['', 'nan', 'n/a'] 
            for app in applications
        )
        
        if has_gitlab_fields:
            return 'gitlab'
        else:
            return 'general'
    
    def create_gitlab_targets(self, applications: List[Dict], org_mapping: Dict[str, str]) -> List[Dict]:
        """
        Create GitLab targets structure
        """
        targets = []
        
        for app in applications:
            app_name = app['application_name']
            org_id = org_mapping.get(app_name)
            
            if not org_id:
                print(f"⚠️  No organization found for application: {app_name}")
                continue
            
            # Find GitLab integration
            integration_id = self.find_integration_id(org_id, 'gitlab')
            if not integration_id:
                print(f"⚠️  No GitLab integration found for org {org_id} (app: {app_name})")
                continue
            
            # Extract project info from repository URL or use Gitlab Project ID
            gitlab_project_id = app.get('gitlab_project_id', '').strip()
            repository_url = app.get('repository_url', '').strip()
            
            # Create target object
            target = {
                "orgId": org_id,
                "integrationId": integration_id,
                "target": {
                    "id": int(gitlab_project_id) if gitlab_project_id and gitlab_project_id.isdigit() else None
                }
            }
            
            # Add branch if specified
            branch = app.get('branch', '').strip()
            if branch and branch.lower() not in ['', 'nan', 'n/a']:
                target["target"]["branch"] = branch
            
            # Add exclusionGlobs if specified
            exclusion_globs = app.get('exclusion_globs', '').strip()
            if exclusion_globs and exclusion_globs.lower() not in ['nan', 'n/a']:
                target["exclusionGlobs"] = exclusion_globs
            else:
                target["exclusionGlobs"] = ""
            
            # Add files if specified
            files = app.get('files', '').strip()
            if files and files.lower() not in ['', 'nan', 'n/a']:
                target["files"] = files
            
            # Remove target.id if it's None (couldn't parse GitLab project ID)
            if target["target"]["id"] is None:
                print(f"⚠️  Invalid GitLab Project ID for {app_name}: {gitlab_project_id}")
                continue
            
            targets.append(target)
        
        return targets
    
    def create_general_targets(self, applications: List[Dict], org_mapping: Dict[str, str], integration_types: List[str] = None) -> List[Dict]:
        """
        Create general targets structure for GitHub, Azure DevOps, etc.
        """
        targets = []
        
        for app in applications:
            app_name = app['application_name']
            org_id = org_mapping.get(app_name)
            
            if not org_id:
                print(f"⚠️  No organization found for application: {app_name}")
                continue
            
            repository_url = app.get('repository_url', '').strip()
            if not repository_url:
                print(f"⚠️  No repository URL for {app_name}")
                continue
            
            # Determine integration type from repository URL if not specified
            determined_integration_types = integration_types or []
            if not determined_integration_types:
                if 'github.com' in repository_url.lower():
                    determined_integration_types = ['github']
                elif 'dev.azure.com' in repository_url.lower() or 'visualstudio.com' in repository_url.lower():
                    determined_integration_types = ['azure-repos']
                elif 'bitbucket.org' in repository_url.lower():
                    determined_integration_types = ['bitbucket-cloud']
                else:
                    print(f"⚠️  Cannot determine integration type for {repository_url}")
                    continue
            
            # Try each integration type until we find one
            integration_id = None
            for int_type in determined_integration_types:
                integration_id = self.find_integration_id(org_id, int_type)
                if integration_id:
                    break
            
            if not integration_id:
                print(f"⚠️  No matching integration found for org {org_id} (app: {app_name})")
                continue
            
            # Parse repository URL to extract owner and name
            try:
                if repository_url.endswith('.git'):
                    repository_url = repository_url[:-4]
                
                # Handle different URL formats
                if 'github.com' in repository_url:
                    # GitHub: https://github.com/owner/repo
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
                        continue
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
                        continue
                        
            except Exception as e:
                print(f"⚠️  Error parsing repository URL {repository_url}: {e}")
                continue
            
            # Create target object
            target = {
                "orgId": org_id,
                "integrationId": integration_id,
                "target": {
                    "name": repo_name,
                    "owner": owner,
                    "remoteUrl": repository_url
                }
            }
            
            # Add branch if specified
            branch = app.get('branch', '').strip()
            if branch and branch.lower() not in ['', 'nan', 'n/a']:
                target["target"]["branch"] = branch
            
            # Add exclusionGlobs if specified
            exclusion_globs = app.get('exclusion_globs', '').strip()
            if exclusion_globs and exclusion_globs.lower() not in ['nan', 'n/a']:
                target["exclusionGlobs"] = exclusion_globs
            else:
                target["exclusionGlobs"] = ""
            
            # Add files if specified
            files = app.get('files', '').strip()
            if files and files.lower() not in ['', 'nan', 'n/a']:
                target["files"] = files
            
            targets.append(target)
        
        return targets
    
    def create_targets_json(self, csv_file_path: str, output_json_path: str, integration_types: List[str] = None):
        """
        Create import-targets.json file with proper org mapping
        """
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
        
        # Detect workflow type
        workflow_type = self.detect_workflow_type(applications)
        print(f"Detected workflow type: {workflow_type}")
        
        # Create targets based on workflow type
        if workflow_type == 'gitlab':
            targets = self.create_gitlab_targets(applications, org_mapping)
        else:
            targets = self.create_general_targets(applications, org_mapping, integration_types)
        
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
        description="Create Snyk import targets from CSV file (Phase 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create targets file with GitHub integration
  python create_targets.py --group-id abc123 --csv-file mydata.csv --integration-type github
  
  # Create targets file with multiple integration types
  python create_targets.py --group-id abc123 --csv-file mydata.csv --integration-type github,azure-repos
        """
    )
    
    parser.add_argument('--group-id', required=True, help='Snyk Group ID')
    parser.add_argument('--csv-file', required=True, help='CSV file path')
    parser.add_argument('--integration-type', required=True, help='Integration types (comma-separated, e.g., github,azure-repos)')
    parser.add_argument('--output', help='Output JSON file path (default: import-targets.json)')
    
    args = parser.parse_args()
    
    # Check for Snyk token
    snyk_token = os.environ.get('SNYK_TOKEN')
    if not snyk_token:
        print("Error: SNYK_TOKEN environment variable is required")
        print("Set it with: export SNYK_TOKEN='your-token-here'")
        sys.exit(1)
    
    # Parse integration types from comma-separated string (now required)
    integration_types = [t.strip() for t in args.integration_type.split(',') if t.strip()]
    print(f"Using integration types: {', '.join(integration_types)}")
    
    # Generate automatic filename if not provided
    if not args.output:
        output_path = "import-targets.json"
    else:
        output_path = args.output
    
    mapper = SnykTargetMapper(snyk_token, args.group_id)
    
    print(f"Creating targets file: {output_path}")
    mapper.create_targets_json(args.csv_file, output_path, integration_types)
    
    print(f"\n✅ Phase 2 complete! Use this file to import repositories:")
    print(f"   {output_path}")


if __name__ == '__main__':
    main()
