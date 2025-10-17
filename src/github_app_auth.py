"""
GitHub App Authentication Module

This module provides GitHub App authentication support for API calls,
compatible with the same authentication method used by snyk-api-import.

Required Environment Variables:
- GITHUB_APP_ID: Your GitHub App's numeric ID
- GITHUB_APP_PRIVATE_KEY: Your GitHub App's private key in PEM format
- GITHUB_APP_INSTALLATION_ID: (Optional) Specific installation ID

Usage:
    from github_app_auth import GitHubAppAuth
    
    auth = GitHubAppAuth()
    if auth.is_configured():
        headers = auth.get_auth_headers()
        # Use headers for API requests
"""

import os
import time
import jwt
import requests
from typing import Optional, Dict
import json
import logging


class GitHubAppAuth:
    """GitHub App authentication handler with token caching"""
    
    def __init__(self):
        self.logger = logging.getLogger('github_app_auth')
        self._cached_token: Optional[str] = None
        self._token_expiry: Optional[float] = None
        self._app_id: Optional[str] = None
        self._private_key: Optional[str] = None
        self._installation_id: Optional[str] = None
        
    def is_configured(self) -> bool:
        """
        Check if GitHub App is properly configured
        Returns True if all required environment variables are set and valid
        """
        try:
            self._load_config()
            return True
        except Exception as e:
            self.logger.debug(f"GitHub App not configured: {e}")
            return False
    
    def get_configuration_error(self) -> str:
        """
        Get a human-readable error message for configuration issues
        """
        app_id = os.getenv('GITHUB_APP_ID')
        private_key = os.getenv('GITHUB_APP_PRIVATE_KEY')
        
        if not app_id:
            return 'GITHUB_APP_ID environment variable is not set. Please set it to your GitHub App ID.'
        
        if not private_key:
            return 'GITHUB_APP_PRIVATE_KEY environment variable is not set. Please set it to your GitHub App private key (PEM format).'
        
        if not private_key.strip().startswith('-----BEGIN') or not private_key.strip().endswith('-----END RSA PRIVATE KEY-----'):
            return 'GITHUB_APP_PRIVATE_KEY must be in PEM format. Please ensure it starts with "-----BEGIN" and ends with "-----END".'
        
        if not app_id.isdigit():
            return 'GITHUB_APP_ID must be a numeric string. Please check your GitHub App ID.'
        
        return 'GitHub Cloud App configuration appears to be invalid.'
    
    def _load_config(self):
        """Load and validate configuration from environment variables"""
        self._app_id = os.getenv('GITHUB_APP_ID')
        self._private_key = os.getenv('GITHUB_APP_PRIVATE_KEY')
        self._installation_id = os.getenv('GITHUB_APP_INSTALLATION_ID')
        
        if not self._app_id:
            raise ValueError('GITHUB_APP_ID environment variable is required. Please set it to your GitHub App ID.')
        
        if not self._private_key:
            raise ValueError('GITHUB_APP_PRIVATE_KEY environment variable is required. Please set it to your GitHub App private key (PEM format).')
        
        # Validate that the private key looks like a PEM key
        if not self._private_key.strip().startswith('-----BEGIN') or not self._private_key.strip().endswith('-----END RSA PRIVATE KEY-----'):
            raise ValueError('GITHUB_APP_PRIVATE_KEY must be in PEM format. Please ensure it starts with "-----BEGIN" and ends with "-----END".')
        
        # Validate app ID is numeric
        if not self._app_id.isdigit():
            raise ValueError('GITHUB_APP_ID must be a numeric string. Please check your GitHub App ID.')
    
    def _generate_jwt_token(self) -> str:
        """
        Generate a JWT token for GitHub App authentication
        JWT tokens are valid for 10 minutes and used to get installation tokens
        """
        now = int(time.time())
        payload = {
            'iss': self._app_id,  # Issuer: GitHub App ID
            'iat': now - 60,      # Issued at: 60 seconds ago (to account for clock skew)
            'exp': now + 600,     # Expires: 10 minutes from now (GitHub's max)
        }
        
        # Generate JWT using the private key
        return jwt.encode(payload, self._private_key, algorithm='RS256')
    
    def _get_installation_id(self) -> str:
        """
        Get installation ID - either from environment variable or by discovering it
        """
        if self._installation_id:
            return self._installation_id
        
        # If no specific installation ID, we need to discover it
        # This requires calling the GitHub API to list installations
        jwt_token = self._generate_jwt_token()
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        
        response = requests.get('https://api.github.com/app/installations', headers=headers)
        if response.status_code == 200:
            installations = response.json()
            if installations and len(installations) > 0:
                # Use the first installation if multiple exist
                installation_id = str(installations[0]['id'])
                self.logger.info(f"Auto-discovered GitHub App installation ID: {installation_id}")
                return installation_id
            else:
                raise ValueError('No GitHub App installations found. Please install the app on at least one organization.')
        else:
            raise ValueError(f'Failed to list GitHub App installations: {response.status_code} {response.text}')
    
    def _get_installation_token(self) -> str:
        """
        Get an installation access token using the JWT token
        Installation tokens are valid for 1 hour and used for API calls
        """
        # Check if we have a valid cached token
        if self._cached_token and self._token_expiry and time.time() < self._token_expiry:
            return self._cached_token
        
        try:
            jwt_token = self._generate_jwt_token()
            installation_id = self._get_installation_id()
            
            headers = {
                'Authorization': f'Bearer {jwt_token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28'
            }
            
            response = requests.post(
                f'https://api.github.com/app/installations/{installation_id}/access_tokens',
                headers=headers
            )
            
            if response.status_code == 201:
                token_data = response.json()
                token = token_data['token']
                
                # Cache the token with 50-minute expiry (tokens are valid for 1 hour)
                self._cached_token = token
                self._token_expiry = time.time() + 50 * 60  # 50 minutes
                
                self.logger.debug(f"Successfully obtained GitHub App installation token")
                return token
            else:
                raise ValueError(f'Failed to get installation access token: {response.status_code} {response.text}')
                
        except Exception as e:
            # Clear cached token on error
            self._cached_token = None
            self._token_expiry = None
            raise ValueError(f'Failed to authenticate with GitHub App: {e}. Please check your GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, and ensure the app is installed.')
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for GitHub API requests
        Returns headers with Bearer token for installation access
        """
        if not self.is_configured():
            raise ValueError(f'GitHub App not configured: {self.get_configuration_error()}')
        
        token = self._get_installation_token()
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }
    
    def clear_token_cache(self):
        """Clear cached token (useful for testing or when switching configurations)"""
        self._cached_token = None
        self._token_expiry = None
    
    def get_repository_info(self, owner: str, repo: str) -> Optional[Dict]:
        """
        Get repository information including default branch
        This is a convenience method for testing the authentication
        """
        try:
            headers = self.get_auth_headers()
            response = requests.get(f'https://api.github.com/repos/{owner}/{repo}', headers=headers)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                self.logger.warning(f"Repository {owner}/{repo} not found or not accessible")
                return None
            elif response.status_code == 403:
                self.logger.warning(f"Access denied to repository {owner}/{repo}")
                return None
            else:
                self.logger.error(f"Failed to get repository info: {response.status_code} {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting repository info for {owner}/{repo}: {e}")
            return None


def test_github_app_auth():
    """
    Test function to verify GitHub App authentication is working
    """
    auth = GitHubAppAuth()
    
    if not auth.is_configured():
        print(f"❌ GitHub App not configured: {auth.get_configuration_error()}")
        return False
    
    try:
        # Try to get headers (this will test the full auth flow)
        headers = auth.get_auth_headers()
        print("✅ GitHub App authentication successful!")
        print(f"   Auth header present: {'Authorization' in headers}")
        return True
    except Exception as e:
        print(f"❌ GitHub App authentication failed: {e}")
        return False


if __name__ == '__main__':
    # Test the authentication if run directly
    print("🔍 Testing GitHub App Authentication...")
    test_github_app_auth()