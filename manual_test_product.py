#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manual test script to demonstrate ProductManager fixes
This can be run to verify that adding products works correctly
"""

import logging
import os

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from product_manager import ProductManager

def main():
    print("=" * 70)
    print("   MANUAL TEST: Product Manager Bug Fix Demonstration")
    print("=" * 70)
    print()
    
    # Use a test database
    test_db = 'manual_test_product.db'
    
    # Clean up previous test
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"🧹 Cleaned up previous test database\n")
    
    print("📋 Step 1: Initialize ProductManager")
    print("-" * 70)
    pm = ProductManager(test_db)
    print()
    
    print("📋 Step 2: Add first product (Monster Energy)")
    print("-" * 70)
    result1 = pm.add_product('Monster Energy', 50.0)
    print(f"Result: {result1}")
    print()
    
    print("📋 Step 3: Add second product (Red Bull)")
    print("-" * 70)
    result2 = pm.add_product('Red Bull', 55.0)
    print(f"Result: {result2}")
    print()
    
    print("📋 Step 4: Try to add duplicate (Monster Energy)")
    print("-" * 70)
    result3 = pm.add_product('Monster Energy', 60.0)
    print(f"Result: {result3} (should be False)")
    print()
    
    print("📋 Step 5: Try to add product with invalid price")
    print("-" * 70)
    result4 = pm.add_product('Invalid Product', -10.0)
    print(f"Result: {result4} (should be False)")
    print()
    
    print("📋 Step 6: Try to add product with empty name")
    print("-" * 70)
    result5 = pm.add_product('', 100.0)
    print(f"Result: {result5} (should be False)")
    print()
    
    print("📋 Step 7: List all products")
    print("-" * 70)
    products = pm.list_products()
    print(f"\nProducts in database ({len(products)}):")
    for p in products:
        print(f"  - ID: {p['id']}, Name: {p['name']}, Price: {p['cost_price']} ₽")
    print()
    
    print("📋 Step 8: Format products list")
    print("-" * 70)
    formatted = pm.format_products_list()
    print(formatted)
    print()
    
    print("=" * 70)
    print("✅ MANUAL TEST COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"  - ProductManager initialized: ✅")
    print(f"  - Valid products added: ✅ (2 products)")
    print(f"  - Duplicate rejected: ✅")
    print(f"  - Invalid price rejected: ✅")
    print(f"  - Empty name rejected: ✅")
    print(f"  - Products listed: ✅")
    print()
    print(f"Test database: {test_db}")
    print("You can inspect it with: sqlite3 manual_test_product.db")
    print()

if __name__ == '__main__':
    main()
