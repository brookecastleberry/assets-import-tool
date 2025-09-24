#!/usr/bin/env python3
"""
Test multiple integration types functionality
"""

import sys
import argparse

def test_multiple_integration_types():
    """Test that argparse correctly handles multiple --integration-type flags"""
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--integration-type', action='append', help='Integration types')
    
    # Simulate command line arguments
    test_args = ['--integration-type', 'github', '--integration-type', 'gitlab', '--integration-type', 'bitbucket-cloud', '--integration-type', 'azure-repos']
    args = parser.parse_args(test_args)
    
    print(f"Parsed integration types: {args.integration_type}")
    print(f"Type: {type(args.integration_type)}")
    
    # Test compatibility logic with multiple types
    from snyk_org_mapper import SnykOrgMapper
    
    mapper = SnykOrgMapper("fake-token", "fake-group")
    
    integration_types = args.integration_type
    asset_sources = ["GitHub, Snyk", "GitLab", "Bitbucket", "Azure DevOps"]
    
    print("\nTesting compatibility with multiple integration types:")
    for asset_source in asset_sources:
        print(f"\nAsset Source: '{asset_source}'")
        for integration_type in integration_types:
            compatible = mapper.is_asset_source_compatible(asset_source, integration_type)
            status = "✓" if compatible else "✗"
            print(f"  {status} {integration_type}: {compatible}")

if __name__ == "__main__":
    test_multiple_integration_types()
