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
