#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Product Database Migration Script
Ensures product tables exist and are properly initialized with detailed logging
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


class ProductDatabaseMigration:
    """Handler for product database migrations"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        logger.info(f"🔧 Initializing Product Database Migration for: {self.db_path}")
    
    def check_database_exists(self) -> bool:
        """Check if database file exists"""
        exists = os.path.exists(self.db_path)
        if exists:
            logger.info(f"✅ Database file exists: {self.db_path}")
            size = os.path.getsize(self.db_path)
            logger.info(f"📊 Database size: {size:,} bytes")
        else:
            logger.warning(f"⚠️  Database file not found: {self.db_path}")
        return exists
    
    def check_table_exists(self, cursor: sqlite3.Cursor, table_name: str) -> bool:
        """Check if a table exists in the database"""
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        exists = cursor.fetchone() is not None
        if exists:
            logger.info(f"✅ Table '{table_name}' exists")
        else:
            logger.warning(f"⚠️  Table '{table_name}' does not exist")
        return exists
    
    def get_table_schema(self, cursor: sqlite3.Cursor, table_name: str) -> list:
        """Get schema information for a table"""
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            logger.info(f"📋 Schema for '{table_name}':")
            for col in columns:
                logger.info(f"   - {col[1]} ({col[2]}) {'NOT NULL' if col[3] else ''} {'PK' if col[5] else ''}")
            return columns
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Error getting schema for '{table_name}': {e}")
            return []
    
    def get_table_row_count(self, cursor: sqlite3.Cursor, table_name: str) -> int:
        """Get row count for a table"""
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            logger.info(f"📊 Table '{table_name}' has {count:,} rows")
            return count
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Error counting rows in '{table_name}': {e}")
            return -1
    
    def create_products_table(self, cursor: sqlite3.Cursor) -> bool:
        """Create products table"""
        try:
            logger.info("📋 Creating products table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    cost_price REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("✅ Products table created successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Error creating products table: {e}")
            return False
    
    def create_admin_products_table(self, cursor: sqlite3.Cursor) -> bool:
        """Create admin_products table"""
        try:
            logger.info("📋 Creating admin_products table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    admin_name TEXT NOT NULL,
                    product_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    cost_price REAL NOT NULL,
                    total_debt REAL NOT NULL,
                    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settled BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            logger.info("✅ Admin_products table created successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Error creating admin_products table: {e}")
            return False
    
    def create_indexes(self, cursor: sqlite3.Cursor) -> bool:
        """Create indexes for better performance"""
        try:
            logger.info("📋 Creating indexes...")
            
            # Index on product name for faster lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_products_name 
                ON products(name)
            ''')
            logger.info("✅ Created index: idx_products_name")
            
            # Index on admin_id for faster debt queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_admin_products_admin_id 
                ON admin_products(admin_id)
            ''')
            logger.info("✅ Created index: idx_admin_products_admin_id")
            
            # Index on settled status for faster filtering
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_admin_products_settled 
                ON admin_products(settled)
            ''')
            logger.info("✅ Created index: idx_admin_products_settled")
            
            # Composite index on admin_id and settled for common queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_admin_products_admin_settled 
                ON admin_products(admin_id, settled)
            ''')
            logger.info("✅ Created index: idx_admin_products_admin_settled")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            return False
    
    def verify_table_integrity(self, cursor: sqlite3.Cursor, table_name: str) -> bool:
        """Verify table integrity"""
        try:
            logger.info(f"🔍 Verifying integrity of '{table_name}'...")
            cursor.execute(f"PRAGMA integrity_check({table_name})")
            result = cursor.fetchone()
            if result and result[0] == 'ok':
                logger.info(f"✅ Table '{table_name}' integrity check passed")
                return True
            else:
                logger.error(f"❌ Table '{table_name}' integrity check failed: {result}")
                return False
        except Exception as e:
            logger.error(f"❌ Error checking integrity of '{table_name}': {e}")
            return False
    
    def run_migration(self) -> bool:
        """Run the complete migration process"""
        logger.info("🚀 Starting Product Database Migration")
        logger.info("=" * 70)
        
        try:
            # Check if database exists
            self.check_database_exists()
            
            # Connect to database
            logger.info(f"📂 Connecting to database: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            logger.info("✅ Database connection established")
            
            # Check existing tables
            logger.info("\n📊 Checking existing tables...")
            products_exists = self.check_table_exists(cursor, 'products')
            admin_products_exists = self.check_table_exists(cursor, 'admin_products')
            
            # Get current state if tables exist
            if products_exists:
                self.get_table_schema(cursor, 'products')
                self.get_table_row_count(cursor, 'products')
            
            if admin_products_exists:
                self.get_table_schema(cursor, 'admin_products')
                self.get_table_row_count(cursor, 'admin_products')
            
            # Create or update tables
            logger.info("\n🔨 Creating/updating tables...")
            if not self.create_products_table(cursor):
                logger.error("❌ Failed to create products table")
                conn.close()
                return False
            
            if not self.create_admin_products_table(cursor):
                logger.error("❌ Failed to create admin_products table")
                conn.close()
                return False
            
            # Create indexes
            logger.info("\n🔍 Creating indexes...")
            if not self.create_indexes(cursor):
                logger.warning("⚠️  Some indexes may not have been created")
            
            # Commit changes
            logger.info("\n💾 Committing changes...")
            conn.commit()
            logger.info("✅ Changes committed successfully")
            
            # Verify final state
            logger.info("\n✔️  Verifying final state...")
            products_exists = self.check_table_exists(cursor, 'products')
            admin_products_exists = self.check_table_exists(cursor, 'admin_products')
            
            if products_exists and admin_products_exists:
                logger.info("\n📊 Final table state:")
                self.get_table_schema(cursor, 'products')
                self.get_table_row_count(cursor, 'products')
                self.get_table_schema(cursor, 'admin_products')
                self.get_table_row_count(cursor, 'admin_products')
                
                # Verify integrity
                logger.info("\n🔍 Running integrity checks...")
                self.verify_table_integrity(cursor, 'products')
                self.verify_table_integrity(cursor, 'admin_products')
            
            # Close connection
            conn.close()
            logger.info("\n✅ Database connection closed")
            
            logger.info("\n" + "=" * 70)
            logger.info("🎉 Product Database Migration completed successfully!")
            logger.info("=" * 70)
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"\n❌ SQLite error during migration: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        except Exception as e:
            logger.error(f"\n❌ Unexpected error during migration: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("   PRODUCT DATABASE MIGRATION SCRIPT")
    print("=" * 70 + "\n")
    
    # Check if custom database path provided
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    
    # Run migration
    migration = ProductDatabaseMigration(db_path)
    success = migration.run_migration()
    
    # Return exit code
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
