#!/usr/bin/env python3
"""
Test script to verify CSV parsing works correctly
"""

import csv
import io
from typing import List, Dict

def read_csv_applications(csv_file_path: str) -> List[Dict]:
    """
    Read the CSV file and extract Application Names and other relevant data
    """
    applications = []
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            
            # Skip the first row if it starts with "Table"
            if lines and lines[0].strip().startswith("Table"):
                lines = lines[1:]
            
            csv_content = io.StringIO(''.join(lines))
            reader = csv.DictReader(csv_content)
            
            for row in reader:
                app_name = row.get("Application", "").strip()
                if app_name and app_name != "N/A":  # Skip empty and N/A values
                    # Handle multiple applications separated by commas
                    app_names = [name.strip() for name in app_name.split(',') if name.strip() and name.strip() != "N/A"]
                    
                    for single_app in app_names:
                        applications.append({
                            'application_name': single_app,
                            'asset_type': row.get("Type", ""),
                            'asset_name': row.get("Asset", ""),
                            'repository_url': row.get("Repository URL", ""),
                            'organizations': row.get("Organizations", ""),
                        })
    
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return []
    
    return applications

def main():
    csv_file = "/Users/brookecastleberry/Desktop/all_assets_2025_09_24_154651.csv"
    
    print("Testing CSV parsing...")
    applications = read_csv_applications(csv_file)
    
    print(f"Found {len(applications)} application entries")
    
    # Get unique application names
    unique_apps = set()
    for app in applications:
        unique_apps.add(app['application_name'])
    
    print(f"Unique application names ({len(unique_apps)}):")
    for app_name in sorted(unique_apps):
        print(f"  - '{app_name}'")
    
    print(f"\nFirst 5 entries:")
    for i, app in enumerate(applications[:5]):
        print(f"{i+1}. {app}")

if __name__ == "__main__":
    main()
