#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Migration Runner
Runs SQL migration files in order
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def run_migrations(db_path: str = 'knowledge.db', migrations_dir: str = './migrations'):
    """
    Run all SQL migration files in order
    
    Args:
        db_path: Path to SQLite database
        migrations_dir: Directory containing migration files
    """
    logger.info(f"📊 Running migrations from {migrations_dir}")
    logger.info(f"📁 Database: {db_path}")
    
    migrations_path = Path(migrations_dir)
    if not migrations_path.exists():
        logger.error(f"❌ Migrations directory not found: {migrations_dir}")
        return False
    
    # Get all .sql files and sort them
    migration_files = sorted(migrations_path.glob('*.sql'))
    
    if not migration_files:
        logger.warning(f"⚠️ No migration files found in {migrations_dir}")
        return True
    
    logger.info(f"Found {len(migration_files)} migration file(s)")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create migrations tracking table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        
        # Get list of already applied migrations
        cursor.execute('SELECT filename FROM _migrations')
        applied = set(row[0] for row in cursor.fetchall())
        
        # Run each migration
        for migration_file in migration_files:
            filename = migration_file.name
            
            if filename in applied:
                logger.info(f"⏭️  Skipping {filename} (already applied)")
                continue
            
            logger.info(f"🔄 Applying {filename}...")
            
            try:
                # Read and execute migration
                with open(migration_file, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                
                # Split script into individual statements to handle ALTER TABLE errors gracefully
                statements = []
                current_statement = []
                
                for line in sql_script.split('\n'):
                    stripped = line.strip()
                    # Skip comments and empty lines
                    if stripped.startswith('--') or not stripped:
                        continue
                    current_statement.append(line)
                    # Check if statement is complete (ends with semicolon)
                    if stripped.endswith(';'):
                        statements.append('\n'.join(current_statement))
                        current_statement = []
                
                # Execute each statement separately
                for statement in statements:
                    if statement.strip():
                        try:
                            cursor.execute(statement)
                        except sqlite3.OperationalError as e:
                            # Allow some errors like duplicate column or table doesn't exist
                            error_msg = str(e).lower()
                            if 'duplicate column' in error_msg or 'already exists' in error_msg:
                                logger.debug(f"Skipping: {error_msg}")
                            elif 'no such table' in error_msg and 'alter table' in statement.lower():
                                logger.debug(f"Skipping ALTER on non-existent table: {error_msg}")
                            else:
                                raise
                
                # Mark as applied
                cursor.execute('INSERT INTO _migrations (filename) VALUES (?)', (filename,))
                conn.commit()
                
                logger.info(f"✅ Applied {filename}")
                
            except Exception as e:
                logger.error(f"❌ Error applying {filename}: {e}")
                conn.rollback()
                raise
        
        conn.close()
        logger.info("✅ All migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Allow custom db path from command line
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'knowledge.db'
    
    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
        db_path = os.getenv('DB_PATH', db_path)
    except ImportError:
        pass
    
    success = run_migrations(db_path)
    sys.exit(0 if success else 1)
