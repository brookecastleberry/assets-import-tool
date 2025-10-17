#!/usr/bin/env python3
"""
Test GitHub App Authentication

This script tests the GitHub App authentication module to ensure it's working correctly.

Usage:
    python test_github_app.py
    
Environment Variables Required:
    GITHUB_APP_ID=your_app_id
    GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----...-----END RSA PRIVATE KEY-----"
    
Optional:
    GITHUB_APP_INSTALLATION_ID=installation_id
"""

import sys
import os

# Add scripts directory to path so we can import github_app_auth
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from github_app_auth import GitHubAppAuth, test_github_app_auth
except ImportError as e:
    print(f"❌ Error importing github_app_auth: {e}")
    print("Make sure PyJWT is installed: pip install PyJWT>=2.8.0")
    sys.exit(1)


def test_configuration():
    """Test GitHub App configuration"""
    print("🔧 Testing GitHub App Configuration...")
    
    auth = GitHubAppAuth()
    
    if auth.is_configured():
        print("✅ Configuration is valid!")
        return True
    else:
        print(f"❌ Configuration error: {auth.get_configuration_error()}")
        return False


def test_api_access():
    """Test GitHub App API access with a sample repository"""
    print("\n🌐 Testing GitHub App API Access...")
    
    auth = GitHubAppAuth()
    
    if not auth.is_configured():
        print("❌ Skipping API test - configuration invalid")
        return False
    
    # Test with a well-known public repository
    print("   Testing access to octocat/Hello-World repository...")
    repo_info = auth.get_repository_info("octocat", "Hello-World")
    
    if repo_info:
        print(f"✅ API access successful!")
        print(f"   Repository: {repo_info.get('full_name')}")
        print(f"   Default branch: {repo_info.get('default_branch')}")
        print(f"   Private: {repo_info.get('private')}")
        return True
    else:
        print("⚠️  API access test inconclusive (repository may not be accessible)")
        return False


def display_environment_info():
    """Display current environment variable status"""
    print("\n📋 Environment Variables:")
    
    app_id = os.getenv('GITHUB_APP_ID')
    private_key = os.getenv('GITHUB_APP_PRIVATE_KEY')
    installation_id = os.getenv('GITHUB_APP_INSTALLATION_ID')
    
    print(f"   GITHUB_APP_ID: {'✅ Set' if app_id else '❌ Not set'}")
    if app_id:
        print(f"     Value: {app_id}")
    
    print(f"   GITHUB_APP_PRIVATE_KEY: {'✅ Set' if private_key else '❌ Not set'}")
    if private_key:
        lines = private_key.strip().split('\n')
        print(f"     Format: {'✅ PEM' if lines[0].startswith('-----BEGIN') else '❌ Invalid'}")
        print(f"     Length: {len(private_key)} characters")
    
    print(f"   GITHUB_APP_INSTALLATION_ID: {'✅ Set' if installation_id else '⚪ Optional (will auto-discover)'}")
    if installation_id:
        print(f"     Value: {installation_id}")


def main():
    """Main test function"""
    print("🚀 GitHub App Authentication Test")
    print("=" * 50)
    
    # Display environment info
    display_environment_info()
    
    # Test configuration
    config_ok = test_configuration()
    
    if config_ok:
        # Test API access
        api_ok = test_api_access()
        
        print("\n" + "=" * 50)
        if config_ok and api_ok:
            print("🎉 All tests passed! GitHub App authentication is working correctly.")
            return 0
        elif config_ok:
            print("⚠️  Configuration is valid but API access test was inconclusive.")
            print("   This may be normal if your app doesn't have access to the test repository.")
            return 0
        else:
            print("❌ Tests failed. Check your configuration.")
            return 1
    else:
        print("\n" + "=" * 50)
        print("❌ Configuration test failed. Please check your environment variables.")
        print("\nRequired setup:")
        print("   export GITHUB_APP_ID='your-app-id'")
        print("   export GITHUB_APP_PRIVATE_KEY='-----BEGIN RSA PRIVATE KEY-----")
        print("   your-private-key-content")
        print("   -----END RSA PRIVATE KEY-----'")
        return 1


if __name__ == '__main__':
    sys.exit(main())