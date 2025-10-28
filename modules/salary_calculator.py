#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Salary Calculator - Расчет зарплат на основе отработанных смен
"""

import sqlite3
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple
from calendar import monthrange

logger = logging.getLogger(__name__)


class SalaryCalculator:
    """Calculator for admin salaries based on worked shifts"""
    
    # Default tax rates by employment type
    TAX_RATES = {
        'self_employed': 6.0,   # 6% - Самозанятые
        'staff': 30.0,          # 30% - Штат
        'gpc': 15.0             # 15% - ГПХ
    }
    
    def __init__(self, db_path: str, shift_manager=None):
        self.db_path = db_path
        self.shift_manager = shift_manager
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_advance_period(self, month: int = None, year: int = None) -> Tuple[date, date]:
        """
        Returns (start, end) for advance period (1-15 of month)
        
        Args:
            month: Month number (1-12), defaults to current month
            year: Year, defaults to current year
        
        Returns:
            Tuple of (start_date, end_date)
        """
        now = date.today()
        target_month = month or now.month
        target_year = year or now.year
        
        start_date = date(target_year, target_month, 1)
        end_date = date(target_year, target_month, 15)
        
        return start_date, end_date
    
    def get_salary_period(self, month: int = None, year: int = None) -> Tuple[date, date]:
        """
        Returns (start, end) for salary period (16-end of month)
        
        Args:
            month: Month number (1-12), defaults to current month
            year: Year, defaults to current year
        
        Returns:
            Tuple of (start_date, end_date)
        """
        now = date.today()
        target_month = month or now.month
        target_year = year or now.year
        
        start_date = date(target_year, target_month, 16)
        # Get last day of month
        last_day = monthrange(target_year, target_month)[1]
        end_date = date(target_year, target_month, last_day)
        
        return start_date, end_date
    
    def get_worked_shifts(self, admin_id: int, period_start: date, period_end: date) -> List[Dict]:
        """
        Get all shifts worked by admin in period from active_shifts table
        
        Args:
            admin_id: Admin user ID
            period_start: Start date of period
            period_end: End date of period
        
        Returns:
            List of shift dictionaries
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, admin_id, club, shift_type, opened_at, confirmed_by, status
                FROM active_shifts 
                WHERE admin_id = ? 
                AND DATE(opened_at) BETWEEN ? AND ?
                AND status = 'closed'
                ORDER BY opened_at
            ''', (admin_id, period_start, period_end))
            
            rows = cursor.fetchall()
            conn.close()
            
            shifts = []
            for row in rows:
                shifts.append({
                    'id': row[0],
                    'admin_id': row[1],
                    'club': row[2],
                    'shift_type': row[3],
                    'opened_at': row[4],
                    'confirmed_by': row[5],
                    'status': row[6]
                })
            
            logger.info(f"Found {len(shifts)} shifts for admin {admin_id} in period {period_start} - {period_end}")
            return shifts
            
        except Exception as e:
            logger.error(f"Failed to get worked shifts: {e}")
            return []
    
    def get_cash_withdrawals(self, admin_id: int, period_start: date, period_end: date) -> float:
        """
        Get total cash taken during shifts in period
        
        Args:
            admin_id: Admin user ID
            period_start: Start date of period
            period_end: End date of period
        
        Returns:
            Total amount taken from register
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT SUM(scw.amount)
                FROM shift_cash_withdrawals scw
                JOIN active_shifts s ON scw.shift_id = s.id
                WHERE scw.admin_id = ? 
                AND DATE(s.opened_at) BETWEEN ? AND ?
            ''', (admin_id, period_start, period_end))
            
            result = cursor.fetchone()
            conn.close()
            
            total = result[0] if result[0] else 0.0
            logger.info(f"Total cash withdrawals for admin {admin_id}: {total}")
            return total
            
        except Exception as e:
            logger.error(f"Failed to get cash withdrawals: {e}")
            return 0.0
    
    def get_admin_salary_settings(self, admin_id: int) -> Dict:
        """
        Get admin salary settings from database
        
        Args:
            admin_id: Admin user ID
        
        Returns:
            Dictionary with employment_type, salary_per_shift, tax_rate
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT employment_type, salary_per_shift, tax_rate
                FROM admins 
                WHERE user_id = ?
            ''', (admin_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                employment_type = row[0] or 'self_employed'
                salary_per_shift = row[1] or 0.0
                custom_tax_rate = row[2] or 0.0
                
                # Use custom tax rate if set, otherwise use default
                tax_rate = custom_tax_rate if custom_tax_rate > 0 else self.TAX_RATES.get(employment_type, 6.0)
                
                return {
                    'employment_type': employment_type,
                    'salary_per_shift': salary_per_shift,
                    'tax_rate': tax_rate,
                    'custom_tax_rate': custom_tax_rate
                }
            else:
                logger.warning(f"Admin {admin_id} not found in database")
                return {
                    'employment_type': 'self_employed',
                    'salary_per_shift': 0.0,
                    'tax_rate': 6.0,
                    'custom_tax_rate': 0.0
                }
                
        except Exception as e:
            logger.error(f"Failed to get admin salary settings: {e}")
            return {
                'employment_type': 'self_employed',
                'salary_per_shift': 0.0,
                'tax_rate': 6.0,
                'custom_tax_rate': 0.0
            }
    
    def calculate_salary(self, admin_id: int, period_start: date, period_end: date) -> Dict:
        """
        Calculate salary for period
        
        Args:
            admin_id: Admin user ID
            period_start: Start date of period
            period_end: End date of period
        
        Returns:
            Dictionary with calculation results:
            {
                'shifts': List[Dict],  # all shifts
                'total_shifts': int,
                'gross_amount': float,
                'tax_rate': float,
                'tax_amount': float,
                'net_amount': float,
                'cash_taken': float,
                'amount_due': float,
                'employment_type': str,
                'salary_per_shift': float
            }
        """
        try:
            # Get admin settings
            settings = self.get_admin_salary_settings(admin_id)
            
            # Get worked shifts
            shifts = self.get_worked_shifts(admin_id, period_start, period_end)
            
            # Get cash withdrawals
            cash_taken = self.get_cash_withdrawals(admin_id, period_start, period_end)
            
            # Calculate amounts
            total_shifts = len(shifts)
            salary_per_shift = settings['salary_per_shift']
            gross_amount = total_shifts * salary_per_shift
            tax_rate = settings['tax_rate']
            tax_amount = gross_amount * (tax_rate / 100)
            net_amount = gross_amount - tax_amount
            amount_due = net_amount - cash_taken
            
            result = {
                'shifts': shifts,
                'total_shifts': total_shifts,
                'gross_amount': gross_amount,
                'tax_rate': tax_rate,
                'tax_amount': tax_amount,
                'net_amount': net_amount,
                'cash_taken': cash_taken,
                'amount_due': amount_due,
                'employment_type': settings['employment_type'],
                'salary_per_shift': salary_per_shift,
                'period_start': period_start,
                'period_end': period_end
            }
            
            logger.info(f"Salary calculation for admin {admin_id}: {total_shifts} shifts, {gross_amount} gross, {amount_due} due")
            return result
            
        except Exception as e:
            logger.error(f"Failed to calculate salary: {e}")
            return {
                'shifts': [],
                'total_shifts': 0,
                'gross_amount': 0.0,
                'tax_rate': 0.0,
                'tax_amount': 0.0,
                'net_amount': 0.0,
                'cash_taken': 0.0,
                'amount_due': 0.0,
                'employment_type': 'self_employed',
                'salary_per_shift': 0.0,
                'period_start': period_start,
                'period_end': period_end
            }
    
    def record_payment(self, admin_id: int, payment_type: str, period_start: date, 
                      period_end: date, calculation: Dict) -> int:
        """
        Save payment record to salary_payments table
        
        Args:
            admin_id: Admin user ID
            payment_type: 'advance' or 'salary'
            period_start: Start date of period
            period_end: End date of period
            calculation: Result from calculate_salary()
        
        Returns:
            Payment record ID
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO salary_payments (
                    admin_id, payment_type, period_start, period_end,
                    total_shifts, gross_amount, tax_amount, net_amount,
                    cash_taken, amount_due
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                admin_id, payment_type, period_start, period_end,
                calculation['total_shifts'], calculation['gross_amount'],
                calculation['tax_amount'], calculation['net_amount'],
                calculation['cash_taken'], calculation['amount_due']
            ))
            
            payment_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Recorded payment {payment_id} for admin {admin_id}")
            return payment_id
            
        except Exception as e:
            logger.error(f"Failed to record payment: {e}")
            return 0
    
    def get_payment_history(self, admin_id: int, limit: int = 10) -> List[Dict]:
        """
        Get recent payment history for admin
        
        Args:
            admin_id: Admin user ID
            limit: Maximum number of records to return
        
        Returns:
            List of payment records
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, payment_type, period_start, period_end,
                       total_shifts, gross_amount, tax_amount, net_amount,
                       cash_taken, amount_due, created_at
                FROM salary_payments 
                WHERE admin_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (admin_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            payments = []
            for row in rows:
                payments.append({
                    'id': row[0],
                    'payment_type': row[1],
                    'period_start': row[2],
                    'period_end': row[3],
                    'total_shifts': row[4],
                    'gross_amount': row[5],
                    'tax_amount': row[6],
                    'net_amount': row[7],
                    'cash_taken': row[8],
                    'amount_due': row[9],
                    'created_at': row[10]
                })
            
            return payments
            
        except Exception as e:
            logger.error(f"Failed to get payment history: {e}")
            return []
    
    def record_cash_withdrawal(self, shift_id: int, admin_id: int, amount: float, reason: str = 'salary') -> int:
        """
        Record cash withdrawal during shift
        
        Args:
            shift_id: Shift ID
            admin_id: Admin user ID
            amount: Amount withdrawn
            reason: Reason for withdrawal
        
        Returns:
            Withdrawal record ID
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO shift_cash_withdrawals (shift_id, admin_id, amount, reason)
                VALUES (?, ?, ?, ?)
            ''', (shift_id, admin_id, amount, reason))
            
            withdrawal_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Recorded cash withdrawal {withdrawal_id}: {amount} for admin {admin_id}")
            return withdrawal_id
            
        except Exception as e:
            logger.error(f"Failed to record cash withdrawal: {e}")
            return 0

