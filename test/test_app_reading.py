#!/usr/bin/env python3
"""
Test the updated CSV parsing with pandas approach
"""

from snyk_org_mapper import SnykOrgMapper

def test_csv_reading():
    # Create a mock mapper (we don't need real API credentials for this test)
    mapper = SnykOrgMapper("fake-token", "fake-group")
    
    csv_file = "/Users/brookecastleberry/Desktop/all_assets_2025_09_24_154651.csv"
    
    print("Testing CSV reading...")
    applications = mapper.read_csv_applications(csv_file)
    
    if applications:
        print(f"Successfully found {len(applications)} applications!")
        print("\nFirst 5 applications:")
        for i, app in enumerate(applications[:5]):
            print(f"{i+1}. Application: '{app['application_name']}'")
            print(f"   Asset: '{app['asset_name']}'")
            print(f"   Repository: '{app['repository_url']}'")
            print(f"   Asset Source: '{app['asset_source']}'")
            print()
    else:
        print("No applications found - Application column might be empty")

if __name__ == "__main__":
    test_csv_reading()
