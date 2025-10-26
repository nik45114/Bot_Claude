#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Admin Management Module
Basic functionality tests
"""

import sys
import os
import tempfile
import sqlite3

# Add parent directory to path (get project root dynamically)
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing imports...")
    
    try:
        from modules.admins.db import AdminDB, ROLE_PERMISSIONS, PERMISSIONS
        print("  ✅ db module imported")
    except Exception as e:
        print(f"  ❌ db module failed: {e}")
        return False
    
    try:
        from modules.admins.formatters import (
            format_admin_card, format_admin_list, format_admin_display_name
        )
        print("  ✅ formatters module imported")
    except Exception as e:
        print(f"  ❌ formatters module failed: {e}")
        return False
    
    try:
        from modules.admins.wizard import AdminWizard
        print("  ✅ wizard module imported")
    except Exception as e:
        print(f"  ❌ wizard module failed: {e}")
        return False
    
    try:
        from modules.admins import register_admins
        print("  ✅ __init__ module imported")
    except Exception as e:
        print(f"  ❌ __init__ module failed: {e}")
        return False
    
    return True


def test_database_operations():
    """Test database operations"""
    print("\n🧪 Testing database operations...")
    
    from modules.admins.db import AdminDB
    
    # Create temporary database
    test_db = os.path.join(tempfile.gettempdir(), 'test_admins.db')
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Initialize database with schema
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    # Create minimal admins table
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        role TEXT DEFAULT 'staff',
        permissions TEXT NULL,
        active INTEGER DEFAULT 1,
        notes TEXT NULL,
        added_by INTEGER DEFAULT 0,
        can_teach BOOLEAN DEFAULT 1,
        can_import BOOLEAN DEFAULT 1,
        can_manage_admins BOOLEAN DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create other tables
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        created_by INTEGER NOT NULL,
        target_username TEXT NULL,
        role_default TEXT DEFAULT 'staff',
        expires_at TIMESTAMP NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NULL,
        full_name TEXT NULL,
        message TEXT NULL,
        status TEXT DEFAULT 'pending',
        reviewed_by INTEGER NULL,
        reviewed_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target_user_id INTEGER NULL,
        details TEXT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    
    # Test AdminDB
    db = AdminDB(test_db)
    
    # Test add admin
    success = db.add_admin(123456, username='testuser', full_name='Test User', role='staff', added_by=1)
    if success:
        print("  ✅ Add admin")
    else:
        print("  ❌ Add admin failed")
        return False
    
    # Test get admin
    admin = db.get_admin(123456)
    if admin and admin['username'] == 'testuser':
        print("  ✅ Get admin")
    else:
        print("  ❌ Get admin failed")
        return False
    
    # Test list admins
    admins, total = db.list_admins(page=1, per_page=10)
    if len(admins) == 1 and total == 1:
        print("  ✅ List admins")
    else:
        print("  ❌ List admins failed")
        return False
    
    # Test set role
    success = db.set_role(123456, 'manager')
    admin = db.get_admin(123456)
    if success and admin['role'] == 'manager':
        print("  ✅ Set role")
    else:
        print("  ❌ Set role failed")
        return False
    
    # Test permissions
    permissions = db.get_permissions(123456)
    if permissions:
        print("  ✅ Get permissions")
    else:
        print("  ❌ Get permissions failed")
        return False
    
    # Test create invite
    token = db.create_invite(123456, target_username='newuser', role_default='staff')
    if token:
        print("  ✅ Create invite")
    else:
        print("  ❌ Create invite failed")
        return False
    
    # Test get invite
    invite = db.get_invite(token)
    if invite and invite['target_username'] == 'newuser':
        print("  ✅ Get invite")
    else:
        print("  ❌ Get invite failed")
        return False
    
    # Test create request
    success = db.create_request(789012, username='requester', full_name='Requester User', message='Please add me')
    if success:
        print("  ✅ Create request")
    else:
        print("  ❌ Create request failed")
        return False
    
    # Test list requests
    requests, total = db.list_requests(status='pending', page=1, per_page=10)
    if len(requests) == 1 and total == 1:
        print("  ✅ List requests")
    else:
        print("  ❌ List requests failed")
        return False
    
    # Test audit log
    success = db.log_action(123456, 'add', 789012, {'test': 'data'})
    if success:
        print("  ✅ Log action")
    else:
        print("  ❌ Log action failed")
        return False
    
    # Clean up
    os.remove(test_db)
    
    return True


def test_formatters():
    """Test formatter functions"""
    print("\n🧪 Testing formatters...")
    
    from modules.admins.formatters import (
        format_admin_display_name, format_role_emoji, format_role_name,
        format_admin_card, format_admin_list_item
    )
    
    # Test display name
    admin = {'user_id': 123, 'username': 'testuser', 'full_name': 'Test User', 'role': 'staff'}
    name = format_admin_display_name(admin)
    if name == 'Test User':
        print("  ✅ Display name (full_name)")
    else:
        print(f"  ❌ Display name failed: {name}")
        return False
    
    # Test role emoji
    emoji = format_role_emoji('owner')
    if emoji == '👑':
        print("  ✅ Role emoji")
    else:
        print(f"  ❌ Role emoji failed: {emoji}")
        return False
    
    # Test role name
    name = format_role_name('manager')
    if name == 'Менеджер':
        print("  ✅ Role name")
    else:
        print(f"  ❌ Role name failed: {name}")
        return False
    
    # Test admin card
    card = format_admin_card(admin, {'cash_view': True, 'cash_edit': False})
    if 'Test User' in card and 'Сотрудник' in card:
        print("  ✅ Admin card")
    else:
        print("  ❌ Admin card failed")
        return False
    
    # Test list item
    item = format_admin_list_item(admin, 1)
    if 'Test User' in item:
        print("  ✅ List item")
    else:
        print("  ❌ List item failed")
        return False
    
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("  Admin Management Module Tests")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Database Operations", test_database_operations),
        ("Formatters", test_formatters),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {name} passed")
            else:
                failed += 1
                print(f"\n❌ {name} failed")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
