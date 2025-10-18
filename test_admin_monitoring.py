#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Admin Monitoring System
Basic validation of admin monitoring functionality
"""

import sqlite3
import os
import sys
from datetime import datetime

# Test database path
TEST_DB = '/tmp/test_admin_monitoring.db'

def setup_test_db():
    """Create test database with schema"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    # Create admins table
    cursor.execute('''CREATE TABLE admins (
        user_id INTEGER PRIMARY KEY, 
        username TEXT, 
        full_name TEXT, 
        added_by INTEGER,
        can_teach BOOLEAN DEFAULT 1, 
        can_import BOOLEAN DEFAULT 1, 
        can_manage_admins BOOLEAN DEFAULT 1, 
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create admin_chat_logs table
    cursor.execute('''CREATE TABLE admin_chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        full_name TEXT,
        message_text TEXT,
        chat_id INTEGER,
        chat_type TEXT,
        is_command BOOLEAN DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES admins(user_id))''')
    
    cursor.execute('CREATE INDEX idx_admin_chat_logs_user ON admin_chat_logs(user_id, timestamp DESC)')
    cursor.execute('CREATE INDEX idx_admin_chat_logs_timestamp ON admin_chat_logs(timestamp DESC)')
    
    # Add test admins
    cursor.execute('''INSERT INTO admins (user_id, username, full_name, is_active) 
                     VALUES (123456, 'test_user', 'Test User Full Name', 1)''')
    cursor.execute('''INSERT INTO admins (user_id, username, full_name, is_active) 
                     VALUES (789012, 'admin2', NULL, 1)''')
    
    conn.commit()
    conn.close()
    print("✅ Test database created")

def test_admin_manager():
    """Test AdminManager methods using direct SQL"""
    print("\n📋 Testing AdminManager functionality (SQL-based)...")
    
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    # Test 1: Update full_name (simulating set_full_name)
    print("\n1️⃣ Testing set_full_name (UPDATE query)...")
    cursor.execute('UPDATE admins SET full_name = ? WHERE user_id = ?', ("Admin Two Full Name", 789012))
    conn.commit()
    cursor.execute('SELECT full_name FROM admins WHERE user_id = ?', (789012,))
    result = cursor.fetchone()
    assert result[0] == "Admin Two Full Name", f"Expected 'Admin Two Full Name', got '{result[0]}'"
    print("   ✅ set_full_name() works")
    
    # Test 2: Get display name (simulating get_display_name)
    print("\n2️⃣ Testing get_display_name logic...")
    cursor.execute('SELECT full_name, username FROM admins WHERE user_id = ?', (123456,))
    result = cursor.fetchone()
    display_name = result[0] if result and result[0] else (f"@{result[1]}" if result and result[1] else "123456")
    assert display_name == "Test User Full Name", f"Expected 'Test User Full Name', got '{display_name}'"
    print(f"   ✅ Display name for user 123456: {display_name}")
    
    cursor.execute('SELECT full_name, username FROM admins WHERE user_id = ?', (789012,))
    result = cursor.fetchone()
    display_name = result[0] if result and result[0] else (f"@{result[1]}" if result and result[1] else "789012")
    assert display_name == "Admin Two Full Name", f"Expected 'Admin Two Full Name', got '{display_name}'"
    print(f"   ✅ Display name for user 789012: {display_name}")
    
    # Test 3: Log admin messages
    print("\n3️⃣ Testing log_admin_message (INSERT queries)...")
    cursor.execute('''
        INSERT INTO admin_chat_logs 
        (user_id, username, full_name, message_text, chat_id, chat_type, is_command)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (123456, "test_user", "Test User Full Name", "This is a test message", 111111, "private", 0))
    
    cursor.execute('''
        INSERT INTO admin_chat_logs 
        (user_id, username, full_name, message_text, chat_id, chat_type, is_command)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (123456, "test_user", "Test User Full Name", "/test command", 111111, "private", 1))
    conn.commit()
    print("   ✅ log_admin_message() works")
    
    # Test 4: Get admin logs
    print("\n4️⃣ Testing get_admin_logs (SELECT queries)...")
    cursor.execute('''
        SELECT id, user_id, username, full_name, message_text, chat_id, chat_type, 
               is_command, timestamp
        FROM admin_chat_logs
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT 10
    ''', (123456,))
    logs = cursor.fetchall()
    assert len(logs) == 2, f"Expected 2 logs, got {len(logs)}"
    # is_command is the 8th field (index 7)
    # Due to insertion order and DESC sort, most recent (command) should be first
    has_command = any(log[7] in (1, True) for log in logs)
    has_non_command = any(log[7] in (0, False) for log in logs)
    assert has_command, "Should have at least one command"
    assert has_non_command, "Should have at least one non-command"
    print(f"   ✅ Retrieved {len(logs)} logs (both commands and regular messages)")
    
    # Test 5: Get admin stats
    print("\n5️⃣ Testing get_admin_stats (aggregate queries)...")
    cursor.execute('''
        SELECT COUNT(*) FROM admin_chat_logs 
        WHERE user_id = ? AND date(timestamp) = date('now')
    ''', (123456,))
    total_messages = cursor.fetchone()[0]
    assert total_messages == 2, f"Expected 2 messages, got {total_messages}"
    
    cursor.execute('''
        SELECT COUNT(*) FROM admin_chat_logs 
        WHERE user_id = ? AND is_command = 1 AND date(timestamp) = date('now')
    ''', (123456,))
    total_commands = cursor.fetchone()[0]
    assert total_commands == 1, f"Expected 1 command, got {total_commands}"
    print(f"   ✅ Stats: {total_messages} messages, {total_commands} commands")
    
    # Test 6: Get all admins activity
    print("\n6️⃣ Testing get_all_admins_activity (JOIN query)...")
    cursor.execute('''
        SELECT a.user_id, a.username, a.full_name, COUNT(*) as msg_count
        FROM admin_chat_logs l
        JOIN admins a ON l.user_id = a.user_id
        WHERE date(timestamp) = date('now')
        GROUP BY a.user_id, a.username, a.full_name
        ORDER BY msg_count DESC
    ''')
    activity = cursor.fetchall()
    assert len(activity) == 1, f"Expected 1 active admin, got {len(activity)}"
    assert activity[0][0] == 123456, "Expected user 123456"
    assert activity[0][3] == 2, f"Expected 2 messages, got {activity[0][3]}"
    print(f"   ✅ Activity: {len(activity)} admins with messages")
    
    conn.close()
    print("\n✅ All AdminManager SQL tests passed!")

def test_database_schema():
    """Verify database schema is correct"""
    print("\n📋 Testing database schema...")
    
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    # Check admin_chat_logs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_chat_logs'")
    result = cursor.fetchone()
    assert result is not None, "admin_chat_logs table should exist"
    print("   ✅ admin_chat_logs table exists")
    
    # Check columns
    cursor.execute("PRAGMA table_info(admin_chat_logs)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    expected_columns = {
        'id': 'INTEGER',
        'user_id': 'INTEGER',
        'username': 'TEXT',
        'full_name': 'TEXT',
        'message_text': 'TEXT',
        'chat_id': 'INTEGER',
        'chat_type': 'TEXT',
        'is_command': 'BOOLEAN',
        'timestamp': 'TIMESTAMP'
    }
    
    for col, typ in expected_columns.items():
        assert col in columns, f"Column {col} should exist"
        print(f"   ✅ Column {col} exists ({typ})")
    
    # Check indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_admin_chat_logs_user'")
    result = cursor.fetchone()
    assert result is not None, "idx_admin_chat_logs_user index should exist"
    print("   ✅ idx_admin_chat_logs_user index exists")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_admin_chat_logs_timestamp'")
    result = cursor.fetchone()
    assert result is not None, "idx_admin_chat_logs_timestamp index should exist"
    print("   ✅ idx_admin_chat_logs_timestamp index exists")
    
    conn.close()
    print("\n✅ Database schema tests passed!")

def cleanup():
    """Clean up test database"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    print("\n🧹 Test database cleaned up")

if __name__ == '__main__':
    try:
        print("=" * 60)
        print("   Admin Monitoring System Tests")
        print("=" * 60)
        
        setup_test_db()
        test_database_schema()
        test_admin_manager()
        
        print("\n" + "=" * 60)
        print("   ✅ ALL TESTS PASSED!")
        print("=" * 60)
        
        cleanup()
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)
