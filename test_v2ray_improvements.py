#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for V2Ray user management improvements
"""

import sys
import os
import tempfile
import sqlite3
from datetime import datetime, timedelta

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from v2ray_manager import V2RayManager


def test_database_init():
    """Test database initialization with new temp_access table"""
    print("🧪 Testing database initialization...")
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        manager = V2RayManager(db_path)
        
        # Check if v2ray_temp_access table exists
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='v2ray_temp_access'")
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None, "v2ray_temp_access table not created"
        print("✅ Database initialized successfully with temp_access table")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_temp_access_methods():
    """Test temporary access methods"""
    print("\n🧪 Testing temporary access methods...")
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        manager = V2RayManager(db_path)
        
        # Test data
        server_name = "test_server"
        uuid = "12345678-1234-1234-1234-123456789abc"
        expires_at = datetime.now() + timedelta(days=7)
        
        # Test set_temp_access
        print("  Testing set_temp_access...")
        result = manager.set_temp_access(server_name, uuid, expires_at)
        assert result, "set_temp_access failed"
        print("  ✅ set_temp_access works")
        
        # Test get_temp_access
        print("  Testing get_temp_access...")
        access = manager.get_temp_access(server_name, uuid)
        assert access is not None, "get_temp_access returned None"
        assert access['server_name'] == server_name, "server_name mismatch"
        assert access['uuid'] == uuid, "uuid mismatch"
        print("  ✅ get_temp_access works")
        
        # Test remove_temp_access
        print("  Testing remove_temp_access...")
        result = manager.remove_temp_access(server_name, uuid)
        assert result, "remove_temp_access failed"
        
        # Verify removal
        access = manager.get_temp_access(server_name, uuid)
        assert access is None, "temp_access not removed"
        print("  ✅ remove_temp_access works")
        
        # Test get_expired_users
        print("  Testing get_expired_users...")
        expired_date = datetime.now() - timedelta(days=1)
        manager.set_temp_access(server_name, uuid, expired_date)
        
        expired_users = manager.get_expired_users()
        assert len(expired_users) > 0, "get_expired_users didn't find expired users"
        assert expired_users[0]['uuid'] == uuid, "wrong expired user returned"
        print("  ✅ get_expired_users works")
        
        print("✅ All temporary access methods work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Temporary access methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_manager_methods():
    """Test that manager has all required methods"""
    print("\n🧪 Testing V2RayManager methods...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        manager = V2RayManager(db_path)
        
        # Check for required methods
        required_methods = [
            'get_users',
            'delete_user',
            'set_temp_access',
            'get_temp_access',
            'remove_temp_access',
            'get_expired_users',
            'cleanup_expired_users'
        ]
        
        for method in required_methods:
            assert hasattr(manager, method), f"Method {method} not found"
            print(f"  ✅ {method} exists")
        
        print("✅ All required methods exist")
        return True
        
    except Exception as e:
        print(f"❌ Manager methods test failed: {e}")
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 V2Ray User Management Improvements Test Suite")
    print("=" * 60)
    
    tests = [
        test_database_init,
        test_temp_access_methods,
        test_manager_methods
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test {test.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
