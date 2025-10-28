#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Payroll Manager - Расчет зарплат администраторов
"""

import sqlite3
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)


class PayrollManager:
    """Manager for salary calculations and payments"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    # ===== Salary Configuration Management =====
    
    def get_salary_config(self, employment_type: str) -> Optional[Dict]:
        """Get salary configuration for employment type"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT employment_type, rate_per_shift, tax_percentage, updated_at
                FROM salary_config 
                WHERE employment_type = ?
            ''', (employment_type,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'employment_type': row[0],
                    'rate_per_shift': row[1],
                    'tax_percentage': row[2],
                    'updated_at': row[3]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting salary config: {e}")
            return None
    
    def update_salary_config(self, employment_type: str, rate_per_shift: float, tax_percentage: float) -> bool:
        """Update salary configuration"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO salary_config 
                (employment_type, rate_per_shift, tax_percentage, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (employment_type, rate_per_shift, tax_percentage))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating salary config: {e}")
            return False
    
    def get_all_salary_configs(self) -> List[Dict]:
        """Get all salary configurations"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT employment_type, rate_per_shift, tax_percentage, updated_at
                FROM salary_config 
                ORDER BY employment_type
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            configs = []
            for row in rows:
                configs.append({
                    'employment_type': row[0],
                    'rate_per_shift': row[1],
                    'tax_percentage': row[2],
                    'updated_at': row[3]
                })
            
            return configs
        except Exception as e:
            logger.error(f"Error getting all salary configs: {e}")
            return []
    
    # ===== Admin Employment Type Management =====
    
    def set_admin_employment_type(self, admin_id: int, employment_type: str) -> bool:
        """Set employment type for admin"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE admins 
                SET employment_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (employment_type, admin_id))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error setting admin employment type: {e}")
            return False
    
    def get_admin_employment_type(self, admin_id: int) -> Optional[str]:
        """Get employment type for admin"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT employment_type 
                FROM admins 
                WHERE user_id = ?
            ''', (admin_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Error getting admin employment type: {e}")
            return None
    
    # ===== Shift Salary Calculation =====
    
    def calculate_shift_salary(self, admin_id: int, shift_id: int) -> Optional[Dict]:
        """Calculate salary for a specific shift"""
        try:
            # Get admin employment type
            employment_type = self.get_admin_employment_type(admin_id)
            if not employment_type:
                logger.warning(f"No employment type for admin {admin_id}")
                return None
            
            # Get salary config
            config = self.get_salary_config(employment_type)
            if not config:
                logger.warning(f"No salary config for employment type {employment_type}")
                return None
            
            # Get shift info
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, admin_id, club, shift_type, opened_at, closed_at, salary_taken
                FROM active_shifts 
                WHERE id = ? AND admin_id = ?
            ''', (shift_id, admin_id))
            
            shift = cursor.fetchone()
            conn.close()
            
            if not shift:
                logger.warning(f"Shift {shift_id} not found for admin {admin_id}")
                return None
            
            # Calculate salary
            rate = config['rate_per_shift']
            tax_percentage = config['tax_percentage']
            
            gross_salary = rate
            tax_amount = (rate * tax_percentage) / 100
            net_salary = rate - tax_amount
            
            return {
                'shift_id': shift[0],
                'admin_id': shift[1],
                'club': shift[2],
                'shift_type': shift[3],
                'opened_at': shift[4],
                'closed_at': shift[5],
                'salary_taken': shift[6] or 0,
                'employment_type': employment_type,
                'rate_per_shift': rate,
                'tax_percentage': tax_percentage,
                'gross_salary': gross_salary,
                'tax_amount': tax_amount,
                'net_salary': net_salary,
                'remaining_salary': net_salary - (shift[6] or 0)
            }
        except Exception as e:
            logger.error(f"Error calculating shift salary: {e}")
            return None
    
    # ===== Payment Management =====
    
    def record_salary_payment(self, admin_id: int, amount: float, payment_type: str, 
                             shift_id: Optional[int] = None, notes: str = "") -> bool:
        """Record a salary payment"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO salary_payments 
                (admin_id, shift_id, amount, payment_type, payment_date, notes)
                VALUES (?, ?, ?, ?, DATE('now'), ?)
            ''', (admin_id, shift_id, amount, payment_type, notes))
            
            # If payment is linked to a shift, update shift record
            if shift_id:
                cursor.execute('''
                    UPDATE active_shifts 
                    SET salary_taken = COALESCE(salary_taken, 0) + ?
                    WHERE id = ?
                ''', (amount, shift_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error recording salary payment: {e}")
            return False
    
    def get_admin_payments(self, admin_id: int, start_date: Optional[date] = None, 
                          end_date: Optional[date] = None) -> List[Dict]:
        """Get payments for admin in date range"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            where_clauses = ['admin_id = ?']
            params = [admin_id]
            
            if start_date:
                where_clauses.append('payment_date >= ?')
                params.append(start_date.strftime('%Y-%m-%d'))
            
            if end_date:
                where_clauses.append('payment_date <= ?')
                params.append(end_date.strftime('%Y-%m-%d'))
            
            where_sql = ' AND '.join(where_clauses)
            
            cursor.execute(f'''
                SELECT id, admin_id, shift_id, amount, payment_type, payment_date, notes, created_at
                FROM salary_payments 
                WHERE {where_sql}
                ORDER BY payment_date DESC, created_at DESC
            ''', params)
            
            rows = cursor.fetchall()
            conn.close()
            
            payments = []
            for row in rows:
                payments.append({
                    'id': row[0],
                    'admin_id': row[1],
                    'shift_id': row[2],
                    'amount': row[3],
                    'payment_type': row[4],
                    'payment_date': row[5],
                    'notes': row[6],
                    'created_at': row[7]
                })
            
            return payments
        except Exception as e:
            logger.error(f"Error getting admin payments: {e}")
            return []
    
    # ===== Period Calculations =====
    
    def calculate_period_salary(self, admin_id: int, start_date: date, end_date: date) -> Dict:
        """Calculate salary for a period (advance or salary)"""
        try:
            # Get admin employment type
            employment_type = self.get_admin_employment_type(admin_id)
            if not employment_type:
                return {'error': 'No employment type set'}
            
            # Get salary config
            config = self.get_salary_config(employment_type)
            if not config:
                return {'error': 'No salary configuration'}
            
            # Get shifts in period
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, club, shift_type, opened_at, closed_at, salary_taken
                FROM active_shifts 
                WHERE admin_id = ? 
                AND closed_at IS NOT NULL
                AND DATE(closed_at) >= ? 
                AND DATE(closed_at) <= ?
                ORDER BY closed_at
            ''', (admin_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            
            shifts = cursor.fetchall()
            conn.close()
            
            # Calculate totals
            total_shifts = len(shifts)
            total_gross = total_shifts * config['rate_per_shift']
            total_tax = (total_gross * config['tax_percentage']) / 100
            total_net = total_gross - total_tax
            total_taken = sum(shift[5] or 0 for shift in shifts)
            remaining = total_net - total_taken
            
            # Get payments in period
            payments = self.get_admin_payments(admin_id, start_date, end_date)
            
            return {
                'admin_id': admin_id,
                'employment_type': employment_type,
                'period_start': start_date,
                'period_end': end_date,
                'rate_per_shift': config['rate_per_shift'],
                'tax_percentage': config['tax_percentage'],
                'total_shifts': total_shifts,
                'total_gross': total_gross,
                'total_tax': total_tax,
                'total_net': total_net,
                'total_taken_from_cash': total_taken,
                'remaining_salary': remaining,
                'shifts': [
                    {
                        'shift_id': shift[0],
                        'club': shift[1],
                        'shift_type': shift[2],
                        'opened_at': shift[3],
                        'closed_at': shift[4],
                        'salary_taken': shift[5] or 0
                    } for shift in shifts
                ],
                'payments': payments
            }
        except Exception as e:
            logger.error(f"Error calculating period salary: {e}")
            return {'error': str(e)}
    
    def calculate_advance(self, admin_id: int, year: int, month: int) -> Dict:
        """Calculate advance for 1-15 of month"""
        start_date = date(year, month, 1)
        end_date = date(year, month, 15)
        return self.calculate_period_salary(admin_id, start_date, end_date)
    
    def calculate_salary(self, admin_id: int, year: int, month: int) -> Dict:
        """Calculate salary for 16-end of month"""
        start_date = date(year, month, 16)
        # Get last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        return self.calculate_period_salary(admin_id, start_date, end_date)
    
    # ===== Summary Statistics =====
    
    def get_payroll_summary(self, year: int, month: int) -> Dict:
        """Get payroll summary for all admins in month"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Get all active admins
            cursor.execute('''
                SELECT user_id, username, full_name, employment_type
                FROM admins 
                WHERE is_active = 1
                ORDER BY full_name
            ''')
            
            admins = cursor.fetchall()
            conn.close()
            
            summary = {
                'year': year,
                'month': month,
                'admins': [],
                'totals': {
                    'total_gross': 0,
                    'total_tax': 0,
                    'total_net': 0,
                    'total_taken': 0,
                    'total_remaining': 0
                }
            }
            
            for admin in admins:
                admin_id = admin[0]
                username = admin[1]
                full_name = admin[2]
                employment_type = admin[3] or 'self_employed'
                
                # Calculate advance (1-15)
                advance = self.calculate_advance(admin_id, year, month)
                salary = self.calculate_salary(admin_id, year, month)
                
                if 'error' not in advance and 'error' not in salary:
                    total_gross = advance['total_gross'] + salary['total_gross']
                    total_tax = advance['total_tax'] + salary['total_tax']
                    total_net = advance['total_net'] + salary['total_net']
                    total_taken = advance['total_taken_from_cash'] + salary['total_taken_from_cash']
                    remaining = advance['remaining_salary'] + salary['remaining_salary']
                    
                    admin_summary = {
                        'admin_id': admin_id,
                        'username': username,
                        'full_name': full_name,
                        'employment_type': employment_type,
                        'advance_shifts': advance['total_shifts'],
                        'salary_shifts': salary['total_shifts'],
                        'total_shifts': advance['total_shifts'] + salary['total_shifts'],
                        'gross_salary': total_gross,
                        'tax_amount': total_tax,
                        'net_salary': total_net,
                        'taken_from_cash': total_taken,
                        'remaining': remaining
                    }
                    
                    summary['admins'].append(admin_summary)
                    
                    # Add to totals
                    summary['totals']['total_gross'] += total_gross
                    summary['totals']['total_tax'] += total_tax
                    summary['totals']['total_net'] += total_net
                    summary['totals']['total_taken'] += total_taken
                    summary['totals']['total_remaining'] += remaining
            
            return summary
        except Exception as e:
            logger.error(f"Error getting payroll summary: {e}")
            return {'error': str(e)}

