#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cash Manager - Финансовый мониторинг касс
Управление 4 кассами: 2 официальные + 2 коробки
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CashManager:
    """Менеджер финансового мониторинга касс"""
    
    def __init__(self, db_path: str = 'knowledge.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица движения наличности
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cash_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club TEXT NOT NULL,
                cash_type TEXT NOT NULL,
                amount REAL NOT NULL,
                operation TEXT NOT NULL,
                description TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER NOT NULL
            )
        ''')
        
        # Таблица балансов касс
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cash_balances (
                club TEXT NOT NULL,
                cash_type TEXT NOT NULL,
                balance REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (club, cash_type)
            )
        ''')
        
        # Инициализируем балансы для всех касс если их нет
        clubs = ['rio', 'michurinskaya']
        cash_types = ['official', 'box']
        
        for club in clubs:
            for cash_type in cash_types:
                cursor.execute('''
                    INSERT OR IGNORE INTO cash_balances (club, cash_type, balance)
                    VALUES (?, ?, 0)
                ''', (club, cash_type))
        
        conn.commit()
        conn.close()
        logger.info("✅ Cash Manager database initialized")
    
    def add_movement(self, club: str, cash_type: str, amount: float, 
                    operation: str, description: str = "", category: str = "",
                    created_by: int = 0) -> bool:
        """
        Добавить движение денег
        
        Args:
            club: 'rio' или 'michurinskaya'
            cash_type: 'official' или 'box'
            amount: сумма (положительная)
            operation: 'income' или 'expense'
            description: описание операции
            category: категория (зарплата, закупка, инкассация и т.д.)
            created_by: ID пользователя
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Добавляем запись о движении
            cursor.execute('''
                INSERT INTO cash_movements 
                (club, cash_type, amount, operation, description, category, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (club, cash_type, abs(amount), operation, description, category, created_by))
            
            # Обновляем баланс
            if operation == 'income':
                cursor.execute('''
                    UPDATE cash_balances 
                    SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE club = ? AND cash_type = ?
                ''', (abs(amount), club, cash_type))
            else:  # expense
                cursor.execute('''
                    UPDATE cash_balances 
                    SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP
                    WHERE club = ? AND cash_type = ?
                ''', (abs(amount), club, cash_type))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Cash movement added: {club}/{cash_type} {operation} {amount}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding cash movement: {e}")
            return False
    
    def get_balance(self, club: str, cash_type: str) -> float:
        """Получить текущий баланс кассы"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT balance FROM cash_balances
                WHERE club = ? AND cash_type = ?
            ''', (club, cash_type))
            
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else 0.0
            
        except Exception as e:
            logger.error(f"❌ Error getting balance: {e}")
            return 0.0
    
    def get_all_balances(self) -> Dict:
        """Получить балансы всех касс"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT club, cash_type, balance FROM cash_balances')
            
            balances = {}
            for row in cursor.fetchall():
                club, cash_type, balance = row
                if club not in balances:
                    balances[club] = {}
                balances[club][cash_type] = balance
            
            conn.close()
            return balances
            
        except Exception as e:
            logger.error(f"❌ Error getting all balances: {e}")
            return {}
    
    def get_movements(self, club: str = None, cash_type: str = None, 
                     limit: int = 50) -> List[Dict]:
        """Получить историю движений"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM cash_movements WHERE 1=1'
            params = []
            
            if club:
                query += ' AND club = ?'
                params.append(club)
            
            if cash_type:
                query += ' AND cash_type = ?'
                params.append(cash_type)
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            
            movements = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return movements
            
        except Exception as e:
            logger.error(f"❌ Error getting movements: {e}")
            return []
    
    def get_monthly_summary(self, club: str, year: int, month: int) -> Dict:
        """Получить итоги за месяц"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем суммы по официальным и коробкам отдельно
            cursor.execute('''
                SELECT 
                    cash_type,
                    operation,
                    SUM(amount) as total
                FROM cash_movements
                WHERE club = ?
                AND strftime('%Y', created_at) = ?
                AND strftime('%m', created_at) = ?
                GROUP BY cash_type, operation
            ''', (club, str(year), str(month).zfill(2)))
            
            summary = {
                'official': {'income': 0, 'expense': 0, 'net': 0},
                'box': {'income': 0, 'expense': 0, 'net': 0},
                'total': {'income': 0, 'expense': 0, 'net': 0}
            }
            
            for row in cursor.fetchall():
                cash_type, operation, total = row
                summary[cash_type][operation] = total
                summary['total'][operation] += total
            
            # Вычисляем чистый доход
            for cash_type in ['official', 'box', 'total']:
                summary[cash_type]['net'] = (
                    summary[cash_type]['income'] - summary[cash_type]['expense']
                )
            
            # Получаем разбивку по категориям расходов
            cursor.execute('''
                SELECT category, SUM(amount) as total
                FROM cash_movements
                WHERE club = ?
                AND strftime('%Y', created_at) = ?
                AND strftime('%m', created_at) = ?
                AND operation = 'expense'
                AND category != ''
                GROUP BY category
            ''', (club, str(year), str(month).zfill(2)))
            
            summary['expenses_by_category'] = {}
            for row in cursor.fetchall():
                category, total = row
                summary['expenses_by_category'][category] = total
            
            conn.close()
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error getting monthly summary: {e}")
            return {}
    
    def format_balance_report(self) -> str:
        """Форматирование отчёта по балансам"""
        balances = self.get_all_balances()
        
        text = "💰 ТЕКУЩИЕ БАЛАНСЫ КАСС\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        club_names = {
            'rio': '🏢 Рио',
            'michurinskaya': '🏢 Мичуринская/Север'
        }
        
        cash_type_names = {
            'official': '✅ Официальная',
            'box': '📦 Коробка'
        }
        
        total_all = 0
        
        for club, club_name in club_names.items():
            text += f"{club_name}\n"
            club_total = 0
            
            for cash_type, type_name in cash_type_names.items():
                balance = balances.get(club, {}).get(cash_type, 0)
                text += f"  {type_name}: {balance:,.0f} ₽\n"
                club_total += balance
            
            text += f"  💵 Итого: {club_total:,.0f} ₽\n\n"
            total_all += club_total
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💎 ВСЕГО: {total_all:,.0f} ₽"
        
        return text
    
    def format_movements_report(self, movements: List[Dict]) -> str:
        """Форматирование отчёта по движениям"""
        if not movements:
            return "📭 Нет движений денег"
        
        text = "📊 ИСТОРИЯ ДВИЖЕНИЙ\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        club_names = {
            'rio': 'Рио',
            'michurinskaya': 'Мичуринская'
        }
        
        cash_type_names = {
            'official': 'Офиц.',
            'box': 'Короб.'
        }
        
        for mov in movements[:20]:  # Показываем последние 20
            operation = "➕" if mov['operation'] == 'income' else "➖"
            club = club_names.get(mov['club'], mov['club'])
            cash_type = cash_type_names.get(mov['cash_type'], mov['cash_type'])
            amount = mov['amount']
            
            date_str = mov['created_at'][:16]  # YYYY-MM-DD HH:MM
            
            text += f"{operation} {amount:,.0f} ₽ | {club}/{cash_type}\n"
            if mov['description']:
                text += f"   {mov['description']}\n"
            if mov['category']:
                text += f"   🏷 {mov['category']}\n"
            text += f"   📅 {date_str}\n\n"
        
        return text
    
    def format_monthly_summary(self, club: str, year: int, month: int) -> str:
        """Форматирование месячного отчёта"""
        summary = self.get_monthly_summary(club, year, month)
        
        if not summary:
            return "❌ Нет данных за этот месяц"
        
        club_names = {
            'rio': 'Рио',
            'michurinskaya': 'Мичуринская/Север'
        }
        
        month_names = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        
        text = f"📈 ИТОГИ ЗА {month_names[month].upper()} {year}\n"
        text += f"🏢 {club_names.get(club, club)}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "✅ ОФИЦИАЛЬНАЯ КАССА\n"
        text += f"   ➕ Приход: {summary['official']['income']:,.0f} ₽\n"
        text += f"   ➖ Расход: {summary['official']['expense']:,.0f} ₽\n"
        text += f"   💰 Чистый: {summary['official']['net']:,.0f} ₽\n\n"
        
        text += "📦 КОРОБКА\n"
        text += f"   ➕ Приход: {summary['box']['income']:,.0f} ₽\n"
        text += f"   ➖ Расход: {summary['box']['expense']:,.0f} ₽\n"
        text += f"   💰 Чистый: {summary['box']['net']:,.0f} ₽\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "💎 ИТОГО\n"
        text += f"   ➕ Приход: {summary['total']['income']:,.0f} ₽\n"
        text += f"   ➖ Расход: {summary['total']['expense']:,.0f} ₽\n"
        text += f"   💰 Чистый: {summary['total']['net']:,.0f} ₽\n"
        
        if summary.get('expenses_by_category'):
            text += "\n📊 РАСХОДЫ ПО КАТЕГОРИЯМ\n"
            for category, amount in summary['expenses_by_category'].items():
                text += f"   • {category}: {amount:,.0f} ₽\n"
        
        return text
