#!/usr/bin/env python3
"""
Test runner for the assets import tool

This script runs all unit tests and provides a summary of results.
"""

import os
import sys
import subprocess
from pathlib import Path


def install_pytest():
    """Install pytest if not available"""
    try:
        import pytest
        return True
    except ImportError:
        print("📦 pytest not found. Installing...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pytest'])
            print("✅ pytest installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install pytest")
            return False


def run_tests():
    """Run all tests in the tests directory"""
    
    if not install_pytest():
        return False
    
    # Import pytest after ensuring it's installed
    import pytest
    
    # Get the tests directory
    tests_dir = Path(__file__).parent
    
    print("🧪 Running comprehensive unit tests for Assets Import Tool...")
    print("📋 Test Coverage:")
    print("   • Core Modules: logging, CSV, API, file utils")
    print("   • CLI Flags: --branch, --files, --exclusion-globs, --empty-org-only, --source, --rows")
    print("   • Detection Logic: branch detection, GitLab project ID detection")
    print("   • Integration: complex flag combinations, error handling")
    print("=" * 60)
    
    # Run pytest with verbose output and coverage if available
    pytest_args = [
        str(tests_dir),
        '-v',  # Verbose output
        '--tb=short',  # Shorter traceback format
        '--color=yes',  # Colored output
    ]
    
    # Try to add coverage if available
    try:
        import coverage
        pytest_args.extend(['--cov=src', '--cov-report=term-missing'])
    except ImportError:
        print("ℹ️  Install 'coverage' for test coverage reports: pip install coverage pytest-cov")
    
    # Run the tests
    exit_code = pytest.main(pytest_args)
    
    print("=" * 60)
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    
    return exit_code == 0


def main():
    """Main test runner"""
    
    # Change to the project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print(f"🔍 Running tests from: {project_root}")
    
    # Add src to Python path
    src_path = project_root / 'src'
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    success = run_tests()
    
    if success:
        print("\n🎉 Test suite completed successfully!")
        return 0
    else:
        print("\n💥 Test suite failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
