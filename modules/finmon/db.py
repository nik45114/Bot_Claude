#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Database - SQLite operations for Financial Monitoring
"""

import sqlite3
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from .models import Club, Shift, CashBalance

logger = logging.getLogger(__name__)


class FinMonDB:
    """Класс для работы с базой данных FinMon"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация базы данных"""
        try:
            with open('migrations/finmon_001_init.sql', 'r') as f:
                sql = f.read()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.executescript(sql)
            conn.commit()
            conn.close()
            logger.info("✅ FinMon database initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize FinMon database: {e}")
    
    def get_clubs(self) -> List[Dict[str, Any]]:
        """Получить список всех клубов"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, type, created_at
                FROM finmon_clubs
                ORDER BY name, type
            ''')
            
            clubs = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return clubs
        except Exception as e:
            logger.error(f"❌ Error getting clubs: {e}")
            return []
    
    def get_club_display_name(self, club_id: int) -> str:
        """Получить читаемое название клуба"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT name, type FROM finmon_clubs WHERE id = ?', (club_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                name, club_type = row
                type_label = "офиц" if club_type == "official" else "коробка"
                return f"{name} {type_label}"
            return "Unknown"
        except Exception as e:
            logger.error(f"❌ Error getting club name: {e}")
            return "Unknown"
    
    def save_shift(self, shift: Shift) -> Optional[int]:
        """Сохранить смену"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO finmon_shifts (
                    club_id, shift_date, shift_time, admin_tg_id, admin_username,
                    fact_cash, fact_card, qr, card2,
                    safe_cash_end, box_cash_end, goods_cash,
                    compensations, salary_payouts, other_expenses,
                    joysticks_total, joysticks_in_repair, joysticks_need_repair, games_count,
                    toilet_paper, paper_towels, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                shift.club_id, shift.shift_date, shift.shift_time, shift.admin_tg_id, shift.admin_username,
                shift.fact_cash, shift.fact_card, shift.qr, shift.card2,
                shift.safe_cash_end, shift.box_cash_end, shift.goods_cash,
                shift.compensations, shift.salary_payouts, shift.other_expenses,
                shift.joysticks_total, shift.joysticks_in_repair, shift.joysticks_need_repair, shift.games_count,
                shift.toilet_paper, shift.paper_towels, shift.notes
            ))
            
            shift_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Shift saved: ID={shift_id}")
            return shift_id
        except Exception as e:
            logger.error(f"❌ Error saving shift: {e}")
            return None
    
    def update_cash_balance(self, club_id: int, cash_type: str, delta: float) -> bool:
        """Обновить баланс кассы"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE finmon_cashes
                SET balance = balance + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE club_id = ? AND cash_type = ?
            ''', (delta, club_id, cash_type))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Cash balance updated: club_id={club_id}, type={cash_type}, delta={delta}")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating cash balance: {e}")
            return False
    
    def get_balances(self) -> List[Dict[str, Any]]:
        """Получить все балансы касс"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    c.id, c.club_id, c.cash_type, c.balance, c.updated_at,
                    cl.name as club_name
                FROM finmon_cashes c
                JOIN finmon_clubs cl ON c.club_id = cl.id
                ORDER BY cl.name, c.cash_type
            ''')
            
            balances = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return balances
        except Exception as e:
            logger.error(f"❌ Error getting balances: {e}")
            return []
    
    def get_shifts(self, limit: int = 10, admin_id: Optional[int] = None, owner_ids: List[int] = None) -> List[Dict[str, Any]]:
        """Получить последние смены"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Владельцы видят все смены, админы - только свои
            if owner_ids and admin_id in owner_ids:
                cursor.execute('''
                    SELECT 
                        s.*,
                        cl.name as club_name,
                        cl.type as club_type
                    FROM finmon_shifts s
                    JOIN finmon_clubs cl ON s.club_id = cl.id
                    ORDER BY s.shift_date DESC, s.shift_time DESC, s.created_at DESC
                    LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT 
                        s.*,
                        cl.name as club_name,
                        cl.type as club_type
                    FROM finmon_shifts s
                    JOIN finmon_clubs cl ON s.club_id = cl.id
                    WHERE s.admin_tg_id = ?
                    ORDER BY s.shift_date DESC, s.shift_time DESC, s.created_at DESC
                    LIMIT ?
                ''', (admin_id, limit))
            
            shifts = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return shifts
        except Exception as e:
            logger.error(f"❌ Error getting shifts: {e}")
            return []
    
    def get_summary(self, period: str = 'today') -> Dict[str, Any]:
        """
        Получить сводку по доходам/расходам за период
        
        Args:
            period: 'today', 'week', 'month', 'all'
        
        Returns:
            Словарь с данными сводки
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Определить фильтр по дате
            if period == 'today':
                date_filter = "date(s.shift_date) = date('now')"
            elif period == 'week':
                date_filter = "date(s.shift_date) >= date('now', '-7 days')"
            elif period == 'month':
                date_filter = "date(s.shift_date) >= date('now', '-30 days')"
            else:  # all
                date_filter = "1=1"
            
            # Получить данные по каждому клубу
            query = f'''
                SELECT 
                    cl.name,
                    cl.type,
                    COUNT(s.id) as shift_count,
                    SUM(s.fact_cash) as total_cash,
                    SUM(s.fact_card) as total_card,
                    SUM(s.qr) as total_qr,
                    SUM(s.card2) as total_card2,
                    SUM(s.compensations) as total_compensations,
                    SUM(s.salary_payouts) as total_salary,
                    SUM(s.other_expenses) as total_other_expenses
                FROM finmon_shifts s
                JOIN finmon_clubs cl ON s.club_id = cl.id
                WHERE {date_filter}
                GROUP BY cl.name, cl.type
                ORDER BY cl.name, cl.type
            '''
            
            cursor.execute(query)
            club_rows = cursor.fetchall()
            
            # Получить общую сводку
            total_query = f'''
                SELECT 
                    COUNT(s.id) as shift_count,
                    SUM(s.fact_cash) as total_cash,
                    SUM(s.fact_card) as total_card,
                    SUM(s.qr) as total_qr,
                    SUM(s.card2) as total_card2,
                    SUM(s.compensations) as total_compensations,
                    SUM(s.salary_payouts) as total_salary,
                    SUM(s.other_expenses) as total_other_expenses
                FROM finmon_shifts s
                WHERE {date_filter}
            '''
            
            cursor.execute(total_query)
            total_row = cursor.fetchone()
            
            conn.close()
            
            # Форматирование результата
            clubs = {}
            for row in club_rows:
                club_display = f"{row['name']} {'офиц' if row['type'] == 'official' else 'коробка'}"
                clubs[club_display] = {
                    'shift_count': row['shift_count'] or 0,
                    'total_cash': row['total_cash'] or 0,
                    'total_card': row['total_card'] or 0,
                    'total_qr': row['total_qr'] or 0,
                    'total_card2': row['total_card2'] or 0,
                    'total_compensations': row['total_compensations'] or 0,
                    'total_salary': row['total_salary'] or 0,
                    'total_other_expenses': row['total_other_expenses'] or 0,
                }
            
            total = {
                'shift_count': total_row['shift_count'] or 0,
                'total_cash': total_row['total_cash'] or 0,
                'total_card': total_row['total_card'] or 0,
                'total_qr': total_row['total_qr'] or 0,
                'total_card2': total_row['total_card2'] or 0,
                'total_compensations': total_row['total_compensations'] or 0,
                'total_salary': total_row['total_salary'] or 0,
                'total_other_expenses': total_row['total_other_expenses'] or 0,
            }
            
            return {
                'clubs': clubs,
                'total': total
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting summary: {e}")
            return {'clubs': {}, 'total': {}}
