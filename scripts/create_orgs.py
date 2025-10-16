"""
Snyk Organization Creator - Phase 1

This script reads Application names from a CSV file and creates a JSON file 
with organizations that need to be created in Snyk.
"""

import json
import csv
from typing import Dict, List
import argparse
import sys
import os

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not available, using basic CSV parsing")


class SnykOrgCreator:
    def __init__(self, group_id: str):
        self.group_id = group_id
    
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
                    
                    for index, row in enumerate(reader, start=start_row):
                        app_name = row.get("Application", "").strip()
                        if app_name and app_name.lower() not in ['nan', 'n/a', '']:
                            # Handle multiple applications separated by commas
                            app_names = [name.strip() for name in app_name.split(',') 
                                        if name.strip() and name.strip().lower() not in ['n/a', 'nan']]
                            
                            for single_app in app_names:
                                applications.append({
                                    'application_name': single_app,
                                    'row_index': index
                                })
        
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return []
        
        print(f"Found {len(applications)} application entries from CSV")
        return applications

    def create_orgs_json(self, csv_file_path: str, output_json_path: str, source_org_id: str = None):
        """
        Create orgs.json file with all unique Application names from CSV
        """
        # Read applications from CSV
        applications = self.read_applications_from_csv(csv_file_path)
        
        if not applications:
            print("❌ No applications found in CSV")
            return
        
        # Find unique application names
        unique_app_names = set()
        for app in applications:
            unique_app_names.add(app['application_name'])
        
        # Validate application names don't exceed 60 characters
        invalid_names = []
        for app_name in unique_app_names:
            if len(app_name) > 60:
                invalid_names.append(app_name)
        
        if invalid_names:
            print("❌ Error: The following application names exceed 60 characters:")
            for invalid_name in sorted(invalid_names):
                print(f"   - '{invalid_name}' ({len(invalid_name)} characters)")
            print(f"\nSnyk organization names must be 60 characters or less.")
            print(f"Please shorten these application names in your CSV and try again.")
            sys.exit(1)
        
        print(f"📋 Found {len(unique_app_names)} unique applications to create as organizations:")
        for org_name in sorted(unique_app_names):
            print(f"   - {org_name}")
        
        # Create orgs structure
        orgs_to_create = []
        for org_name in sorted(unique_app_names):
            org_data = {
                "name": org_name,
                "groupId": self.group_id
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
    
    # Generate automatic filename if not provided
    if not args.output:
        output_path = f"group-{args.group_id}-orgs.json"
    else:
        output_path = args.output
    
    creator = SnykOrgCreator(args.group_id)
    
    print(f"Creating organizations file: {output_path}")
    creator.create_orgs_json(args.csv_file, output_path, args.source_org_id)
    
    print(f"\n✅ Phase 1 complete! Use this file to create organizations in Snyk:")
    print(f"   {output_path}")
    print(f"\n📋 Next steps:")
    print(f"   1. Use Snyk API Import Tool to create organizations from {output_path}")
    print(f"   2. Then run: python create_targets.py --group-id {args.group_id} --csv-file {args.csv_file} --integration-type YOUR_INTEGRATION_TYPE")


if __name__ == '__main__':
    main()
