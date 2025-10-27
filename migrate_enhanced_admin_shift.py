#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Database Migration Script
"""

import sqlite3
import os
import sys

def run_enhanced_migration(db_path: str):
    """Выполнение миграции базы данных для улучшенной системы"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Создаем таблицы для улучшенной системы
        cursor.execute("CREATE TABLE IF NOT EXISTS admin_management (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL, username TEXT, full_name TEXT, role TEXT DEFAULT 'staff', permissions TEXT, added_by INTEGER, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_seen TIMESTAMP, is_active BOOLEAN DEFAULT 1, notes TEXT, shift_count INTEGER DEFAULT 0, last_shift_date DATE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        
        cursor.execute("CREATE TABLE IF NOT EXISTS shift_control (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER NOT NULL, club_name TEXT NOT NULL, shift_date DATE NOT NULL, shift_time TEXT NOT NULL, fact_cash REAL DEFAULT 0, fact_card REAL DEFAULT 0, qr_amount REAL DEFAULT 0, card2_amount REAL DEFAULT 0, safe_cash_end REAL DEFAULT 0, box_cash_end REAL DEFAULT 0, photo_file_id TEXT, photo_path TEXT, ocr_text TEXT, ocr_numbers TEXT, ocr_verified BOOLEAN DEFAULT 0, ocr_confidence REAL DEFAULT 0, status TEXT DEFAULT 'pending', verified_by INTEGER, verified_at TIMESTAMP, verification_notes TEXT, visible_to_owner_only BOOLEAN DEFAULT 1, shared_with_admins TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (admin_id) REFERENCES admin_management(user_id), FOREIGN KEY (verified_by) REFERENCES admin_management(user_id))")
        
        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_management_user_id ON admin_management(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_control_admin ON shift_control(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_control_date ON shift_control(shift_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_control_status ON shift_control(status)")
        
        # Синхронизируем существующих админов
        cursor.execute("INSERT OR IGNORE INTO admin_management (user_id, username, full_name, added_by, is_active, created_at) SELECT user_id, username, full_name, added_by, is_active, created_at FROM admins WHERE is_active = 1")
        
        conn.commit()
        conn.close()
        
        print("Enhanced database migration completed successfully")
        return True
        
    except Exception as e:
        print(f"Error running enhanced migration: {e}")
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "knowledge.db"
    run_enhanced_migration(db_path)
