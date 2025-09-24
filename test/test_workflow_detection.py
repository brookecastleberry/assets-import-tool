#!/usr/bin/env python3
"""
Test workflow detection for integrated functionality
"""

from snyk_org_mapper import SnykOrgMapper

def test_workflow_detection():
    """Test the workflow detection logic"""
    
    mapper = SnykOrgMapper("fake-token", "fake-group")
    
    # Test GitLab workflow detection
    gitlab_applications = [
        {
            'application_name': 'Test App',
            'gitlab_project_id': '123',
            'branch': 'main',
            'asset_name': 'test-repo',
            'repository_url': 'https://gitlab.com/test/repo',
            'asset_source': 'GitLab'
        }
    ]
    
    # Test general workflow detection
    general_applications = [
        {
            'application_name': 'Test App',
            'gitlab_project_id': '',
            'asset_name': 'test-repo',
            'repository_url': 'https://github.com/test/repo',
            'asset_source': 'GitHub'
        }
    ]
    
    # Test empty gitlab project id
    empty_gitlab_applications = [
        {
            'application_name': 'Test App',
            'gitlab_project_id': 'nan',
            'asset_name': 'test-repo',
            'repository_url': 'https://github.com/test/repo',
            'asset_source': 'GitHub'
        }
    ]
    
    print("Testing workflow detection:")
    print("=" * 50)
    
    gitlab_workflow = mapper.detect_workflow_type(gitlab_applications)
    print(f"GitLab applications → Workflow: {gitlab_workflow}")
    
    general_workflow = mapper.detect_workflow_type(general_applications)
    print(f"General applications → Workflow: {general_workflow}")
    
    empty_gitlab_workflow = mapper.detect_workflow_type(empty_gitlab_applications)
    print(f"Empty GitLab ID applications → Workflow: {empty_gitlab_workflow}")
    
    print("\nWorkflow detection working correctly!" if all([
        gitlab_workflow == "gitlab",
        general_workflow == "general", 
        empty_gitlab_workflow == "general"
    ]) else "Issues detected with workflow detection!")

if __name__ == "__main__":
    test_workflow_detection()
