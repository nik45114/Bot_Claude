#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Product Database Diagnostics Script
Detailed logging and diagnosis of product database issues
"""

import sqlite3
import sys
import os
import logging
from datetime import datetime

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = 'knowledge.db'


class ProductDatabaseDiagnostics:
    """Handler for product database diagnostics"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        logger.info(f"🔍 Initializing Product Database Diagnostics for: {self.db_path}")
    
    def check_database_file(self) -> dict:
        """Check database file status"""
        logger.info("\n📂 Checking database file...")
        
        info = {
            'exists': False,
            'size': 0,
            'readable': False,
            'writable': False
        }
        
        if os.path.exists(self.db_path):
            info['exists'] = True
            logger.info(f"✅ Database file exists: {self.db_path}")
            
            # Get size
            info['size'] = os.path.getsize(self.db_path)
            logger.info(f"📊 File size: {info['size']:,} bytes ({info['size']/1024:.2f} KB)")
            
            # Check permissions
            info['readable'] = os.access(self.db_path, os.R_OK)
            info['writable'] = os.access(self.db_path, os.W_OK)
            
            if info['readable']:
                logger.info("✅ File is readable")
            else:
                logger.error("❌ File is NOT readable")
            
            if info['writable']:
                logger.info("✅ File is writable")
            else:
                logger.warning("⚠️  File is NOT writable")
        else:
            logger.error(f"❌ Database file does not exist: {self.db_path}")
        
        return info
    
    def check_database_integrity(self, cursor: sqlite3.Cursor) -> bool:
        """Check overall database integrity"""
        logger.info("\n🔍 Checking database integrity...")
        
        try:
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            if result and result[0] == 'ok':
                logger.info("✅ Database integrity check PASSED")
                return True
            else:
                logger.error(f"❌ Database integrity check FAILED: {result}")
                return False
        except Exception as e:
            logger.error(f"❌ Error checking database integrity: {e}")
            return False
    
    def check_table_status(self, cursor: sqlite3.Cursor, table_name: str) -> dict:
        """Check detailed status of a table"""
        logger.info(f"\n📋 Checking table: {table_name}")
        
        status = {
            'exists': False,
            'columns': [],
            'row_count': 0,
            'indexes': [],
            'foreign_keys': []
        }
        
        try:
            # Check if table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            
            if cursor.fetchone():
                status['exists'] = True
                logger.info(f"✅ Table '{table_name}' exists")
                
                # Get columns
                cursor.execute(f"PRAGMA table_info({table_name})")
                status['columns'] = cursor.fetchall()
                logger.info(f"📊 Columns ({len(status['columns'])}):")
                for col in status['columns']:
                    col_info = f"   {col[1]} ({col[2]})"
                    if col[3]:  # NOT NULL
                        col_info += " NOT NULL"
                    if col[4]:  # Default value
                        col_info += f" DEFAULT {col[4]}"
                    if col[5]:  # Primary key
                        col_info += " PRIMARY KEY"
                    logger.info(col_info)
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                status['row_count'] = cursor.fetchone()[0]
                logger.info(f"📊 Row count: {status['row_count']:,}")
                
                # Get indexes
                cursor.execute(f"PRAGMA index_list({table_name})")
                status['indexes'] = cursor.fetchall()
                if status['indexes']:
                    logger.info(f"🔍 Indexes ({len(status['indexes'])}):")
                    for idx in status['indexes']:
                        logger.info(f"   {idx[1]} {'(UNIQUE)' if idx[2] else ''}")
                else:
                    logger.info("ℹ️  No indexes on this table")
                
                # Get foreign keys
                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                status['foreign_keys'] = cursor.fetchall()
                if status['foreign_keys']:
                    logger.info(f"🔗 Foreign keys ({len(status['foreign_keys'])}):")
                    for fk in status['foreign_keys']:
                        logger.info(f"   {fk[3]} -> {fk[2]}.{fk[4]}")
                else:
                    logger.info("ℹ️  No foreign keys on this table")
            else:
                logger.error(f"❌ Table '{table_name}' does NOT exist")
        
        except Exception as e:
            logger.error(f"❌ Error checking table '{table_name}': {e}")
        
        return status
    
    def check_data_integrity(self, cursor: sqlite3.Cursor) -> dict:
        """Check data integrity issues"""
        logger.info("\n🔍 Checking data integrity...")
        
        issues = {
            'orphaned_admin_products': [],
            'products_with_invalid_prices': [],
            'admin_products_with_invalid_quantities': [],
            'products_with_empty_names': []
        }
        
        try:
            # Check for orphaned admin_products (referencing non-existent products)
            cursor.execute('''
                SELECT ap.id, ap.product_id, ap.product_name
                FROM admin_products ap
                LEFT JOIN products p ON ap.product_id = p.id
                WHERE p.id IS NULL
                LIMIT 10
            ''')
            issues['orphaned_admin_products'] = cursor.fetchall()
            
            if issues['orphaned_admin_products']:
                logger.warning(f"⚠️  Found {len(issues['orphaned_admin_products'])} orphaned admin_products records")
                for record in issues['orphaned_admin_products'][:5]:
                    logger.warning(f"   ID: {record[0]}, Product ID: {record[1]}, Name: {record[2]}")
            else:
                logger.info("✅ No orphaned admin_products records")
            
            # Check for products with invalid prices
            cursor.execute('''
                SELECT id, name, cost_price
                FROM products
                WHERE cost_price <= 0
            ''')
            issues['products_with_invalid_prices'] = cursor.fetchall()
            
            if issues['products_with_invalid_prices']:
                logger.warning(f"⚠️  Found {len(issues['products_with_invalid_prices'])} products with invalid prices")
                for record in issues['products_with_invalid_prices']:
                    logger.warning(f"   ID: {record[0]}, Name: {record[1]}, Price: {record[2]}")
            else:
                logger.info("✅ No products with invalid prices")
            
            # Check for admin_products with invalid quantities
            cursor.execute('''
                SELECT id, admin_name, product_name, quantity
                FROM admin_products
                WHERE quantity <= 0
            ''')
            issues['admin_products_with_invalid_quantities'] = cursor.fetchall()
            
            if issues['admin_products_with_invalid_quantities']:
                logger.warning(f"⚠️  Found {len(issues['admin_products_with_invalid_quantities'])} admin_products with invalid quantities")
                for record in issues['admin_products_with_invalid_quantities'][:5]:
                    logger.warning(f"   ID: {record[0]}, Admin: {record[1]}, Product: {record[2]}, Qty: {record[3]}")
            else:
                logger.info("✅ No admin_products with invalid quantities")
            
            # Check for products with empty names
            cursor.execute('''
                SELECT id, name, cost_price
                FROM products
                WHERE name = '' OR name IS NULL
            ''')
            issues['products_with_empty_names'] = cursor.fetchall()
            
            if issues['products_with_empty_names']:
                logger.warning(f"⚠️  Found {len(issues['products_with_empty_names'])} products with empty names")
            else:
                logger.info("✅ No products with empty names")
        
        except Exception as e:
            logger.error(f"❌ Error checking data integrity: {e}")
        
        return issues
    
    def get_statistics(self, cursor: sqlite3.Cursor) -> dict:
        """Get database statistics"""
        logger.info("\n📊 Gathering statistics...")
        
        stats = {}
        
        try:
            # Total products
            cursor.execute("SELECT COUNT(*) FROM products")
            stats['total_products'] = cursor.fetchone()[0]
            logger.info(f"📦 Total products: {stats['total_products']:,}")
            
            # Total admin_products records
            cursor.execute("SELECT COUNT(*) FROM admin_products")
            stats['total_admin_products'] = cursor.fetchone()[0]
            logger.info(f"📋 Total admin_products records: {stats['total_admin_products']:,}")
            
            # Unsettled records
            cursor.execute("SELECT COUNT(*) FROM admin_products WHERE settled = FALSE")
            stats['unsettled_records'] = cursor.fetchone()[0]
            logger.info(f"💳 Unsettled records: {stats['unsettled_records']:,}")
            
            # Total unsettled debt
            cursor.execute("SELECT SUM(total_debt) FROM admin_products WHERE settled = FALSE")
            result = cursor.fetchone()[0]
            stats['total_debt'] = result if result else 0
            logger.info(f"💰 Total unsettled debt: {stats['total_debt']:,.2f} ₽")
            
            # Number of admins with debt
            cursor.execute('''
                SELECT COUNT(DISTINCT admin_id) 
                FROM admin_products 
                WHERE settled = FALSE
            ''')
            stats['admins_with_debt'] = cursor.fetchone()[0]
            logger.info(f"👥 Admins with debt: {stats['admins_with_debt']}")
            
            # Most expensive product
            cursor.execute("SELECT name, cost_price FROM products ORDER BY cost_price DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                stats['most_expensive_product'] = result
                logger.info(f"💎 Most expensive product: {result[0]} ({result[1]:,.2f} ₽)")
            
            # Most taken product
            cursor.execute('''
                SELECT product_name, SUM(quantity) as total
                FROM admin_products
                WHERE settled = FALSE
                GROUP BY product_name
                ORDER BY total DESC
                LIMIT 1
            ''')
            result = cursor.fetchone()
            if result:
                stats['most_taken_product'] = result
                logger.info(f"📦 Most taken product: {result[0]} ({result[1]} units)")
        
        except Exception as e:
            logger.error(f"❌ Error gathering statistics: {e}")
        
        return stats
    
    def run_diagnostics(self) -> bool:
        """Run complete diagnostics"""
        logger.info("🚀 Starting Product Database Diagnostics")
        logger.info("=" * 70)
        
        try:
            # Check database file
            file_info = self.check_database_file()
            
            if not file_info['exists']:
                logger.error("\n❌ Database file does not exist. Nothing to diagnose.")
                return False
            
            if not file_info['readable']:
                logger.error("\n❌ Database file is not readable. Check permissions.")
                return False
            
            # Connect to database
            logger.info(f"\n📂 Connecting to database: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            logger.info("✅ Database connection established")
            
            # Check database integrity
            self.check_database_integrity(cursor)
            
            # Check tables
            products_status = self.check_table_status(cursor, 'products')
            admin_products_status = self.check_table_status(cursor, 'admin_products')
            
            # Check data integrity
            if products_status['exists'] and admin_products_status['exists']:
                data_issues = self.check_data_integrity(cursor)
                
                # Get statistics
                stats = self.get_statistics(cursor)
            else:
                logger.warning("\n⚠️  One or more tables missing, skipping data checks")
            
            # Close connection
            conn.close()
            logger.info("\n✅ Database connection closed")
            
            # Summary
            logger.info("\n" + "=" * 70)
            logger.info("📋 DIAGNOSTICS SUMMARY")
            logger.info("=" * 70)
            
            if products_status['exists'] and admin_products_status['exists']:
                logger.info("✅ All product tables exist")
                logger.info(f"📊 Products table: {products_status['row_count']:,} rows")
                logger.info(f"📊 Admin_products table: {admin_products_status['row_count']:,} rows")
            else:
                logger.warning("⚠️  Some tables are missing!")
                if not products_status['exists']:
                    logger.warning("   - products table is MISSING")
                if not admin_products_status['exists']:
                    logger.warning("   - admin_products table is MISSING")
                logger.info("\n💡 Recommendation: Run migrate_product_db.py to create missing tables")
            
            logger.info("=" * 70)
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"\n❌ SQLite error during diagnostics: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        except Exception as e:
            logger.error(f"\n❌ Unexpected error during diagnostics: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("   PRODUCT DATABASE DIAGNOSTICS")
    print("=" * 70 + "\n")
    
    # Check if custom database path provided
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    
    # Run diagnostics
    diagnostics = ProductDatabaseDiagnostics(db_path)
    success = diagnostics.run_diagnostics()
    
    # Return exit code
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
