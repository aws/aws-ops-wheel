#!/usr/bin/env python3
"""
Test script to verify comprehensive cleanup integration

This script tests that the integration between pytest and the comprehensive
cleanup script works properly.

Usage:
    python test_comprehensive_cleanup_integration.py
"""
import os
import sys
import subprocess
import tempfile
import shutil
from typing import Tuple

def test_comprehensive_cleanup_dry_run() -> Tuple[bool, str]:
    """Test that comprehensive cleanup runs in dry-run mode"""
    try:
        # Get the integration tests directory
        integration_tests_dir = os.path.dirname(__file__)
        clear_script_path = os.path.join(integration_tests_dir, "clear_test_data.py")
        
        # Test that the script exists and is executable
        if not os.path.exists(clear_script_path):
            return False, f"Cleanup script not found at: {clear_script_path}"
        
        # Run the cleanup script in dry-run mode
        cmd = [sys.executable, clear_script_path, "--dry-run"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 1 minute timeout for dry run
            cwd=integration_tests_dir
        )
        
        success = result.returncode == 0
        
        if success:
            return True, "Comprehensive cleanup dry-run completed successfully"
        else:
            error_msg = f"Dry-run failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f"\nSTDERR: {result.stderr[:500]}"
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        return False, "Comprehensive cleanup dry-run timed out"
    except Exception as e:
        return False, f"Comprehensive cleanup dry-run failed: {e}"


def test_pytest_integration() -> Tuple[bool, str]:
    """Test that pytest can import the comprehensive cleanup functions"""
    try:
        # Get the integration tests directory
        integration_tests_dir = os.path.dirname(__file__)
        conftest_path = os.path.join(integration_tests_dir, "conftest.py")
        
        if not os.path.exists(conftest_path):
            return False, f"conftest.py not found at: {conftest_path}"
        
        # Try to import the comprehensive cleanup function
        sys.path.insert(0, integration_tests_dir)
        from conftest import _run_comprehensive_cleanup
        
        # Test the function with dry-run mode
        success = _run_comprehensive_cleanup(debug_enabled=True, dry_run=True)
        
        if success:
            return True, "Pytest integration test completed successfully"
        else:
            return False, "Comprehensive cleanup function returned False"
            
    except ImportError as e:
        return False, f"Failed to import comprehensive cleanup function: {e}"
    except Exception as e:
        return False, f"Pytest integration test failed: {e}"


def test_pytest_command_line_options() -> Tuple[bool, str]:
    """Test that pytest recognizes the new command line options"""
    try:
        # Get the integration tests directory
        integration_tests_dir = os.path.dirname(__file__)
        
        # Test pytest help to see if our options are present
        cmd = [sys.executable, "-m", "pytest", "--help"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=integration_tests_dir
        )
        
        if result.returncode != 0:
            return False, f"pytest --help failed with exit code {result.returncode}"
        
        help_output = result.stdout
        
        # Check if our custom options are present
        expected_options = [
            "--comprehensive-cleanup",
            "--cleanup-dry-run"
        ]
        
        missing_options = []
        for option in expected_options:
            if option not in help_output:
                missing_options.append(option)
        
        if missing_options:
            return False, f"Missing pytest options: {', '.join(missing_options)}"
        
        return True, "All pytest command line options found"
        
    except subprocess.TimeoutExpired:
        return False, "pytest --help timed out"
    except Exception as e:
        return False, f"pytest options test failed: {e}"


def main():
    """Run all integration tests"""
    print("🧹 Testing Comprehensive Cleanup Integration")
    print("=" * 50)
    
    tests = [
        ("Comprehensive Cleanup Dry-Run", test_comprehensive_cleanup_dry_run),
        ("Pytest Integration", test_pytest_integration),
        ("Pytest Command Line Options", test_pytest_command_line_options),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        
        try:
            success, message = test_func()
            
            if success:
                print(f"✅ {test_name}: PASSED")
                print(f"   {message}")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
                print(f"   {message}")
                failed += 1
                
        except Exception as e:
            print(f"❌ {test_name}: ERROR")
            print(f"   Unexpected error: {e}")
            failed += 1
    
    print(f"\n📊 TEST SUMMARY")
    print("=" * 50)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📋 Total:  {len(tests)}")
    
    if failed == 0:
        print(f"\n🎉 All comprehensive cleanup integration tests PASSED!")
        print(f"✨ The integration tests are ready to use comprehensive cleanup.")
        print(f"")
        print(f"Usage examples:")
        print(f"  pytest --integration-debug                    # With comprehensive cleanup (default)")
        print(f"  pytest --no-cleanup                          # Disable all cleanup")
        print(f"  pytest --cleanup-dry-run                     # Dry-run mode")
        print(f"  pytest --comprehensive-cleanup               # Explicit enable (default)")
        print(f"  python clear_test_data.py --dry-run          # Manual dry-run")
        print(f"  python clear_test_data.py                    # Manual full cleanup")
        
        return 0
    else:
        print(f"\n⚠️  {failed} integration test(s) failed.")
        print(f"💡 Please check the error messages above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
