import os
import time
import requests
import base64
from typing import Dict, Optional

def rate_limit(request_lock, last_request_time, request_interval):
	"""Apply rate limiting to API requests."""
	with request_lock:
		current_time = time.time()
		time_since_last_request = current_time - last_request_time[0]
		if time_since_last_request < request_interval:
			sleep_time = request_interval - time_since_last_request
			time.sleep(sleep_time)
		last_request_time[0] = time.time()

def get_auth_headers(scm_type: str, source_type: str = None, logger=None) -> Optional[Dict[str, str]]:
	"""Get authentication headers for SCM APIs based on environment variables."""
	if scm_type == 'github':
		token = os.getenv('GITHUB_TOKEN')
		if token:
			return {'Authorization': f'token {token}'}
	elif scm_type == 'gitlab':
		token = os.getenv('GITLAB_TOKEN')
		if token:
			return {'PRIVATE-TOKEN': token}
	elif scm_type == 'azure':
		token = os.getenv('AZURE_DEVOPS_TOKEN')
		if token:
			auth_string = f":{token}"
			encoded_auth = base64.b64encode(auth_string.encode()).decode()
			return {'Authorization': f'Basic {encoded_auth}'}
	return None

def display_auth_status(source_type: str):
	"""Display authentication status for SCM APIs."""
	print("🔐 SCM Authentication Status:")
	github_token = os.getenv('GITHUB_TOKEN')
	if github_token:
		print("  ✅ GitHub: Authenticated (GITHUB_TOKEN found)")
	else:
		print("  ⚠️  GitHub: Unauthenticated (60 req/hour limit)")
	gitlab_token = os.getenv('GITLAB_TOKEN')
	if gitlab_token:
		print("  ✅ GitLab: Authenticated (GITLAB_TOKEN found)")
	else:
		print("  ⚠️  GitLab: Unauthenticated (10 req/min limit)")
	azure_token = os.getenv('AZURE_DEVOPS_TOKEN')
	if azure_token:
		print("  ✅ Azure DevOps: Authenticated (AZURE_DEVOPS_TOKEN found)")
	else:
		print("  ⚠️  Azure DevOps: No authentication (API calls disabled)")
	print()

def make_request_with_retry(url: str, max_retries: int, retry_delay: int, retry_backoff: int, rate_limit_fn, headers: Optional[Dict[str, str]] = None, logger=None, timeout: int = 10) -> Optional[requests.Response]:
	"""Make HTTP request with exponential backoff retry logic."""
	for attempt in range(max_retries):
		try:
			rate_limit_fn()
			response = requests.get(url, timeout=timeout, headers=headers, verify=False)
			if response.status_code == 200:
				return response
			elif response.status_code == 429:
				wait_time = retry_delay * (retry_backoff ** attempt) * 2
				warning_msg = f"⚠️  Rate limit hit for {url}, waiting {wait_time}s before retry {attempt + 1}/{max_retries}"
				print(warning_msg)
				if logger:
					logger.warning(warning_msg)
				time.sleep(wait_time)
				continue
			elif 400 <= response.status_code < 500:
				error_msg = f"⚠️  Client error {response.status_code} for {url}, not retrying"
				print(error_msg)
				if logger:
					logger.error(error_msg)
				return None
			elif response.status_code >= 500:
				wait_time = retry_delay * (retry_backoff ** attempt)
				warning_msg = f"⚠️  Server error {response.status_code} for {url}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
				print(warning_msg)
				if logger:
					logger.warning(warning_msg)
				if attempt < max_retries - 1:
					time.sleep(wait_time)
				continue
		except requests.exceptions.RequestException as e:
			wait_time = retry_delay * (retry_backoff ** attempt)
			error_msg = f"⚠️  Request exception for {url}: {e}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
			print(error_msg)
			if logger:
				logger.error(error_msg)
			if attempt < max_retries - 1:
				time.sleep(wait_time)
			continue
	print(f"❌ Failed to fetch {url} after {max_retries} attempts")
	return None
