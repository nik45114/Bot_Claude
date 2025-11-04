#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for Product Database Migration, Reset, and Diagnostics scripts
"""

import os
import sys
import tempfile
import sqlite3
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TEST_DB = os.path.join(tempfile.gettempdir(), 'test_product_migration.db')


def cleanup_test_db():
    """Remove test database"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
        logger.info(f"🧹 Cleaned up test database: {TEST_DB}")


def test_migration_script():
    """Test the migration script"""
    print("\n🧪 Testing Migration Script")
    print("=" * 70)
    
    cleanup_test_db()
    
    from migrate_product_db import ProductDatabaseMigration
    
    # Test migration on new database
    migration = ProductDatabaseMigration(TEST_DB)
    success = migration.run_migration()
    
    assert success, "Migration should succeed"
    assert os.path.exists(TEST_DB), "Database file should be created"
    
    # Verify tables exist
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    assert cursor.fetchone() is not None, "Products table should exist"
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_products'")
    assert cursor.fetchone() is not None, "Admin_products table should exist"
    
    # Verify indexes exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_products_name'")
    assert cursor.fetchone() is not None, "Index idx_products_name should exist"
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_admin_products_admin_id'")
    assert cursor.fetchone() is not None, "Index idx_admin_products_admin_id should exist"
    
    conn.close()
    
    print("✅ Migration script test passed\n")


def test_diagnostics_script():
    """Test the diagnostics script"""
    print("\n🧪 Testing Diagnostics Script")
    print("=" * 70)
    
    from diagnose_product_db import ProductDatabaseDiagnostics
    
    # Add some test data
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO products (name, cost_price) VALUES ('Test Product', 100.0)")
    cursor.execute("""
        INSERT INTO admin_products 
        (admin_id, admin_name, product_id, product_name, quantity, cost_price, total_debt)
        VALUES (1, 'Test Admin', 1, 'Test Product', 2, 100.0, 200.0)
    """)
    
    conn.commit()
    conn.close()
    
    # Run diagnostics
    diagnostics = ProductDatabaseDiagnostics(TEST_DB)
    success = diagnostics.run_diagnostics()
    
    assert success, "Diagnostics should succeed"
    
    print("✅ Diagnostics script test passed\n")


def test_diagnostics_on_missing_database():
    """Test diagnostics on non-existent database"""
    print("\n🧪 Testing Diagnostics on Missing Database")
    print("=" * 70)
    
    from diagnose_product_db import ProductDatabaseDiagnostics
    
    missing_db = '/tmp/nonexistent_db.db'
    if os.path.exists(missing_db):
        os.remove(missing_db)
    
    diagnostics = ProductDatabaseDiagnostics(missing_db)
    success = diagnostics.run_diagnostics()
    
    assert not success, "Diagnostics should fail on missing database"
    
    print("✅ Diagnostics on missing database test passed\n")


def test_diagnostics_with_data_issues():
    """Test diagnostics with data integrity issues"""
    print("\n🧪 Testing Diagnostics with Data Issues")
    print("=" * 70)
    
    cleanup_test_db()
    
    from migrate_product_db import ProductDatabaseMigration
    from diagnose_product_db import ProductDatabaseDiagnostics
    
    # Create database
    migration = ProductDatabaseMigration(TEST_DB)
    migration.run_migration()
    
    # Add data with issues
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    # Invalid price
    cursor.execute("INSERT INTO products (name, cost_price) VALUES ('Bad Product', -10.0)")
    
    # Invalid quantity
    cursor.execute("INSERT INTO products (name, cost_price) VALUES ('Good Product', 50.0)")
    cursor.execute("""
        INSERT INTO admin_products 
        (admin_id, admin_name, product_id, product_name, quantity, cost_price, total_debt)
        VALUES (1, 'Test Admin', 2, 'Good Product', -5, 50.0, -250.0)
    """)
    
    conn.commit()
    conn.close()
    
    # Run diagnostics - should detect issues
    diagnostics = ProductDatabaseDiagnostics(TEST_DB)
    success = diagnostics.run_diagnostics()
    
    assert success, "Diagnostics should run even with data issues"
    
    print("✅ Diagnostics with data issues test passed\n")


def test_reset_script_clean():
    """Test reset script with clean option"""
    print("\n🧪 Testing Reset Script (Clean Mode)")
    print("=" * 70)
    
    from reset_product_db import ProductDatabaseReset
    
    # Add some data first
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute("DELETE FROM admin_products")
    cursor.execute("DELETE FROM products")
    
    cursor.execute("INSERT INTO products (name, cost_price) VALUES ('Product To Delete', 100.0)")
    conn.commit()
    conn.close()
    
    # Run clean reset (without data preservation)
    reset_handler = ProductDatabaseReset(TEST_DB)
    success = reset_handler.reset_without_data_preservation()
    
    assert success, "Reset should succeed"
    
    # Verify tables exist but are empty
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    assert count == 0, "Products table should be empty after clean reset"
    
    conn.close()
    
    print("✅ Reset script (clean mode) test passed\n")


def test_reset_script_with_preservation():
    """Test reset script with data preservation"""
    print("\n🧪 Testing Reset Script (Data Preservation)")
    print("=" * 70)
    
    from reset_product_db import ProductDatabaseReset
    
    # Add some data
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM admin_products")
    cursor.execute("DELETE FROM products")
    
    cursor.execute("INSERT INTO products (name, cost_price) VALUES ('Product To Preserve', 150.0)")
    product_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO admin_products 
        (admin_id, admin_name, product_id, product_name, quantity, cost_price, total_debt)
        VALUES (1, 'Admin', ?, 'Product To Preserve', 3, 150.0, 450.0)
    """, (product_id,))
    
    conn.commit()
    conn.close()
    
    # Run reset with data preservation
    reset_handler = ProductDatabaseReset(TEST_DB)
    success = reset_handler.reset_with_data_preservation()
    
    assert success, "Reset with preservation should succeed"
    
    # Verify data was preserved
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM products")
    product_count = cursor.fetchone()[0]
    assert product_count == 1, "Product should be preserved"
    
    cursor.execute("SELECT COUNT(*) FROM admin_products")
    admin_product_count = cursor.fetchone()[0]
    assert admin_product_count == 1, "Admin product should be preserved"
    
    cursor.execute("SELECT name FROM products WHERE name = 'Product To Preserve'")
    assert cursor.fetchone() is not None, "Specific product should be preserved"
    
    conn.close()
    
    print("✅ Reset script (data preservation) test passed\n")


def test_migration_on_existing_database():
    """Test migration on database that already has tables"""
    print("\n🧪 Testing Migration on Existing Database")
    print("=" * 70)
    
    from migrate_product_db import ProductDatabaseMigration
    
    # Database already exists with tables from previous tests
    migration = ProductDatabaseMigration(TEST_DB)
    success = migration.run_migration()
    
    assert success, "Migration should succeed on existing database"
    
    # Verify tables still exist
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    assert cursor.fetchone() is not None, "Products table should still exist"
    
    conn.close()
    
    print("✅ Migration on existing database test passed\n")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("   TESTING PRODUCT DATABASE MIGRATION TOOLS")
    print("=" * 70)
    
    try:
        test_migration_script()
        test_diagnostics_script()
        test_diagnostics_on_missing_database()
        test_diagnostics_with_data_issues()
        test_reset_script_clean()
        test_reset_script_with_preservation()
        test_migration_on_existing_database()
        
        print("\n" + "=" * 70)
        print("✅ ALL MIGRATION TOOLS TESTS PASSED!")
        print("=" * 70)
        
        # Cleanup
        cleanup_test_db()
        
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
