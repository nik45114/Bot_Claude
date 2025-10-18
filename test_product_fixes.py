#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for Product Manager bug fixes
Tests table initialization, detailed logging, and edge cases
"""

import os
import sys
import sqlite3
import tempfile
import logging

# Setup logging to see detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

TEST_DB = os.path.join(tempfile.gettempdir(), 'test_product_fixes.db')

def test_table_existence_check():
    """Test that tables are properly checked and created"""
    print("\n🧪 Testing table existence checks...")
    
    # Remove test DB if exists
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from product_manager import ProductManager
    
    # Initialize manager - should create tables
    pm = ProductManager(TEST_DB)
    
    # Verify tables exist
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    assert cursor.fetchone() is not None, "Products table should exist"
    print("  ✅ Products table exists")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_products'")
    assert cursor.fetchone() is not None, "Admin_products table should exist"
    print("  ✅ Admin_products table exists")
    
    conn.close()
    print("✅ Table existence checks passed")

def test_add_product_with_logging():
    """Test add_product with detailed logging"""
    print("\n🧪 Testing add_product with detailed logging...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from product_manager import ProductManager
    
    pm = ProductManager(TEST_DB)
    
    # Test 1: Add valid product
    print("\n  Test 1: Adding valid product...")
    result = pm.add_product('Test Product 1', 100.0)
    assert result is True, "Should successfully add product"
    print("  ✅ Valid product added")
    
    # Test 2: Try to add duplicate
    print("\n  Test 2: Adding duplicate product...")
    result = pm.add_product('Test Product 1', 150.0)
    assert result is False, "Should fail to add duplicate"
    print("  ✅ Duplicate rejected correctly")
    
    # Test 3: Add product with empty name
    print("\n  Test 3: Adding product with empty name...")
    result = pm.add_product('', 100.0)
    assert result is False, "Should fail with empty name"
    print("  ✅ Empty name rejected")
    
    # Test 4: Add product with invalid price
    print("\n  Test 4: Adding product with invalid price...")
    result = pm.add_product('Test Product 2', 0.0)
    assert result is False, "Should fail with zero price"
    print("  ✅ Zero price rejected")
    
    result = pm.add_product('Test Product 2', -10.0)
    assert result is False, "Should fail with negative price"
    print("  ✅ Negative price rejected")
    
    # Test 5: Add another valid product
    print("\n  Test 5: Adding second valid product...")
    result = pm.add_product('Test Product 2', 200.0)
    assert result is True, "Should successfully add second product"
    print("  ✅ Second product added")
    
    # Verify both products exist
    products = pm.list_products()
    assert len(products) == 2, f"Should have 2 products, got {len(products)}"
    print(f"  ✅ Both products in database: {[p['name'] for p in products]}")
    
    print("✅ Add product with logging tests passed")

def test_table_recovery():
    """Test that missing tables are recreated"""
    print("\n🧪 Testing table recovery...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from product_manager import ProductManager
    
    # Create database with tables
    pm = ProductManager(TEST_DB)
    
    # Manually drop the products table
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS products")
    conn.commit()
    conn.close()
    
    print("  Dropped products table")
    
    # Try to add product - should detect missing table and recreate
    print("  Attempting to add product to recreate table...")
    result = pm.add_product('Recovery Test', 50.0)
    assert result is True, "Should recreate table and add product"
    
    # Verify table was recreated
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    assert cursor.fetchone() is not None, "Products table should be recreated"
    conn.close()
    
    print("  ✅ Table recreated successfully")
    print("✅ Table recovery test passed")

def test_product_manager_initialization():
    """Test ProductManager initialization"""
    print("\n🧪 Testing ProductManager initialization...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from product_manager import ProductManager
    
    # Test initialization with new database
    pm1 = ProductManager(TEST_DB)
    assert pm1.db_path == TEST_DB, "Database path should be set correctly"
    print("  ✅ Initialization with new database")
    
    # Test initialization with existing database
    pm2 = ProductManager(TEST_DB)
    assert pm2.db_path == TEST_DB, "Database path should be set correctly"
    print("  ✅ Initialization with existing database")
    
    # Add product with first instance
    result = pm1.add_product('Init Test 1', 100.0)
    assert result is True, "Should add product with first instance"
    
    # Verify with second instance
    products = pm2.list_products()
    assert len(products) == 1, "Second instance should see the product"
    print("  ✅ Multiple instances work correctly")
    
    print("✅ ProductManager initialization tests passed")

def test_special_characters_in_name():
    """Test products with special characters in name"""
    print("\n🧪 Testing special characters in product names...")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    from product_manager import ProductManager
    
    pm = ProductManager(TEST_DB)
    
    # Test with various special characters
    test_names = [
        "Product (Special)",
        "Product & Co",
        "Product 'quoted'",
        'Product "double quoted"',
        "Product №1",
        "Product 50%"
    ]
    
    for name in test_names:
        result = pm.add_product(name, 100.0)
        assert result is True, f"Should add product with name: {name}"
        print(f"  ✅ Added: {name}")
    
    # Verify all products exist
    products = pm.list_products()
    assert len(products) == len(test_names), f"Should have {len(test_names)} products"
    print(f"  ✅ All {len(test_names)} products with special characters added")
    
    print("✅ Special characters test passed")

def main():
    print("=" * 60)
    print("   TESTING PRODUCT MANAGER BUG FIXES")
    print("=" * 60)
    
    try:
        test_table_existence_check()
        test_add_product_with_logging()
        test_table_recovery()
        test_product_manager_initialization()
        test_special_characters_in_name()
        
        print("\n" + "=" * 60)
        print("✅ ALL PRODUCT FIX TESTS PASSED!")
        print("=" * 60)
        
        # Cleanup
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
