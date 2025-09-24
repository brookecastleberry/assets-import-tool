#!/usr/bin/env python3
"""
Test comma-separated integration types parsing
"""

def test_comma_separated_parsing():
    """Test parsing comma-separated integration types"""
    
    test_cases = [
        "github",
        "github,gitlab",
        "github,gitlab,bitbucket-cloud",
        "github, gitlab, bitbucket-cloud, azure-repos",
        " github , gitlab ",  # Test with spaces
        "",  # Test empty string
    ]
    
    print("Testing comma-separated integration type parsing:")
    print("=" * 60)
    
    for test_input in test_cases:
        # Simulate the parsing logic from the main script
        if test_input:
            integration_types = [t.strip() for t in test_input.split(',') if t.strip()]
        else:
            integration_types = None
            
        print(f"Input: '{test_input}'")
        print(f"Parsed: {integration_types}")
        print(f"Type: {type(integration_types)}")
        print()
    
    # Test with actual compatibility checking
    from snyk_org_mapper import SnykOrgMapper
    
    mapper = SnykOrgMapper("fake-token", "fake-group")
    
    # Test the most common use case
    integration_types = [t.strip() for t in "github,gitlab,bitbucket-cloud".split(',') if t.strip()]
    asset_sources = ["GitHub, Snyk", "GitLab", "Bitbucket"]
    
    print("Testing compatibility with parsed integration types:")
    print(f"Integration types: {integration_types}")
    
    for asset_source in asset_sources:
        print(f"\nAsset Source: '{asset_source}'")
        for integration_type in integration_types:
            compatible = mapper.is_asset_source_compatible(asset_source, integration_type)
            status = "✓" if compatible else "✗"
            print(f"  {status} {integration_type}")

if __name__ == "__main__":
    test_comma_separated_parsing()
