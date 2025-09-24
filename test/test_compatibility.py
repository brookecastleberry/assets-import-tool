#!/usr/bin/env python3
"""
Test the asset source compatibility logic
"""

from snyk_org_mapper import SnykOrgMapper

def test_compatibility():
    # Create a mock mapper
    mapper = SnykOrgMapper("fake-token", "fake-group")
    
    # Test cases
    test_cases = [
        # (asset_source, integration_type, expected_result)
        ("GitHub", "github", True),
        ("GitHub, Snyk", "github", True),
        ("BitBucket, Snyk", "github", False),
        ("GitLab", "gitlab", True),
        ("Bitbucket", "bitbucket-cloud", True),
        ("Azure DevOps", "azure-repos", True),
        ("GitHub", "github-enterprise", True),
        ("GitHub", "github-cloud-app", True),
        ("", "github", False),
        ("GitHub", "", False),
        ("unknown-source", "github", False),
    ]
    
    print("Testing Asset Source compatibility...")
    print("=" * 60)
    
    for asset_source, integration_type, expected in test_cases:
        result = mapper.is_asset_source_compatible(asset_source, integration_type)
        status = "✓" if result == expected else "✗"
        print(f"{status} Asset Source: '{asset_source}' | Integration: '{integration_type}' | Expected: {expected} | Got: {result}")
    
    print("\nDone!")

if __name__ == "__main__":
    test_compatibility()
