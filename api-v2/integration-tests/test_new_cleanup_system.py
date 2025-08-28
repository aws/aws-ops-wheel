#!/usr/bin/env python3
"""
Test script to validate the new AWS SDK cleanup system

This script tests the new CleanupManager implementation to ensure it works
correctly with AWS SDK operations before deploying to full integration tests.
"""
import sys
import os
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.cleanup import CleanupManager


def test_cleanup_manager_initialization():
    """Test that CleanupManager initializes correctly with AWS SDK backend"""
    print("=== Testing CleanupManager Initialization ===")
    
    try:
        # Test basic initialization
        manager = CleanupManager(cleanup_enabled=True, debug=True, dry_run=True)
        print("✅ CleanupManager initialized successfully")
        
        # Test configuration
        assert hasattr(manager, 'aws_orchestrator'), "AWS orchestrator not found"
        assert hasattr(manager, '_created_wheel_groups'), "Resource tracking not found"
        assert hasattr(manager, '_created_cognito_users'), "Cognito user tracking not found"
        print("✅ All required attributes present")
        
        return True
        
    except Exception as e:
        print(f"❌ CleanupManager initialization failed: {e}")
        return False


def test_resource_registration():
    """Test resource registration methods"""
    print("\n=== Testing Resource Registration ===")
    
    try:
        manager = CleanupManager(cleanup_enabled=True, debug=True, dry_run=True)
        
        # Test all registration methods
        manager.register_wheel_group("test-wg-123")
        manager.register_wheel("test-wheel-456", "test-wg-123")
        manager.register_participant("test-participant-789", "test-wheel-456", "test-wg-123")
        manager.register_user("test-user-abc")
        manager.register_cognito_user("testuser@integrationtest.example.com", "testuser@integrationtest.example.com")
        
        print("✅ All resource registration methods work")
        
        # Test resource tracking
        remaining = manager.get_remaining_resources()
        assert len(remaining['wheel_groups']) == 1, f"Expected 1 wheel group, got {len(remaining['wheel_groups'])}"
        assert len(remaining['wheels']) == 1, f"Expected 1 wheel, got {len(remaining['wheels'])}"
        assert len(remaining['participants']) == 1, f"Expected 1 participant, got {len(remaining['participants'])}"
        assert len(remaining['users']) == 1, f"Expected 1 user, got {len(remaining['users'])}"
        assert len(remaining['cognito_users']) == 1, f"Expected 1 Cognito user, got {len(remaining['cognito_users'])}"
        
        print("✅ Resource tracking working correctly")
        print(f"   Tracked resources: {remaining}")
        
        return True
        
    except Exception as e:
        print(f"❌ Resource registration failed: {e}")
        return False


def test_legacy_compatibility():
    """Test legacy method compatibility"""
    print("\n=== Testing Legacy Method Compatibility ===")
    
    try:
        manager = CleanupManager(cleanup_enabled=True, debug=True, dry_run=True)
        
        # Test legacy methods exist and work
        result = manager.delete_participant("legacy-test-participant")
        print(f"✅ delete_participant works (dry run): {result}")
        
        result = manager.delete_wheel("legacy-test-wheel")
        print(f"✅ delete_wheel works (dry run): {result}")
        
        result = manager.delete_wheel_group("legacy-test-wheel-group")
        print(f"✅ delete_wheel_group works (dry run): {result}")
        
        result = manager.delete_user("legacy-test-user")
        print(f"✅ delete_user works (dry run): {result}")
        
        # Test cleanup metrics
        metrics = manager.get_cleanup_metrics()
        assert isinstance(metrics, dict), "Cleanup metrics should be a dictionary"
        print(f"✅ get_cleanup_metrics works: {metrics}")
        
        return True
        
    except Exception as e:
        print(f"❌ Legacy compatibility test failed: {e}")
        return False


def test_dry_run_cleanup():
    """Test dry run cleanup with registered resources"""
    print("\n=== Testing Dry Run Cleanup ===")
    
    try:
        manager = CleanupManager(cleanup_enabled=True, debug=True, dry_run=True)
        
        # Register some test resources
        manager.register_wheel_group("dry-run-wg-123")
        manager.register_wheel("dry-run-wheel-456", "dry-run-wg-123")
        manager.register_participant("dry-run-participant-789")
        manager.register_cognito_user("dryrunuser@integrationtest.example.com")
        
        print(f"Registered {len(manager.get_remaining_resources())} resource types")
        
        # Test dry run cleanup
        successful, failed = manager.cleanup_all_registered_resources()
        print(f"✅ Dry run cleanup completed: {successful} successful, {failed} failed")
        
        # In dry run, resources should still be tracked since nothing was actually deleted
        remaining = manager.get_remaining_resources()
        total_remaining = sum(len(resources) for resources in remaining.values())
        print(f"✅ Remaining resources after dry run: {total_remaining} (expected in dry run)")
        
        return True
        
    except Exception as e:
        print(f"❌ Dry run cleanup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_aws_sdk_integration():
    """Test AWS SDK integration without making actual calls"""
    print("\n=== Testing AWS SDK Integration ===")
    
    try:
        manager = CleanupManager(cleanup_enabled=True, debug=True, dry_run=True)
        
        # Test AWS SDK orchestrator is initialized
        orchestrator = manager.aws_orchestrator
        assert orchestrator is not None, "AWS orchestrator not initialized"
        
        # Test configuration
        config = orchestrator.config
        assert config.table_names['users'] == 'OpsWheelV2-Users-test', "Table names not configured correctly"
        assert config.table_names['wheel_groups'] == 'OpsWheelV2-WheelGroups-test', "Wheel groups table not configured"
        
        # Test cleaners are initialized
        assert hasattr(orchestrator, 'dynamodb_cleaner'), "DynamoDB cleaner not found"
        assert hasattr(orchestrator, 'cognito_cleaner'), "Cognito cleaner not found"
        
        print("✅ AWS SDK integration properly configured")
        print(f"   DynamoDB tables: {config.table_names}")
        print(f"   Batch size: {config.batch_size}")
        print(f"   Retry attempts: {config.retry_attempts}")
        
        return True
        
    except Exception as e:
        print(f"❌ AWS SDK integration test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Testing New AWS SDK Cleanup System\n")
    
    tests = [
        ("Cleanup Manager Initialization", test_cleanup_manager_initialization),
        ("Resource Registration", test_resource_registration),
        ("Legacy Compatibility", test_legacy_compatibility),
        ("Dry Run Cleanup", test_dry_run_cleanup),
        ("AWS SDK Integration", test_aws_sdk_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("🎯 TEST SUMMARY")
    print("="*60)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:8} {test_name}")
        if success:
            passed += 1
    
    total = len(results)
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! New cleanup system is ready for deployment.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please fix issues before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
