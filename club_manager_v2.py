#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Manager v2 - Улучшенная версия с аналитикой расходов
Только для владельца (owner)
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ClubManager:
    """Менеджер клубов с улучшенной системой расходов"""
    
    def __init__(self, db_path: str = 'knowledge.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица клубов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clubs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                address TEXT,
                phone TEXT,
                chat_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица смен
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                admin_name TEXT,
                shift_type TEXT NOT NULL,
                shift_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (club_id) REFERENCES clubs(id)
            )
        ''')
        
        # Таблица финансов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shift_finance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER NOT NULL,
                cash_fact INTEGER DEFAULT 0,
                cash_plan INTEGER DEFAULT 0,
                cash_safe INTEGER DEFAULT 0,
                cashless_fact INTEGER DEFAULT 0,
                qr_payment INTEGER DEFAULT 0,
                cashless_new INTEGER DEFAULT 0,
                cash_products INTEGER DEFAULT 0,
                cash_box INTEGER DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (shift_id) REFERENCES shifts(id)
            )
        ''')
        
        # Таблица оборудования
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shift_equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER NOT NULL,
                joysticks_total INTEGER DEFAULT 0,
                joysticks_repair INTEGER DEFAULT 0,
                joysticks_need_repair INTEGER DEFAULT 0,
                computers_total INTEGER DEFAULT 0,
                FOREIGN KEY (shift_id) REFERENCES shifts(id)
            )
        ''')
        
        # Таблица расходников
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shift_supplies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER NOT NULL,
                item TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (shift_id) REFERENCES shifts(id)
            )
        ''')
        
        # Таблица расходов (УЛУЧШЕННАЯ!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shift_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                amount INTEGER NOT NULL,
                category TEXT DEFAULT 'other',
                recipient TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shift_id) REFERENCES shifts(id)
            )
        ''')
        
        # Таблица проблем
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shift_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER NOT NULL,
                issue TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shift_id) REFERENCES shifts(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_club(self, name: str, address: str = "", phone: str = "", chat_id: int = None) -> bool:
        """Добавление клуба"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO clubs (name, address, phone, chat_id)
                VALUES (?, ?, ?, ?)
            ''', (name, address, phone, chat_id))
            conn.commit()
            conn.close()
            logger.info(f"✅ Клуб {name} добавлен")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления клуба: {e}")
            return False
    
    def list_clubs(self) -> List[Dict]:
        """Список клубов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, address, phone FROM clubs WHERE is_active = 1')
            clubs = []
            for row in cursor.fetchall():
                clubs.append({
                    'id': row[0],
                    'name': row[1],
                    'address': row[2],
                    'phone': row[3]
                })
            conn.close()
            return clubs
        except:
            return []
    
    def parse_report(self, text: str) -> Dict:
        """Парсинг отчёта из текста (УЛУЧШЕННЫЙ!)"""
        import re
        
        report = {
            'finance': {},
            'equipment': {},
            'supplies': [],
            'issues': [],
            'expenses': [],
            'shift_type': 'evening',
            'shift_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Тип смены и дата
        shift_match = re.search(r'(Утро|День|Вечер|Ночь)\s+(\d{1,2}\.\d{1,2})', text, re.IGNORECASE)
        if shift_match:
            shift_types = {'утро': 'morning', 'день': 'day', 'вечер': 'evening', 'ночь': 'night'}
            report['shift_type'] = shift_types.get(shift_match.group(1).lower(), 'evening')
            date_parts = shift_match.group(2).split('.')
            report['shift_date'] = f"2025-{date_parts[1].zfill(2)}-{date_parts[0].zfill(2)}"
        
        # Финансы
        cash_fact = re.search(r'[Фф]акт\s+[Нн]ал\s+(\d[\d\s,]+)', text)
        if cash_fact:
            report['finance']['cash_fact'] = int(cash_fact.group(1).replace(' ', '').replace(',', ''))
        
        cash_plan = re.search(r'[Фф]акт\s+[Нн]ал\s+\d[\d\s,]+\s*/\s*(\d[\d\s,]+)', text)
        if cash_plan:
            report['finance']['cash_plan'] = int(cash_plan.group(1).replace(' ', '').replace(',', ''))
        
        safe = re.search(r'[Нн]аличка\s+в\s+сейфе\s+(\d[\d\s,]+)', text)
        if safe:
            report['finance']['cash_safe'] = int(safe.group(1).replace(' ', '').replace(',', ''))
        
        cashless = re.search(r'[Фф]акт\s+[Бб][Нн]\s+(\d[\d\s,]+)', text)
        if cashless:
            report['finance']['cashless_fact'] = int(cashless.group(1).replace(' ', '').replace(',', ''))
        
        qr = re.search(r'QR\s+(\d[\d\s,]+)', text)
        if qr:
            report['finance']['qr_payment'] = int(qr.group(1).replace(' ', '').replace(',', ''))
        
        new_cashless = re.search(r'[Бб]езнал\s+новая\s+касса\s+(\d[\d\s,]+)', text)
        if new_cashless:
            report['finance']['cashless_new'] = int(new_cashless.group(1).replace(' ', '').replace(',', ''))
        
        products = re.search(r'[Нн]аличка\s+monster.*?(\d[\d\s,]+)', text, re.IGNORECASE)
        if products:
            report['finance']['cash_products'] = int(products.group(1).replace(' ', '').replace(',', ''))
        
        cash_box = re.search(r'[Фф]акт\s+[Нн]ал\s+в\s+коробке\s+(\d[\d\s,]+)', text)
        if cash_box:
            report['finance']['cash_box'] = int(cash_box.group(1).replace(' ', '').replace(',', ''))
        
        # Оборудование
        joysticks = re.search(r'[Кк]оличество\s+джойстиков\s+(\d+)', text)
        if joysticks:
            report['equipment']['joysticks_total'] = int(joysticks.group(1))
        
        joy_repair = re.search(r'(\d+)\s+в\s+ремонте', text)
        if joy_repair:
            report['equipment']['joysticks_repair'] = int(joy_repair.group(1))
        
        joy_need = re.search(r'(\d+)\s+требуется\s+ремонт', text)
        if joy_need:
            report['equipment']['joysticks_need_repair'] = int(joy_need.group(1))
        
        computers = re.search(r'[Ии]гр\s+(\d+)', text)
        if computers:
            report['equipment']['computers_total'] = int(computers.group(1))
        
        # Расходники
        toilet = re.search(r'[Тт]уалетка\s+(есть|нет)', text, re.IGNORECASE)
        if toilet:
            report['supplies'].append({'item': 'Туалетка', 'status': toilet.group(1)})
        
        towels = re.search(r'[Бб]умажные\s+полотенца\s+(есть|нет)', text, re.IGNORECASE)
        if towels:
            report['supplies'].append({'item': 'Бумажные полотенца', 'status': towels.group(1)})
        
        # РАСХОДЫ (УЛУЧШЕННЫЙ ПАРСИНГ!)
        # Варианты:
        # 1. "- 4500 вика зп"
        # 2. "( - 4500 вика зп)"
        # 3. "- 4500 вика, - 3000 ваня зп"
        # 4. "зп вика 4500"
        # 5. "инкассация 10000"
        
        expense_patterns = [
            # "- 4500 вика зп" или "- 4500 вика"
            (r'-\s*(\d[\d\s,]+)\s+([^,\n-]+?)(?:,|\n|$)', 'standard'),
            # "( - 4500 вика зп)"
            (r'\(\s*-\s*(\d[\d\s,]+)\s+([^)]+)\)', 'parentheses'),
            # "зп вика 4500" или "зарплата вика 4500"
            (r'(зп|зарплата|аванс)\s+([^\d]+?)\s+(\d[\d\s,]+)', 'salary_first'),
            # "закупка 1500 monster"
            (r'(закупка|товар)\s+(\d[\d\s,]+)\s+(.+?)(?:\n|$)', 'purchase_first'),
            # "инкассация 10000"
            (r'(инкассаци[яи]|сдача|банк|изъят[иое])\s+(\d[\d\s,]+)', 'collection_first'),
        ]
        
        for pattern, pattern_type in expense_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    if pattern_type in ['standard', 'parentheses']:
                        amount = int(match.group(1).replace(' ', '').replace(',', ''))
                        description = match.group(2).strip()
                        recipient = None
                        
                        # Пытаемся выделить получателя из описания
                        # "вика зп" -> recipient="вика", description="зп"
                        parts = description.split()
                        if len(parts) >= 2 and any(word in parts[-1].lower() for word in ['зп', 'зарплата', 'аванс']):
                            recipient = ' '.join(parts[:-1])
                            description = parts[-1]
                        elif len(parts) >= 2:
                            recipient = parts[0]
                            description = ' '.join(parts[1:])
                        
                    elif pattern_type == 'salary_first':
                        description = match.group(1)  # зп/зарплата
                        recipient = match.group(2).strip()
                        amount = int(match.group(3).replace(' ', '').replace(',', ''))
                        
                    elif pattern_type == 'purchase_first':
                        description = match.group(1) + ' ' + match.group(3).strip()  # закупка + товар
                        recipient = None
                        amount = int(match.group(2).replace(' ', '').replace(',', ''))
                        
                    elif pattern_type == 'collection_first':
                        description = match.group(1)  # инкассация
                        recipient = None
                        amount = int(match.group(2).replace(' ', '').replace(',', ''))
                    
                    # Определяем категорию
                    category = self._categorize_expense(description, recipient)
                    
                    # Проверяем, не дубликат ли это
                    is_duplicate = any(
                        e['amount'] == amount and e['description'] == description
                        for e in report['expenses']
                    )
                    
                    if not is_duplicate:
                        report['expenses'].append({
                            'amount': amount,
                            'description': description,
                            'category': category,
                            'recipient': recipient
                        })
                
                except (ValueError, IndexError) as e:
                    logger.warning(f"Ошибка парсинга расхода: {e}")
                    continue
        
        return report
    
    def _categorize_expense(self, description: str, recipient: str = None) -> str:
        """Определение категории расхода"""
        desc_lower = description.lower()
        
        # Зарплата
        if any(word in desc_lower for word in ['зп', 'зарплата', 'аванс', 'выплата']):
            return 'salary'
        
        # Закупка
        if any(word in desc_lower for word in ['закупка', 'товар', 'monster', 'red bull', 'покупка', 'снеки']):
            return 'purchase'
        
        # Инкассация/изъятие
        if any(word in desc_lower for word in ['инкассаци', 'сдача', 'банк', 'изъят', 'вывод']):
            return 'collection'
        
        # Ремонт
        if any(word in desc_lower for word in ['ремонт', 'починка', 'запчасти']):
            return 'repair'
        
        # Коммунальные
        if any(word in desc_lower for word in ['свет', 'вода', 'интернет', 'аренда', 'коммунал']):
            return 'utility'
        
        return 'other'
    
    def save_shift_report(self, club_id: int, admin_id: int, admin_name: str, report: Dict) -> int:
        """Сохранение отчёта смены"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Создаём смену
            cursor.execute('''
                INSERT INTO shifts (club_id, admin_id, admin_name, shift_type, shift_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (club_id, admin_id, admin_name, report['shift_type'], report['shift_date']))
            
            shift_id = cursor.lastrowid
            
            # Финансы
            if report.get('finance'):
                f = report['finance']
                cursor.execute('''
                    INSERT INTO shift_finance 
                    (shift_id, cash_fact, cash_plan, cash_safe, cashless_fact, qr_payment, 
                     cashless_new, cash_products, cash_box)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (shift_id, f.get('cash_fact', 0), f.get('cash_plan', 0), f.get('cash_safe', 0),
                      f.get('cashless_fact', 0), f.get('qr_payment', 0), f.get('cashless_new', 0),
                      f.get('cash_products', 0), f.get('cash_box', 0)))
            
            # Оборудование
            if report.get('equipment'):
                e = report['equipment']
                cursor.execute('''
                    INSERT INTO shift_equipment 
                    (shift_id, joysticks_total, joysticks_repair, joysticks_need_repair, computers_total)
                    VALUES (?, ?, ?, ?, ?)
                ''', (shift_id, e.get('joysticks_total', 0), e.get('joysticks_repair', 0),
                      e.get('joysticks_need_repair', 0), e.get('computers_total', 0)))
            
            # Расходники
            for supply in report.get('supplies', []):
                cursor.execute('''
                    INSERT INTO shift_supplies (shift_id, item, status)
                    VALUES (?, ?, ?)
                ''', (shift_id, supply['item'], supply['status']))
            
            # Расходы
            for expense in report.get('expenses', []):
                cursor.execute('''
                    INSERT INTO shift_expenses (shift_id, description, amount, category, recipient)
                    VALUES (?, ?, ?, ?, ?)
                ''', (shift_id, expense['description'], expense['amount'], 
                      expense['category'], expense.get('recipient')))
            
            # Проблемы
            for issue in report.get('issues', []):
                cursor.execute('''
                    INSERT INTO shift_issues (shift_id, issue)
                    VALUES (?, ?)
                ''', (shift_id, issue))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Отчёт смены #{shift_id} сохранён")
            return shift_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения отчёта: {e}")
            return 0
    
    def add_expense(self, shift_id: int, description: str, amount: int, 
                   category: str = None, recipient: str = None, notes: str = None) -> bool:
        """Добавление расхода к смене"""
        try:
            if category is None:
                category = self._categorize_expense(description, recipient)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO shift_expenses (shift_id, description, amount, category, recipient, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (shift_id, description, amount, category, recipient, notes))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Расход добавлен к смене #{shift_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления расхода: {e}")
            return False
    
    def format_report(self, shift_id: int) -> str:
        """Красивое форматирование отчёта"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем данные смены
            cursor.execute('''
                SELECT s.shift_type, s.shift_date, s.admin_name, c.name
                FROM shifts s
                JOIN clubs c ON s.club_id = c.id
                WHERE s.id = ?
            ''', (shift_id,))
            
            shift = cursor.fetchone()
            if not shift:
                return "Отчёт не найден"
            
            shift_types = {'morning': '🌅 Утро', 'day': '☀️ День', 'evening': '🌆 Вечер', 'night': '🌙 Ночь'}
            shift_type_emoji = shift_types.get(shift[0], '📋')
            
            text = f"""╔═══════════════════════════════
