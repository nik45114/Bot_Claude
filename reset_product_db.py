#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Product Database Reset Script
Reset or recreate product database tables when there are issues
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


class ProductDatabaseReset:
    """Handler for resetting product database"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        logger.info(f"🔧 Initializing Product Database Reset for: {self.db_path}")
    
    def backup_database(self) -> str:
        """Create a backup of the database before reset"""
        try:
            if not os.path.exists(self.db_path):
                logger.info("ℹ️  No database to backup")
                return None
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{self.db_path}.backup_{timestamp}"
            
            logger.info(f"📦 Creating backup: {backup_path}")
            
            # Copy database file
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            size = os.path.getsize(backup_path)
            logger.info(f"✅ Backup created: {backup_path} ({size:,} bytes)")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            return None
    
    def export_products_data(self, cursor: sqlite3.Cursor) -> list:
        """Export existing products data"""
        try:
            logger.info("📤 Exporting products data...")
            cursor.execute("SELECT * FROM products")
            products = cursor.fetchall()
            logger.info(f"✅ Exported {len(products)} products")
            return products
        except Exception as e:
            logger.error(f"❌ Error exporting products: {e}")
            return []
    
    def export_admin_products_data(self, cursor: sqlite3.Cursor) -> list:
        """Export existing admin_products data"""
        try:
            logger.info("📤 Exporting admin_products data...")
            cursor.execute("SELECT * FROM admin_products")
            admin_products = cursor.fetchall()
            logger.info(f"✅ Exported {len(admin_products)} admin_products records")
            return admin_products
        except Exception as e:
            logger.error(f"❌ Error exporting admin_products: {e}")
            return []
    
    def drop_table(self, cursor: sqlite3.Cursor, table_name: str) -> bool:
        """Drop a table"""
        try:
            logger.info(f"🗑️  Dropping table: {table_name}")
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            logger.info(f"✅ Table '{table_name}' dropped")
            return True
        except Exception as e:
            logger.error(f"❌ Error dropping table '{table_name}': {e}")
            return False
    
    def drop_indexes(self, cursor: sqlite3.Cursor) -> bool:
        """Drop all product-related indexes"""
        try:
            logger.info("🗑️  Dropping indexes...")
            
            indexes = [
                'idx_products_name',
                'idx_admin_products_admin_id',
                'idx_admin_products_settled',
                'idx_admin_products_admin_settled'
            ]
            
            for idx in indexes:
                try:
                    cursor.execute(f"DROP INDEX IF EXISTS {idx}")
                    logger.info(f"✅ Dropped index: {idx}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not drop index '{idx}': {e}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error dropping indexes: {e}")
            return False
    
    def reset_with_data_preservation(self) -> bool:
        """Reset tables while preserving existing data"""
        logger.info("🔄 Starting reset WITH data preservation")
        logger.info("=" * 70)
        
        try:
            # Create backup
            backup_path = self.backup_database()
            if not backup_path and os.path.exists(self.db_path):
                logger.error("❌ Failed to create backup, aborting reset")
                return False
            
            # Connect to database
            logger.info(f"📂 Connecting to database: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            logger.info("✅ Database connection established")
            
            # Export existing data
            logger.info("\n📤 Exporting existing data...")
            products_data = self.export_products_data(cursor)
            admin_products_data = self.export_admin_products_data(cursor)
            
            # Drop indexes
            logger.info("\n🗑️  Removing indexes...")
            self.drop_indexes(cursor)
            
            # Drop tables
            logger.info("\n🗑️  Removing tables...")
            self.drop_table(cursor, 'admin_products')
            self.drop_table(cursor, 'products')
            
            # Commit drops
            conn.commit()
            logger.info("✅ Tables dropped successfully")
            
            # Recreate tables using migration script
            logger.info("\n🔨 Recreating tables...")
            conn.close()
            
            # Import and run migration
            from migrate_product_db import ProductDatabaseMigration
            migration = ProductDatabaseMigration(self.db_path)
            
            if not migration.run_migration():
                logger.error("❌ Failed to recreate tables")
                return False
            
            # Restore data if it exists
            if products_data or admin_products_data:
                logger.info("\n📥 Restoring data...")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Restore products
                if products_data:
                    logger.info(f"📥 Restoring {len(products_data)} products...")
                    for product in products_data:
                        try:
                            cursor.execute('''
                                INSERT INTO products (id, name, cost_price, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?)
                            ''', product)
                        except Exception as e:
                            logger.warning(f"⚠️  Could not restore product {product[1]}: {e}")
                    logger.info("✅ Products restored")
                
                # Restore admin_products
                if admin_products_data:
                    logger.info(f"📥 Restoring {len(admin_products_data)} admin_products records...")
                    for admin_product in admin_products_data:
                        try:
                            cursor.execute('''
                                INSERT INTO admin_products 
                                (id, admin_id, admin_name, product_id, product_name, 
                                 quantity, cost_price, total_debt, taken_at, settled)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', admin_product)
                        except Exception as e:
                            logger.warning(f"⚠️  Could not restore admin_product record: {e}")
                    logger.info("✅ Admin_products restored")
                
                conn.commit()
                conn.close()
            
            logger.info("\n" + "=" * 70)
            logger.info("🎉 Database reset completed successfully WITH data preservation!")
            logger.info(f"💾 Backup saved at: {backup_path}")
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Error during reset: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def reset_without_data_preservation(self) -> bool:
        """Reset tables without preserving data (clean slate)"""
        logger.info("🔄 Starting CLEAN reset WITHOUT data preservation")
        logger.info("=" * 70)
        
        try:
            # Create backup if database exists
            if os.path.exists(self.db_path):
                backup_path = self.backup_database()
                if backup_path:
                    logger.info(f"💾 Backup created at: {backup_path}")
            
            # Connect to database
            logger.info(f"📂 Connecting to database: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            logger.info("✅ Database connection established")
            
            # Drop indexes
            logger.info("\n🗑️  Removing indexes...")
            self.drop_indexes(cursor)
            
            # Drop tables
            logger.info("\n🗑️  Removing tables...")
            self.drop_table(cursor, 'admin_products')
            self.drop_table(cursor, 'products')
            
            # Commit drops
            conn.commit()
            logger.info("✅ Tables dropped successfully")
            conn.close()
            
            # Recreate tables using migration script
            logger.info("\n🔨 Recreating tables...")
            from migrate_product_db import ProductDatabaseMigration
            migration = ProductDatabaseMigration(self.db_path)
            
            if not migration.run_migration():
                logger.error("❌ Failed to recreate tables")
                return False
            
            logger.info("\n" + "=" * 70)
            logger.info("🎉 Clean database reset completed successfully!")
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Error during reset: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("   PRODUCT DATABASE RESET SCRIPT")
    print("=" * 70 + "\n")
    
    # Parse arguments
    db_path = DB_PATH
    preserve_data = True
    
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == '--clean':
                preserve_data = False
                logger.info("🧹 Clean reset mode: Data will NOT be preserved")
            elif arg.startswith('--db='):
                db_path = arg.split('=')[1]
                logger.info(f"📂 Using custom database: {db_path}")
            elif arg in ['--help', '-h']:
                print("Usage: python3 reset_product_db.py [OPTIONS]")
                print("\nOptions:")
                print("  --clean          Clean reset without preserving data")
                print("  --db=PATH        Use custom database path")
                print("  -h, --help       Show this help message")
                print("\nExamples:")
                print("  python3 reset_product_db.py")
                print("  python3 reset_product_db.py --clean")
                print("  python3 reset_product_db.py --db=test.db")
                print()
                return 0
    
    # Confirm action
    if preserve_data:
        print("⚠️  This will reset product tables while preserving existing data.")
    else:
        print("⚠️  WARNING: This will PERMANENTLY delete all product data!")
    
    print(f"📂 Database: {db_path}")
    print("\nPress ENTER to continue, or Ctrl+C to cancel...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ Reset cancelled by user")
        return 1
    
    # Run reset
    reset_handler = ProductDatabaseReset(db_path)
    
    if preserve_data:
        success = reset_handler.reset_with_data_preservation()
    else:
        success = reset_handler.reset_without_data_preservation()
    
    # Return exit code
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
