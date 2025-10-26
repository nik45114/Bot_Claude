#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runtime Migrator - Lightweight database migration manager
Detects missing columns and applies SQL migrations on-the-fly
"""

import os
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class RuntimeMigrator:
    """Lightweight migrator for runtime schema fixes and SQL migrations"""
    
    def __init__(self, db_path: str = 'knowledge.db', migrations_dir: str = './migrations'):
        """
        Initialize runtime migrator
        
        Args:
            db_path: Path to SQLite database
            migrations_dir: Directory containing migration SQL files
        """
        self.db_path = db_path
        self.migrations_dir = migrations_dir
    
    def check_column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            conn.close()
            return column_name in columns
        except Exception as e:
            logger.error(f"Error checking column {table_name}.{column_name}: {e}")
            return False
    
    def add_column_if_missing(self, table_name: str, column_name: str, column_type: str = 'TIMESTAMP', default: str = 'CURRENT_TIMESTAMP') -> bool:
        """
        Add column to table if it doesn't exist
        
        Args:
            table_name: Name of the table
            column_name: Name of the column to add
            column_type: SQL type of the column
            default: Default value for the column
        
        Returns:
            True if column was added or already exists, False on error
        """
        try:
            if self.check_column_exists(table_name, column_name):
                return True
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default}")
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Added column {table_name}.{column_name}")
            return True
        except Exception as e:
            logger.error(f"Error adding column {table_name}.{column_name}: {e}")
            return False
    
    def apply_runtime_fixes(self) -> Tuple[bool, List[str]]:
        """
        Apply runtime schema fixes for known issues
        
        Returns:
            Tuple of (success, messages)
        """
        messages = []
        all_success = True
        
        # Check for finmon tables and add missing ts columns if needed
        tables_to_fix = [
            ('finmon_shifts', 'ts', 'TIMESTAMP', 'CURRENT_TIMESTAMP'),
            ('finmon_movements', 'ts', 'TIMESTAMP', 'CURRENT_TIMESTAMP'),
        ]
        
        for table_name, column_name, column_type, default in tables_to_fix:
            # First check if table exists
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                table_exists = cursor.fetchone() is not None
                conn.close()
                
                if not table_exists:
                    continue
                
                if not self.check_column_exists(table_name, column_name):
                    if self.add_column_if_missing(table_name, column_name, column_type, default):
                        messages.append(f"✅ Fixed {table_name}.{column_name}")
                    else:
                        messages.append(f"❌ Failed to fix {table_name}.{column_name}")
                        all_success = False
            except Exception as e:
                logger.error(f"Error checking table {table_name}: {e}")
        
        return all_success, messages
    
    def get_pending_migrations(self) -> List[str]:
        """
        Get list of pending migration files
        
        Returns:
            List of migration file paths
        """
        migrations_path = Path(self.migrations_dir)
        if not migrations_path.exists():
            return []
        
        # Get all .sql files sorted by name
        sql_files = sorted(migrations_path.glob('*.sql'))
        return [str(f) for f in sql_files]
    
    def apply_migration_file(self, filepath: str) -> Tuple[bool, str]:
        """
        Apply a single migration SQL file
        
        Args:
            filepath: Path to SQL file
        
        Returns:
            Tuple of (success, message)
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Execute SQL (split by semicolon for multiple statements)
            cursor.executescript(sql_content)
            
            conn.commit()
            conn.close()
            
            filename = os.path.basename(filepath)
            logger.info(f"✅ Applied migration: {filename}")
            return True, f"✅ {filename}"
        except Exception as e:
            filename = os.path.basename(filepath)
            logger.error(f"❌ Failed to apply migration {filename}: {e}")
            return False, f"❌ {filename}: {str(e)[:50]}"
    
    def apply_all_migrations(self) -> Tuple[bool, List[str]]:
        """
        Apply all pending migrations
        
        Returns:
            Tuple of (all_success, messages)
        """
        messages = []
        all_success = True
        
        # First apply runtime fixes
        fixes_success, fixes_messages = self.apply_runtime_fixes()
        messages.extend(fixes_messages)
        if not fixes_success:
            all_success = False
        
        # Then apply SQL migrations
        pending = self.get_pending_migrations()
        if not pending:
            messages.append("ℹ️ No migration files found")
        else:
            for filepath in pending:
                success, message = self.apply_migration_file(filepath)
                messages.append(message)
                if not success:
                    all_success = False
        
        return all_success, messages
    
    def get_summary(self) -> str:
        """
        Get a one-line summary of migration status
        
        Returns:
            Summary string
        """
        pending = self.get_pending_migrations()
        pending_count = len(pending)
        
        if pending_count == 0:
            return "✅ No pending migrations"
        else:
            return f"📋 {pending_count} migration file(s) available"
