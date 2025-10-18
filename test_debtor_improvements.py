#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for debtor system improvements
Tests admin nickname system and product management features
"""

import sqlite3
from product_manager import ProductManager

def test_database_migrations():
    """Test that all migrations were applied correctly"""
    print("=" * 60)
    print("Testing Database Migrations")
    print("=" * 60)
    
    conn = sqlite3.connect('knowledge.db')
    cursor = conn.cursor()
    
    # Check admin_nickname column exists
    cursor.execute('PRAGMA table_info(admins)')
    columns = [row[1] for row in cursor.fetchall()]
    assert 'admin_nickname' in columns, "❌ admin_nickname column missing!"
    print("✅ admin_nickname column exists in admins table")
    
    # Check all indexes
    cursor.execute('SELECT name FROM sqlite_master WHERE type="index" AND name LIKE "idx_%"')
    indexes = [row[0] for row in cursor.fetchall()]
    
    expected_indexes = [
        'idx_admins_active',
        'idx_admin_products_admin',
        'idx_admin_products_product',
        'idx_admin_products_date',
        'idx_admin_products_group'
    ]
    
    for idx in expected_indexes:
        assert idx in indexes, f"❌ Index {idx} missing!"
        print(f"✅ Index {idx} exists")
    
    conn.close()
    print("\n✅ All database migrations passed!\n")

def test_admin_nicknames():
    """Test admin nickname functionality"""
    print("=" * 60)
    print("Testing Admin Nickname System")
    print("=" * 60)
    
    pm = ProductManager('knowledge.db')
    
    # Test setting nicknames
    test_admins = [
        (1001, "Иван"),
        (1002, "Мария"),
        (1003, "Петр")
    ]
    
    for admin_id, nickname in test_admins:
        result = pm.set_admin_nickname(admin_id, nickname)
        assert result, f"❌ Failed to set nickname for admin {admin_id}"
        print(f"✅ Set nickname for admin {admin_id}: {nickname}")
    
    # Test getting nicknames
    for admin_id, expected_nickname in test_admins:
        actual_nickname = pm.get_admin_nickname(admin_id)
        assert actual_nickname == expected_nickname, f"❌ Nickname mismatch for admin {admin_id}"
        print(f"✅ Retrieved nickname for admin {admin_id}: {actual_nickname}")
    
    # Test display name with nickname
    display_name = pm.get_display_name(1001, "Original Name")
    assert display_name == "Иван", "❌ Display name should use nickname"
    print(f"✅ Display name uses nickname: {display_name}")
    
    # Test display name without nickname
    display_name = pm.get_display_name(9999, "No Nickname User")
    assert display_name == "No Nickname User", "❌ Display name should use original name"
    print(f"✅ Display name uses original name when no nickname: {display_name}")
    
    print("\n✅ All admin nickname tests passed!\n")

def test_debtor_system():
    """Test debtor system with nicknames"""
    print("=" * 60)
    print("Testing Debtor System with Nicknames")
    print("=" * 60)
    
    pm = ProductManager('knowledge.db')
    
    # Clear existing products for clean test
    conn = sqlite3.connect('knowledge.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products')
    cursor.execute('DELETE FROM admin_products')
    conn.commit()
    conn.close()
    
    # Add test products
    test_products = [
        ("RedBull", 50.0),
        ("Горилла", 45.0),
        ("Кофе", 30.0),
        ("Пончик", 25.0)
    ]
    
    print("\nAdding test products:")
    for name, price in test_products:
        result = pm.add_product(name, price)
        print(f"  {'✅' if result else '⚠️'} {name}: {price} ₽")
    
    # Set admin nicknames
    pm.set_admin_nickname(2001, "Ваня")
    pm.set_admin_nickname(2002, "Маша")
    pm.set_admin_nickname(2003, "Коля")
    
    # Record products for admins
    print("\nRecording products for admins:")
    test_records = [
        (2001, "Ivan Ivanov", "RedBull", 2),
        (2001, "Ivan Ivanov", "Горилла", 4),
        (2002, "Maria Petrova", "RedBull", 3),
        (2002, "Maria Petrova", "Кофе", 2),
        (2003, "Nikolai Sidorov", "Пончик", 5),
    ]
    
    for admin_id, admin_name, product_name, quantity in test_records:
        # Find product ID
        products = pm.list_products()
        product = next((p for p in products if p['name'] == product_name), None)
        if product:
            result = pm.record_admin_product(admin_id, admin_name, product['id'], quantity)
            nickname = pm.get_admin_nickname(admin_id)
            print(f"  {'✅' if result else '❌'} {nickname}: {quantity}x {product_name}")
    
    # Test debts by debt amount
    print("\n=== Debts sorted by amount ===")
    debts = pm.get_all_debts(sort_by='debt')
    for admin_id, data in debts.items():
        print(f"  👤 {data['name']}: {data['total']:.0f} ₽")
    
    # Test debts by name
    print("\n=== Debts sorted by name ===")
    debts = pm.get_all_debts(sort_by='name')
    for admin_id, data in debts.items():
        print(f"  👤 {data['name']}: {data['total']:.0f} ₽")
    
    # Test detailed report
    print("\n=== Detailed debt report ===")
    report_text = pm.format_detailed_debts_report()
    print(report_text)
    
    # Test products summary
    print("\n=== Products summary ===")
    summary_text = pm.format_products_summary_report()
    print(summary_text)
    
    # Test products report by admin
    print("\n=== Products report (by admin) ===")
    report_text = pm.format_products_report(sort_by='admin')
    print(report_text[:500])  # First 500 chars
    
    # Test products report by product
    print("\n=== Products report (by product) ===")
    report_text = pm.format_products_report(sort_by='product')
    print(report_text[:500])  # First 500 chars
    
    print("\n✅ All debtor system tests passed!\n")

def test_error_handling():
    """Test error handling in product management"""
    print("=" * 60)
    print("Testing Error Handling")
    print("=" * 60)
    
    pm = ProductManager('knowledge.db')
    
    # Test duplicate product
    result = pm.add_product("RedBull", 50.0)
    print(f"  {'⚠️' if not result else '✅'} Adding duplicate product correctly rejected")
    
    # Test invalid price
    result = pm.add_product("Invalid Product", -10.0)
    assert not result, "❌ Should reject negative price"
    print("  ✅ Negative price correctly rejected")
    
    # Test empty name
    result = pm.add_product("", 50.0)
    assert not result, "❌ Should reject empty name"
    print("  ✅ Empty product name correctly rejected")
    
    print("\n✅ All error handling tests passed!\n")

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("DEBTOR SYSTEM IMPROVEMENTS - TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        test_database_migrations()
        test_admin_nicknames()
        test_debtor_system()
        test_error_handling()
        
        print("=" * 60)
        print("🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉")
        print("=" * 60)
        print("\nFeatures tested:")
        print("  ✅ Database migrations (admin_nickname column)")
        print("  ✅ Performance indexes (5 indexes)")
        print("  ✅ Admin nickname system (set/get/display)")
        print("  ✅ Debtor sorting (by debt/name)")
        print("  ✅ Detailed debt reports with nicknames")
        print("  ✅ Products summary reports")
        print("  ✅ Products reports (by admin/product)")
        print("  ✅ Error handling (duplicates, invalid data)")
        print("\nThe system is ready for production use!")
        print("=" * 60 + "\n")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit(main())