║ {shift_type_emoji} Отчёт смены
╠═══════════════════════════════
║ � Клуб: {shift[3]}
║ 📅 Дата: {shift[1]}
║ 👤 Админ: {shift[2]}
╚═══════════════════════════════

"""
            
            # Финансы
            cursor.execute('SELECT * FROM shift_finance WHERE shift_id = ?', (shift_id,))
            finance = cursor.fetchone()
            
            if finance:
                cash_diff = finance[2] - finance[3] if finance[3] > 0 else 0
                diff_emoji = "📈" if cash_diff >= 0 else "📉"
                
                text += f"""💰 ФИНАНСЫ
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 Наличные:
   Факт:     {finance[2]:>8,} ₽
   План:     {finance[3]:>8,} ₽
   {diff_emoji} Разница: {cash_diff:>8,} ₽

   Сейф:     {finance[4]:>8,} ₽
   Коробка:  {finance[9]:>8,} ₽

💳 Безнал:
   Факт:     {finance[5]:>8,} ₽
   QR:       {finance[6]:>8,} ₽
   Новая:    {finance[7]:>8,} ₽

🛒 Товары:  {finance[8]:>8,} ₽

"""
            
            # Оборудование
            cursor.execute('SELECT * FROM shift_equipment WHERE shift_id = ?', (shift_id,))
            equipment = cursor.fetchone()
            
            if equipment:
                joy_working = equipment[2] - equipment[3] - equipment[4]
                joy_percent = (joy_working / equipment[2] * 100) if equipment[2] > 0 else 0
                
                text += f"""🎮 ОБОРУДОВАНИЕ
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🕹 Джойстики:
   Всего:        {equipment[2]:>3}
   ✅ Работают:  {joy_working:>3} ({joy_percent:.0f}%)
   🔧 В ремонте: {equipment[3]:>3}
   ⚠️ Требует:   {equipment[4]:>3}

