#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shift Manager - Управление открытыми сменами и списаниями
"""

import sqlite3
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ShiftManager:
    """Manager for active shifts, expenses, and duty schedule"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def open_shift(self, admin_id: int, club: str, shift_type: str, confirmed_by: Optional[int] = None) -> Optional[int]:
        """
        Open a new shift
        
        Args:
            admin_id: Admin user ID
            club: Club name ('rio' or 'sever')
            shift_type: 'morning' or 'evening'
            confirmed_by: User ID who confirmed (optional, can be same as admin_id)
        
        Returns:
            shift_id if successful, None otherwise
        """
        try:
            # Check if admin already has an open shift
            existing = self.get_active_shift(admin_id)
            if existing:
                logger.warning(f"Admin {admin_id} already has an open shift: {existing['id']}")
                return None
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO active_shifts (admin_id, club, shift_type, confirmed_by, status)
                VALUES (?, ?, ?, ?, 'open')
            ''', (admin_id, club, shift_type, confirmed_by))
            
            shift_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Opened shift {shift_id}: admin={admin_id}, club={club}, type={shift_type}")
            return shift_id
            
        except Exception as e:
            logger.error(f"❌ Failed to open shift: {e}")
            return None
    
    def close_shift(self, shift_id: int) -> bool:
        """
        Close an active shift
        
        Args:
            shift_id: Shift ID to close
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE active_shifts 
                SET status = 'closed'
                WHERE id = ? AND status = 'open'
            ''', (shift_id,))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                logger.info(f"✅ Closed shift {shift_id}")
                return True
            else:
                logger.warning(f"⚠️ Shift {shift_id} not found or already closed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to close shift: {e}")
            return False
    
    def get_active_shift(self, admin_id: int) -> Optional[Dict]:
        """
        Get active shift for admin
        
        Args:
            admin_id: Admin user ID
        
        Returns:
            Dict with shift data or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, admin_id, club, shift_type, opened_at, confirmed_by, status
                FROM active_shifts
                WHERE admin_id = ? AND status = 'open'
                ORDER BY opened_at DESC
                LIMIT 1
            ''', (admin_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get active shift: {e}")
            return None
    
    def get_shift_by_id(self, shift_id: int) -> Optional[Dict]:
        """Get shift by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, admin_id, club, shift_type, opened_at, confirmed_by, status
                FROM active_shifts
                WHERE id = ?
            ''', (shift_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get shift by ID: {e}")
            return None
    
    def add_expense(self, shift_id: int, cash_source: str, amount: float, reason: str) -> bool:
        """
        Add expense to active shift
        
        Args:
            shift_id: Shift ID
            cash_source: 'main' or 'box'
            amount: Amount to deduct
            reason: Reason for expense
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO shift_expenses (shift_id, cash_source, amount, reason)
                VALUES (?, ?, ?, ?)
            ''', (shift_id, cash_source, amount, reason))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Added expense to shift {shift_id}: {amount} from {cash_source} - {reason}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add expense: {e}")
            return False
    
    def get_shift_expenses(self, shift_id: int) -> List[Dict]:
        """
        Get all expenses for a shift
        
        Args:
            shift_id: Shift ID
        
        Returns:
            List of expense dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, shift_id, cash_source, amount, reason, created_at
                FROM shift_expenses
                WHERE shift_id = ?
                ORDER BY created_at ASC
            ''', (shift_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to get shift expenses: {e}")
            return []
    
    def get_expenses_summary(self, shift_id: int) -> Dict[str, float]:
        """
        Get summary of expenses by cash source
        
        Args:
            shift_id: Shift ID
        
        Returns:
            Dict with 'main' and 'box' totals
        """
        expenses = self.get_shift_expenses(shift_id)
        
        summary = {'main': 0.0, 'box': 0.0, 'total': 0.0}
        
        for exp in expenses:
            source = exp['cash_source']
            amount = exp['amount']
            if source in summary:
                summary[source] += amount
            summary['total'] += amount
        
        return summary
    
    def get_expected_duty(self, club: str, shift_type: str, duty_date: Optional[date] = None) -> Optional[Dict]:
        """
        Get expected duty admin from schedule
        
        Args:
            club: Club name
            shift_type: 'morning' or 'evening'
            duty_date: Date to check (default: today)
        
        Returns:
            Dict with duty info or None
        """
        if duty_date is None:
            duty_date = date.today()
        
        date_str = duty_date.strftime('%Y-%m-%d')
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, date, club, shift_type, admin_id, admin_name, imported_at
                FROM duty_schedule
                WHERE date = ? AND club = ? AND shift_type = ?
                LIMIT 1
            ''', (date_str, club, shift_type))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get expected duty: {e}")
            return None
    
    def add_duty_schedule(self, duty_date: date, club: str, shift_type: str, 
                         admin_id: Optional[int] = None, admin_name: Optional[str] = None) -> bool:
        """
        Add or update duty schedule entry
        
        Args:
            duty_date: Date of duty
            club: Club name
            shift_type: 'morning' or 'evening'
            admin_id: Admin user ID (optional)
            admin_name: Admin display name (optional)
        
        Returns:
            True if successful, False otherwise
        """
        date_str = duty_date.strftime('%Y-%m-%d')
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO duty_schedule 
                (date, club, shift_type, admin_id, admin_name, imported_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (date_str, club, shift_type, admin_id, admin_name))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Added duty schedule: {date_str} {club} {shift_type} - {admin_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add duty schedule: {e}")
            return False
    
    def clear_duty_schedule(self) -> bool:
        """Clear all duty schedule entries"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM duty_schedule')
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Cleared duty schedule")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to clear duty schedule: {e}")
            return False
    
    def update_duty_schedule(self, duty_date: date, club: str, shift_type: str,
                            admin_id: Optional[int] = None, admin_name: Optional[str] = None) -> bool:
        """
        Update existing duty schedule entry
        
        Args:
            duty_date: Date of duty
            club: Club name
            shift_type: 'morning' or 'evening'
            admin_id: New admin user ID
            admin_name: New admin display name
        
        Returns:
            True if successful, False otherwise
        """
        date_str = duty_date.strftime('%Y-%m-%d')
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE duty_schedule
                SET admin_id = ?, admin_name = ?, imported_at = CURRENT_TIMESTAMP
                WHERE date = ? AND club = ? AND shift_type = ?
            ''', (admin_id, admin_name, date_str, club, shift_type))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                logger.info(f"✅ Updated duty schedule: {date_str} {club} {shift_type} → {admin_name}")
                return True
            else:
                logger.warning(f"⚠️ No duty schedule entry found to update: {date_str} {club} {shift_type}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Failed to update duty schedule: {e}")
            return False
    
    def check_schedule_match(self, admin_id: int, club: str, shift_type: str, 
                            duty_date: Optional[date] = None) -> bool:
        """
        Check if admin matches the scheduled duty
        
        Args:
            admin_id: Admin user ID to check
            club: Club name
            shift_type: 'morning' or 'evening'
            duty_date: Date to check (default: today)
        
        Returns:
            True if admin matches schedule, False otherwise
        """
        duty_info = self.get_expected_duty(club, shift_type, duty_date)
        
        if not duty_info:
            # No schedule data - no match requirement
            return True
        
        expected_id = duty_info.get('admin_id')
        if not expected_id:
            # Schedule has no admin_id - no match requirement
            return True
        
        return expected_id == admin_id
    
    def remove_duty_schedule(self, duty_date: date, club: str, shift_type: str) -> bool:
        """
        Remove duty schedule entry
        
        Args:
            duty_date: Date of duty
            club: Club name
            shift_type: 'morning' or 'evening'
        
        Returns:
            True if successful, False otherwise
        """
        date_str = duty_date.strftime('%Y-%m-%d')
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM duty_schedule
                WHERE date = ? AND club = ? AND shift_type = ?
            ''', (date_str, club, shift_type))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                logger.info(f"✅ Removed duty schedule: {date_str} {club} {shift_type}")
                return True
            else:
                logger.warning(f"⚠️ No duty schedule entry found: {date_str} {club} {shift_type}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Failed to remove duty schedule: {e}")
            return False
    
    def get_week_schedule(self, start_date: Optional[date] = None, days: int = 7) -> List[Dict]:
        """
        Get schedule for a week
        
        Args:
            start_date: Start date (default: today)
            days: Number of days to fetch (default: 7)
        
        Returns:
            List of duty schedule entries
        """
        if start_date is None:
            start_date = date.today()
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            end_date = start_date + timedelta(days=days)
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT id, date, club, shift_type, admin_id, admin_name, imported_at
                FROM duty_schedule
                WHERE date >= ? AND date < ?
                ORDER BY date, club, shift_type
            ''', (start_str, end_str))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to get week schedule: {e}")
            return []

