#!/usr/bin/env python3
"""
Test Runner for AWS Ops Wheel v2 Integration Tests

Simple script to run integration tests with common configurations.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, capture_output=False):
    """Run a command and return the result"""
    print(f"Running: {' '.join(cmd)}")
    try:
        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd)
            return result.returncode == 0, "", ""
    except FileNotFoundError:
        print(f"Error: Command not found: {cmd[0]}")
        return False, "", ""


def check_requirements():
    """Check if pytest is installed"""
    success, _, _ = run_command(['python', '-m', 'pytest', '--version'], capture_output=True)
    if not success:
        print("Error: pytest not found. Please install requirements:")
        print("  pip install -r requirements.txt")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='Run AWS Ops Wheel v2 Integration Tests')
    
    # Environment selection
    parser.add_argument('--environment', '-e', default='test', 
                       help='Test environment (test, dev)')
    
    # Test selection
    parser.add_argument('--critical', '-c', action='store_true',
                       help='Run only critical tests')
    parser.add_argument('--smoke', '-s', action='store_true',
                       help='Run only smoke tests')
    parser.add_argument('--auth', '-a', action='store_true',
                       help='Run only authentication tests')
    parser.add_argument('--crud', action='store_true',
                       help='Run only CRUD operation tests')
    parser.add_argument('--admin', action='store_true',
                       help='Run only admin functionality tests')
    
    # Test configuration
    parser.add_argument('--integration-debug', '-d', action='store_true',
                       help='Enable integration test debug logging')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Disable test data cleanup')
    parser.add_argument('--admin-password', 
                       help='Override admin password')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose test output')
    
    # Test execution
    parser.add_argument('--parallel', '-p', type=int, metavar='N',
                       help='Run tests in parallel with N workers')
    parser.add_argument('--test-file', '-f',
                       help='Run specific test file')
    parser.add_argument('--test-pattern', '-k',
                       help='Run tests matching pattern')
    
    # Reporting
    parser.add_argument('--no-report', action='store_true',
                       help='Skip HTML report generation')
    parser.add_argument('--junit', action='store_true',
                       help='Generate JUnit XML report')
    
    args = parser.parse_args()
    
    # Check prerequisites
    if not check_requirements():
        return 1
    
    # Change to test directory
    test_dir = Path(__file__).parent
    os.chdir(test_dir)
    
    # Build pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Environment configuration
    cmd.extend(['--environment', args.environment])
    
    if args.integration_debug:
        cmd.append('--integration-debug')
    
    if args.no_cleanup:
        cmd.append('--no-cleanup')
    
    if args.admin_password:
        cmd.extend(['--admin-password', args.admin_password])
    
    if args.verbose:
        cmd.append('-v')
    
    # Test selection
    markers = []
    if args.critical:
        markers.append('critical')
    if args.smoke:
        markers.append('smoke')
    if args.auth:
        markers.append('auth')
    if args.crud:
        markers.append('crud')
    if args.admin:
        markers.append('admin')
    
    if markers:
        cmd.extend(['-m', ' or '.join(markers)])
    
    # Specific test selection
    if args.test_file:
        cmd.append(f'tests/{args.test_file}')
    
    if args.test_pattern:
        cmd.extend(['-k', args.test_pattern])
    
    # Parallel execution
    if args.parallel:
        cmd.extend(['-n', str(args.parallel)])
    
    # Reporting
    if not args.no_report:
        # Ensure reports directory exists
        os.makedirs('reports', exist_ok=True)
        cmd.extend(['--html=reports/integration_test_report.html', '--self-contained-html'])
    
    if args.junit:
        os.makedirs('reports', exist_ok=True)
        cmd.extend(['--junit-xml=reports/junit_report.xml'])
    
    # Add default test directory if no specific test file
    if not args.test_file:
        cmd.append('tests/')
    
    # Print configuration
    print("=" * 60)
    print("AWS Ops Wheel v2 Integration Test Runner")
    print("=" * 60)
    print(f"Environment: {args.environment}")
    print(f"Debug: {args.integration_debug}")
    print(f"Cleanup: {not args.no_cleanup}")
    if markers:
        print(f"Test markers: {', '.join(markers)}")
    if args.test_file:
        print(f"Test file: {args.test_file}")
    if args.test_pattern:
        print(f"Test pattern: {args.test_pattern}")
    print("-" * 60)
    
    # Run tests
    success, stdout, stderr = run_command(cmd)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ INTEGRATION TESTS PASSED")
        print("=" * 60)
        if not args.no_report:
            print(f"📊 HTML Report: {test_dir}/reports/integration_test_report.html")
        if args.junit:
            print(f"📄 JUnit Report: {test_dir}/reports/junit_report.xml")
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ INTEGRATION TESTS FAILED")
        print("=" * 60)
        if not args.no_report:
            print(f"📊 Check HTML Report: {test_dir}/reports/integration_test_report.html")
        print("\nTroubleshooting tips:")
        print("- Run with --integration-debug for detailed logging")
        print("- Check environment configuration in config/environments.json")
        print("- Verify admin credentials and API connectivity")
        print("- Check for test data conflicts or cleanup issues")
        return 1


if __name__ == '__main__':
    sys.exit(main())