💻 Компьютеры:   {equipment[5]:>3}

"""
            
            # Расходники
            cursor.execute('SELECT item, status FROM shift_supplies WHERE shift_id = ?', (shift_id,))
            supplies = cursor.fetchall()
            
            if supplies:
                text += "🧻 РАСХОДНИКИ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                for item, status in supplies:
                    emoji = "✅" if status.lower() == "есть" else "❌"
                    text += f"{emoji} {item}: {status}\n"
                text += "\n"
            
            # РАСХОДЫ (УЛУЧШЕННЫЙ ВЫВОД!)
            cursor.execute('''
                SELECT description, amount, category, recipient 
                FROM shift_expenses 
                WHERE shift_id = ? 
                ORDER BY category, id
            ''', (shift_id,))
            expenses = cursor.fetchall()
            
            if expenses:
                text += "💸 РАСХОДЫ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                
                # Группируем по категориям
                expenses_by_category = {}
                total_expenses = 0
                
                for desc, amount, category, recipient in expenses:
                    if category not in expenses_by_category:
                        expenses_by_category[category] = []
                    
                    expenses_by_category[category].append({
                        'description': desc,
                        'amount': amount,
                        'recipient': recipient
                    })
                    total_expenses += amount
                
                # Эмодзи для категорий
                category_info = {
                    'salary': ('👤 Зарплата', '👤'),
                    'purchase': ('🛒 Закупки', '🛒'),
                    'collection': ('🏦 Инкассация', '🏦'),
                    'repair': ('🔧 Ремонт', '🔧'),
                    'utility': ('🔌 Коммунальные', '🔌'),
                    'other': ('💰 Прочее', '💰')
                }
                
                # Выводим по категориям
                for category, items in expenses_by_category.items():
                    cat_name, cat_emoji = category_info.get(category, ('💰 Прочее', '💰'))
                    text += f"\n{cat_name}:\n"
                    
                    for item in items:
                        recipient_text = f" ({item['recipient']})" if item['recipient'] else ""
                        text += f"  {cat_emoji} {item['description']}{recipient_text}: {item['amount']:,} ₽\n"
                
                text += f"\n📊 Всего расходов: {total_expenses:,} ₽\n\n"
            
            # Проблемы
            cursor.execute('SELECT issue, status FROM shift_issues WHERE shift_id = ? AND status = "open"', (shift_id,))
            issues = cursor.fetchall()
            
            if issues:
                text += "⚠️ ПРОБЛЕМЫ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                for i, (issue, status) in enumerate(issues, 1):
                    text += f"{i}. {issue}\n"
                text += "\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 Отчёт #{shift_id}"
            
            conn.close()
            return text
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования: {e}")
            return "Ошибка форматирования отчёта"
    
    def get_expenses_stats(self, club_id: int = None, days: int = 30) -> Dict:
        """Статистика расходов за период"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Запрос с фильтром по клубу или для всех клубов
            if club_id:
                cursor.execute('''
                    SELECT e.category, SUM(e.amount) as total, COUNT(*) as count
                    FROM shift_expenses e
                    JOIN shifts s ON e.shift_id = s.id
                    WHERE s.club_id = ?
                    AND s.shift_date >= date('now', '-' || ? || ' days')
                    GROUP BY e.category
                    ORDER BY total DESC
                ''', (club_id, days))
            else:
                cursor.execute('''
                    SELECT e.category, SUM(e.amount) as total, COUNT(*) as count
                    FROM shift_expenses e
                    JOIN shifts s ON e.shift_id = s.id
                    WHERE s.shift_date >= date('now', '-' || ? || ' days')
                    GROUP BY e.category
                    ORDER BY total DESC
                ''', (days,))
            
            stats = {
                'by_category': {},
                'total': 0,
                'count': 0
            }
            
            for category, total, count in cursor.fetchall():
                stats['by_category'][category] = {
                    'total': total,
                    'count': count,
                    'average': total / count if count > 0 else 0
                }
                stats['total'] += total
                stats['count'] += count
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}
    
    def get_expenses_history(self, club_id: int = None, days: int = 30, 
                           category: str = None) -> List[Dict]:
        """История расходов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    e.id, e.description, e.amount, e.category, e.recipient,
                    e.created_at, s.shift_date, c.name as club_name, s.admin_name
                FROM shift_expenses e
                JOIN shifts s ON e.shift_id = s.id
                JOIN clubs c ON s.club_id = c.id
                WHERE s.shift_date >= date('now', '-' || ? || ' days')
            '''
            
            params = [days]
            
            if club_id:
                query += ' AND s.club_id = ?'
                params.append(club_id)
            
            if category:
                query += ' AND e.category = ?'
                params.append(category)
            
            query += ' ORDER BY e.created_at DESC LIMIT 50'
            
            cursor.execute(query, params)
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'id': row[0],
                    'description': row[1],
                    'amount': row[2],
                    'category': row[3],
                    'recipient': row[4],
                    'created_at': row[5],
                    'shift_date': row[6],
                    'club_name': row[7],
                    'admin_name': row[8]
                })
            
            conn.close()
            return history
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения истории: {e}")
            return []
    
    def get_club_stats(self, club_id: int, days: int = 7) -> Dict:
        """Статистика клуба за период"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем финансы за период
            cursor.execute('''
                SELECT 
                    SUM(sf.cash_fact) as total_cash,
                    SUM(sf.cashless_fact) as total_cashless,
                    SUM(sf.qr_payment) as total_qr,
                    COUNT(DISTINCT s.id) as shifts_count
                FROM shifts s
                JOIN shift_finance sf ON s.id = sf.shift_id
                WHERE s.club_id = ? 
                AND s.shift_date >= date('now', '-' || ? || ' days')
            ''', (club_id, days))
            
            stats = cursor.fetchone()
            
            # Расходы за период
            cursor.execute('''
                SELECT SUM(e.amount)
                FROM shift_expenses e
                JOIN shifts s ON e.shift_id = s.id
                WHERE s.club_id = ? 
                AND s.shift_date >= date('now', '-' || ? || ' days')
            ''', (club_id, days))
            
            total_expenses = cursor.fetchone()[0] or 0
            
            # Проблемы
            cursor.execute('''
                SELECT COUNT(*) 
                FROM shift_issues si
                JOIN shifts s ON si.shift_id = s.id
                WHERE s.club_id = ? AND si.status = 'open'
            ''', (club_id,))
            
            open_issues = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_cash': stats[0] or 0,
                'total_cashless': stats[1] or 0,
                'total_qr': stats[2] or 0,
                'shifts_count': stats[3] or 0,
                'open_issues': open_issues,
                'total_revenue': (stats[0] or 0) + (stats[1] or 0),
                'total_expenses': total_expenses,
                'net_revenue': (stats[0] or 0) + (stats[1] or 0) - total_expenses
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка статистики: {e}")
            return {}
    
    def get_issues_summary(self, club_id: int = None) -> List[Dict]:
        """Сводка по проблемам"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if club_id:
                cursor.execute('''
                    SELECT si.issue, si.created_at, c.name, s.admin_name
                    FROM shift_issues si
                    JOIN shifts s ON si.shift_id = s.id
                    JOIN clubs c ON s.club_id = c.id
                    WHERE si.status = 'open' AND s.club_id = ?
                    ORDER BY si.created_at DESC
                ''', (club_id,))
            else:
                cursor.execute('''
                    SELECT si.issue, si.created_at, c.name, s.admin_name
                    FROM shift_issues si
                    JOIN shifts s ON si.shift_id = s.id
                    JOIN clubs c ON s.club_id = c.id
                    WHERE si.status = 'open'
                    ORDER BY si.created_at DESC
                ''')
            
            issues = []
            for row in cursor.fetchall():
                issues.append({
                    'issue': row[0],
                    'created_at': row[1],
                    'club': row[2],
                    'admin': row[3]
                })
            
            conn.close()
            return issues
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения проблем: {e}")
            return []
