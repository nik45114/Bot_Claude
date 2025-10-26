#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Database - SQLite operations for Financial Monitoring
"""

import sqlite3
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class FinMonDB:
    """Класс для работы с базой данных FinMon"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_clubs(self) -> List[Dict[str, Any]]:
        """Получить список всех клубов"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, created_at
                FROM finmon_clubs
                ORDER BY name
            ''')
            
            clubs = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return clubs
        except Exception as e:
            logger.error(f"❌ Error getting clubs: {e}")
            return []
    
    def get_club_by_id(self, club_id: int) -> Optional[Dict[str, Any]]:
        """Получить клуб по ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, name FROM finmon_clubs WHERE id = ?', (club_id,))
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error getting club: {e}")
            return None
    
    def get_club_from_chat(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Получить клуб по chat_id"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT c.id, c.name
                FROM finmon_clubs c
                JOIN finmon_chat_club_map m ON c.id = m.club_id
                WHERE m.chat_id = ?
            ''', (chat_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error getting club from chat: {e}")
            return None
    
    def get_balances(self, club_id: int) -> Optional[Dict[str, float]]:
        """Получить текущие балансы клуба"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT official, box, updated_at
                FROM finmon_balances
                WHERE club_id = ?
            ''', (club_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'official': row[0],
                    'box': row[1],
                    'updated_at': row[2]
                }
            return None
        except Exception as e:
            logger.error(f"❌ Error getting balances: {e}")
            return None
    
    def update_balances(self, club_id: int, official: float, box: float) -> bool:
        """Обновить балансы клуба"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE finmon_balances
                SET official = ?, box = ?, updated_at = CURRENT_TIMESTAMP
                WHERE club_id = ?
            ''', (official, box, club_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Updated balances for club {club_id}: official={official}, box={box}")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating balances: {e}")
            return False
    
    def save_shift(self, shift_data: Dict[str, Any]) -> Optional[int]:
        """Сохранить смену и обновить балансы"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get previous balances for delta calculation
            cursor.execute('''
                SELECT official, box
                FROM finmon_balances
                WHERE club_id = ?
            ''', (shift_data['club_id'],))
            
            prev_balances = cursor.fetchone()
            prev_official = prev_balances[0] if prev_balances else 0.0
            prev_box = prev_balances[1] if prev_balances else 0.0
            
            # Calculate deltas
            delta_official = shift_data['safe_cash_end'] - prev_official
            delta_box = shift_data['box_cash_end'] - prev_box
            
            # Insert shift
            cursor.execute('''
                INSERT INTO finmon_shifts (
                    ts, chat_id, club_id, shift_date, shift_time,
                    fact_cash, fact_card, qr, card2,
                    safe_cash_end, box_cash_end, goods_cash,
                    joysticks_total, joysticks_in_repair, joysticks_need_repair, games_count,
                    duty_name, duty_username,
                    delta_official, delta_box,
                    created_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                shift_data.get('ts', datetime.now().isoformat()),
                shift_data.get('chat_id'),
                shift_data['club_id'],
                shift_data['shift_date'],
                shift_data['shift_time'],
                shift_data.get('fact_cash', 0),
                shift_data.get('fact_card', 0),
                shift_data.get('qr', 0),
                shift_data.get('card2', 0),
                shift_data['safe_cash_end'],
                shift_data['box_cash_end'],
                shift_data.get('goods_cash', 0),
                shift_data.get('joysticks_total', 0),
                shift_data.get('joysticks_in_repair', 0),
                shift_data.get('joysticks_need_repair', 0),
                shift_data.get('games_count', 0),
                shift_data.get('duty_name'),
                shift_data.get('duty_username'),
                delta_official,
                delta_box,
                shift_data.get('created_by'),
                shift_data.get('notes')
            ))
            
            shift_id = cursor.lastrowid
            
            # Insert movement record
            cursor.execute('''
                INSERT INTO finmon_movements (
                    ts, club_id, shift_id, delta_official, delta_box
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                shift_data['club_id'],
                shift_id,
                delta_official,
                delta_box
            ))
            
            # Update balances
            cursor.execute('''
                UPDATE finmon_balances
                SET official = ?, box = ?, updated_at = CURRENT_TIMESTAMP
                WHERE club_id = ?
            ''', (shift_data['safe_cash_end'], shift_data['box_cash_end'], shift_data['club_id']))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Saved shift {shift_id} for club {shift_data['club_id']}")
            logger.info(f"   Deltas: official={delta_official:+.2f}, box={delta_box:+.2f}")
            
            return shift_id
        except Exception as e:
            logger.error(f"❌ Error saving shift: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_shifts(self, club_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить список смен"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if club_id:
                cursor.execute('''
                    SELECT s.*, c.name as club_name
                    FROM finmon_shifts s
                    JOIN finmon_clubs c ON s.club_id = c.id
                    WHERE s.club_id = ?
                    ORDER BY s.ts DESC
                    LIMIT ?
                ''', (club_id, limit))
            else:
                cursor.execute('''
                    SELECT s.*, c.name as club_name
                    FROM finmon_shifts s
                    JOIN finmon_clubs c ON s.club_id = c.id
                    ORDER BY s.ts DESC
                    LIMIT ?
                ''', (limit,))
            
            shifts = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return shifts
        except Exception as e:
            logger.error(f"❌ Error getting shifts: {e}")
            return []
    
    def get_movements(self, club_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить движения по балансам"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if club_id:
                cursor.execute('''
                    SELECT m.*, c.name as club_name
                    FROM finmon_movements m
                    JOIN finmon_clubs c ON m.club_id = c.id
                    WHERE m.club_id = ?
                    ORDER BY m.ts DESC
                    LIMIT ?
                ''', (club_id, limit))
            else:
                cursor.execute('''
                    SELECT m.*, c.name as club_name
                    FROM finmon_movements m
                    JOIN finmon_clubs c ON m.club_id = c.id
                    ORDER BY m.ts DESC
                    LIMIT ?
                ''', (limit,))
            
            movements = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return movements
        except Exception as e:
            logger.error(f"❌ Error getting movements: {e}")
            return []


__all__ = ['FinMonDB']
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
    
    # ===== Chat-Club Mapping Methods =====
    
    def get_club_for_chat(self, chat_id: int) -> Optional[int]:
        """Получить club_id для чата"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT club_id FROM finmon_chat_club_map WHERE chat_id = ?', (chat_id,))
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else None
        except Exception as e:
            logger.error(f"❌ Error getting club for chat: {e}")
            return None
    
    def set_chat_club_mapping(self, chat_id: int, club_id: int) -> bool:
        """Установить маппинг чат → клуб"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO finmon_chat_club_map (chat_id, club_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (chat_id, club_id))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"❌ Error setting chat-club mapping: {e}")
            return False
    
    def delete_chat_club_mapping(self, chat_id: int) -> bool:
        """Удалить маппинг чата"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM finmon_chat_club_map WHERE chat_id = ?', (chat_id,))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting chat-club mapping: {e}")
            return False
    
    def get_all_chat_club_mappings(self) -> List[Dict[str, Any]]:
        """Получить все маппинги чат → клуб"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT m.chat_id, m.club_id, c.name, c.type, m.created_at, m.updated_at
                FROM finmon_chat_club_map m
                JOIN finmon_clubs c ON m.club_id = c.id
                ORDER BY m.created_at DESC
            ''')
            
            mappings = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return mappings
        except Exception as e:
            logger.error(f"❌ Error getting chat-club mappings: {e}")
            return []
