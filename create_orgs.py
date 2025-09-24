#!/usr/bin/env python3
"""
Snyk Organization Creator - Phase 1

This script fetches Snyk organizations from a group and maps them to Application Names
from the CSV file, creating a JSON file with organizations that need to be created.
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


class SnykOrgMapper:
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
    
    def create_orgs_json(self, csv_file_path: str, output_json_path: str, group_id: str, source_org_id: str = None):
        """
        Create orgs.json file for organizations that don't exist yet
        """
        # Get existing organizations
        existing_orgs = self.get_organizations_from_group()
        existing_org_names = {org['display_name'].lower() for org in existing_orgs}
        
        # Read applications from CSV
        applications = self.read_applications_from_csv(csv_file_path)
        
        # Find unique application names that don't have corresponding orgs
        unique_app_names = set()
        for app in applications:
            unique_app_names.add(app['application_name'])
        
        # Find applications that need new orgs
        missing_orgs = []
        for app_name in unique_app_names:
            if app_name.lower() not in existing_org_names:
                missing_orgs.append(app_name)
        
        if not missing_orgs:
            print("✅ All applications already have corresponding organizations!")
            # Create empty file to indicate no orgs need to be created
            with open(output_json_path, 'w') as f:
                json.dump({"orgs": []}, f, indent=2)
            return
        
        print(f"📋 Found {len(missing_orgs)} organizations that need to be created:")
        for org_name in sorted(missing_orgs):
            print(f"   - {org_name}")
        
        # Create orgs structure
        orgs_to_create = []
        for org_name in sorted(missing_orgs):
            org_data = {
                "name": org_name,
                "groupId": group_id
            }
            
            # Add sourceOrgId if provided
            if source_org_id:
                org_data["sourceOrgId"] = source_org_id
            
            orgs_to_create.append(org_data)
        
        orgs_json = {"orgs": orgs_to_create}
        
        # Write to file
        with open(output_json_path, 'w') as f:
            json.dump(orgs_json, f, indent=2)
        
        print(f"📄 Created organizations file: {output_json_path}")
        print(f"   Organizations to create: {len(orgs_to_create)}")


def main():
    parser = argparse.ArgumentParser(
        description="Create Snyk organizations from CSV file (Phase 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create organizations file
  python create_orgs.py --group-id abc123 --csv-file mydata.csv
  
  # Create organizations with source org for copying settings
  python create_orgs.py --group-id abc123 --csv-file mydata.csv --source-org-id def456
        """
    )
    
    parser.add_argument('--group-id', required=True, help='Snyk Group ID')
    parser.add_argument('--csv-file', required=True, help='CSV file path')
    parser.add_argument('--source-org-id', help='Source organization ID to copy settings from')
    parser.add_argument('--output', help='Output JSON file path (default: group-{GROUP_ID}-orgs.json)')
    
    args = parser.parse_args()
    
    # Check for Snyk token
    snyk_token = os.environ.get('SNYK_TOKEN')
    if not snyk_token:
        print("Error: SNYK_TOKEN environment variable is required")
        print("Set it with: export SNYK_TOKEN='your-token-here'")
        sys.exit(1)
    
    # Generate automatic filename if not provided
    if not args.output:
        output_path = f"group-{args.group_id}-orgs.json"
    else:
        output_path = args.output
    
    mapper = SnykOrgMapper(snyk_token, args.group_id)
    
    print(f"Creating organizations file: {output_path}")
    mapper.create_orgs_json(args.csv_file, output_path, args.group_id, args.source_org_id)
    
    print(f"\n✅ Phase 1 complete! Use this file to create organizations in Snyk:")
    print(f"   {output_path}")
    print(f"\n📋 Next steps:")
    print(f"   1. Use Snyk API Import Tool to create organizations from {output_path}")
    print(f"   2. Then run: python create_targets.py --group-id {args.group_id} --csv-file {args.csv_file}")


if __name__ == '__main__':
    main()
