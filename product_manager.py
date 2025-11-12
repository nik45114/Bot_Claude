#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Product Manager - Система учёта товара для админов
Запись товара на админов, отчёты, управление товарами
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ProductManager:
    """Менеджер системы учёта товара"""
    
    def __init__(self, db_path: str = 'knowledge.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация таблиц"""
        try:
            logger.info(f"🔧 Initializing Product Manager database at: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Таблица товаров
            logger.info("📋 Creating products table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    cost_price REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("✅ Products table created/verified")
            
            # Таблица взятых товаров админами
            logger.info("📋 Creating admin_products table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    admin_name TEXT NOT NULL,
                    product_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    cost_price REAL NOT NULL,
                    total_debt REAL NOT NULL,
                    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settled BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            logger.info("✅ Admin_products table created/verified")
            
            conn.commit()
            
            # Verify tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
            if cursor.fetchone():
                logger.info("✅ Products table exists in database")
            else:
                logger.error("❌ Products table was not created!")
                
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_products'")
            if cursor.fetchone():
                logger.info("✅ Admin_products table exists in database")
            else:
                logger.error("❌ Admin_products table was not created!")
            
            conn.close()
            logger.info("✅ Product Manager database initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error initializing Product Manager database: {e}")
            raise
    
    def add_product(self, name: str, cost_price: float) -> bool:
        """Добавить новый товар"""
        logger.info(f"🔄 Attempting to add product: name='{name}', cost_price={cost_price}")
        
        # Validate inputs
        if not name or not name.strip():
            logger.error("❌ Product name is empty or invalid")
            return False
        
        if cost_price <= 0:
            logger.error(f"❌ Invalid cost_price: {cost_price} (must be > 0)")
            return False
        
        try:
            logger.info(f"📂 Connecting to database: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if products table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
            if not cursor.fetchone():
                logger.error("❌ Products table does not exist! Attempting to recreate...")
                self._init_db()
                # Reconnect after recreation
                conn.close()
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
            
            # Check if product already exists
            logger.info(f"🔍 Checking if product '{name}' already exists...")
            cursor.execute('SELECT id FROM products WHERE name = ?', (name,))
            existing = cursor.fetchone()
            if existing:
                logger.error(f"❌ Product '{name}' already exists with ID: {existing[0]}")
                conn.close()
                return False
            
            logger.info(f"➕ Inserting product into database...")
            cursor.execute('''
                INSERT INTO products (name, cost_price)
                VALUES (?, ?)
            ''', (name, cost_price))
            
            product_id = cursor.lastrowid
            logger.info(f"✅ Product inserted with ID: {product_id}")
            
            conn.commit()
            logger.info("✅ Transaction committed")
            
            conn.close()
            logger.info("✅ Database connection closed")
            
            logger.info(f"✅ Product added successfully: {name} - {cost_price} ₽ [ID: {product_id}]")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.error(f"❌ IntegrityError adding product '{name}': {e}")
            return False
        except sqlite3.OperationalError as e:
            logger.error(f"❌ OperationalError adding product '{name}': {e}")
            logger.error("   This may indicate a database schema issue or locked database")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error adding product '{name}': {type(e).__name__}: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False
    
    def update_product_price(self, product_id: int, new_price: float) -> bool:
        """Обновить себестоимость товара"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE products 
                SET cost_price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_price, product_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Product price updated: ID {product_id} -> {new_price} ₽")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating product price: {e}")
            return False
    
    def list_products(self) -> List[Dict]:
        """Получить список всех товаров"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM products ORDER BY name')
            
            products = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return products
            
        except Exception as e:
            logger.error(f"❌ Error listing products: {e}")
            return []
    
    def get_product(self, product_id: int) -> Optional[Dict]:
        """Получить информацию о товаре"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"❌ Error getting product: {e}")
            return None
    
    def record_admin_product(self, admin_id: int, admin_name: str, 
                           product_id: int, quantity: int) -> bool:
        """Записать товар на админа"""
        try:
            # Получаем информацию о товаре
            product = self.get_product(product_id)
            if not product:
                logger.error(f"❌ Product {product_id} not found")
                return False
            
            total_debt = product['cost_price'] * quantity
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO admin_products 
                (admin_id, admin_name, product_id, product_name, quantity, cost_price, total_debt)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (admin_id, admin_name, product_id, product['name'], 
                  quantity, product['cost_price'], total_debt))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Product recorded: {admin_name} took {quantity}x {product['name']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error recording admin product: {e}")
            return False
    
    def get_admin_debt(self, admin_id: int) -> float:
        """Получить общий долг админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT SUM(total_debt) FROM admin_products
                WHERE admin_id = ? AND settled = FALSE
            ''', (admin_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row[0] else 0.0
            
        except Exception as e:
            logger.error(f"❌ Error getting admin debt: {e}")
            return 0.0
    
    def get_admin_products(self, admin_id: int, settled: bool = False) -> List[Dict]:
        """Получить список товаров взятых админом"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM admin_products
                WHERE admin_id = ? AND settled = ?
                ORDER BY taken_at DESC
            ''', (admin_id, settled))
            
            products = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return products
            
        except Exception as e:
            logger.error(f"❌ Error getting admin products: {e}")
            return []
    
    def get_admin_nickname(self, admin_id: int) -> Optional[str]:
        """Получить никнейм админа из БД
        
        Args:
            admin_id: ID админа
            
        Returns:
            Никнейм админа или None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT admin_nickname FROM admins WHERE user_id = ?', (admin_id,))
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row and row[0] else None
            
        except Exception as e:
            logger.error(f"❌ Error getting admin nickname: {e}")
            return None
    
    def set_admin_nickname(self, admin_id: int, nickname: str) -> bool:
        """Установить никнейм для админа
        
        Args:
            admin_id: ID админа
            nickname: Никнейм для установки
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Проверяем существует ли админ
            cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (admin_id,))
            if not cursor.fetchone():
                # Создаём запись админа если её нет
                cursor.execute('''
                    INSERT INTO admins (user_id, admin_nickname, is_active)
                    VALUES (?, ?, 1)
                ''', (admin_id, nickname))
            else:
                # Обновляем никнейм
                cursor.execute('''
                    UPDATE admins 
                    SET admin_nickname = ?
                    WHERE user_id = ?
                ''', (nickname, admin_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Admin nickname set: {admin_id} -> {nickname}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting admin nickname: {e}")
            return False
    
    def get_display_name(self, admin_id: int, admin_name: str) -> str:
        """Получить отображаемое имя админа (никнейм или имя)
        
        Args:
            admin_id: ID админа
            admin_name: Имя из Telegram
            
        Returns:
            Приоритет: full_name > nickname > username > admin_name > admin_id
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Get full_name and username from admins table
            cursor.execute('SELECT full_name, username FROM admins WHERE user_id = ?', (admin_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                full_name, username = result
                # Priority: full_name > nickname > username
                if full_name and full_name.strip():
                    return full_name
                
                nickname = self.get_admin_nickname(admin_id)
                if nickname:
                    return nickname
                
                if username and username.strip():
                    return f"@{username}"
            else:
                # Not in admins table, try nickname
                nickname = self.get_admin_nickname(admin_id)
                if nickname:
                    return nickname
            
            # Fallback to admin_name or admin_id
            return admin_name if admin_name else str(admin_id)
        except Exception as e:
            logger.error(f"❌ Error getting display name: {e}")
            nickname = self.get_admin_nickname(admin_id)
            return nickname if nickname else (admin_name if admin_name else str(admin_id))
    
    def get_all_debts(self, sort_by: str = 'debt') -> Dict:
        """Получить долги всех админов с никнеймами
        
        Args:
            sort_by: 'debt' - сортировка по сумме долга (по убыванию)
                    'name' - сортировка по имени админа (по возрастанию)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Определяем порядок сортировки
            order_clause = 'total DESC' if sort_by == 'debt' else 'admin_name ASC'
            
            cursor.execute(f'''
                SELECT admin_id, admin_name, SUM(total_debt) as total
                FROM admin_products
                WHERE settled = FALSE
                GROUP BY admin_id
                ORDER BY {order_clause}
            ''')
            
            debts = {}
            for row in cursor.fetchall():
                admin_id, admin_name, total = row
                # Получаем никнейм для админа
                display_name = self.get_display_name(admin_id, admin_name)
                debts[admin_id] = {
                    'name': display_name,
                    'original_name': admin_name,
                    'total': total
                }
            
            conn.close()
            return debts
            
        except Exception as e:
            logger.error(f"❌ Error getting all debts: {e}")
            return {}
    
    def get_products_report(self, start_date: str = None, end_date: str = None, sort_by: str = 'admin') -> List[Dict]:
        """Получить отчёт по товарам за период с никнеймами админов
        
        Args:
            start_date: начальная дата периода
            end_date: конечная дата периода
            sort_by: 'admin' - сортировка по имени админа
                    'product' - сортировка по названию товара
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
                SELECT admin_id, admin_name, product_name, 
                       SUM(quantity) as total_quantity,
                       SUM(total_debt) as total_debt
                FROM admin_products
                WHERE settled = FALSE
            '''
            
            params = []
            
            if start_date:
                query += ' AND taken_at >= ?'
                params.append(start_date)
            
            if end_date:
                query += ' AND taken_at <= ?'
                params.append(end_date)
            
            # Определяем порядок сортировки
            if sort_by == 'product':
                query += ' GROUP BY product_name, admin_id ORDER BY product_name, admin_name'
            else:
                query += ' GROUP BY admin_id, product_name ORDER BY admin_name, product_name'
            
            cursor.execute(query, params)
            
            report = []
            for row in cursor.fetchall():
                admin_id = row[0]
                admin_name = row[1]
                display_name = self.get_display_name(admin_id, admin_name)
                report.append({
                    'admin_id': admin_id,
                    'admin_name': display_name,
                    'original_name': admin_name,
                    'product_name': row[2],
                    'total_quantity': row[3],
                    'total_debt': row[4]
                })
            
            conn.close()
            return report
            
        except Exception as e:
            logger.error(f"❌ Error getting products report: {e}")
            return []
    
    def get_products_summary(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Получить сводку по товарам (общее количество каждого товара за период)
        
        Args:
            start_date: начальная дата периода
            end_date: конечная дата периода
            
        Returns:
            Список словарей с информацией о каждом товаре:
            [{'product_name': 'Gorilla', 'total_quantity': 12, 'total_debt': 600}, ...]
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
                SELECT product_name, 
                       SUM(quantity) as total_quantity,
                       SUM(total_debt) as total_debt
                FROM admin_products
                WHERE settled = FALSE
            '''
            
            params = []
            
            if start_date:
                query += ' AND taken_at >= ?'
                params.append(start_date)
            
            if end_date:
                query += ' AND taken_at <= ?'
                params.append(end_date)
            
            query += ' GROUP BY product_name ORDER BY product_name'
            
            cursor.execute(query, params)
            
            summary = []
            for row in cursor.fetchall():
                summary.append({
                    'product_name': row[0],
                    'total_quantity': row[1],
                    'total_debt': row[2]
                })
            
            conn.close()
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error getting products summary: {e}")
            return []
    
    def clear_settled_products(self) -> int:
        """Удалить погашенные товары"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM admin_products WHERE settled = TRUE')
            deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Cleared {deleted} settled products")
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Error clearing settled products: {e}")
            return 0
    
    def clear_admin_debt(self, admin_id: int) -> bool:
        """Обнулить долг админа (пометить как погашенный)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE admin_products 
                SET settled = TRUE
                WHERE admin_id = ? AND settled = FALSE
            ''', (admin_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Admin {admin_id} debt cleared")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error clearing admin debt: {e}")
            return False
    
    def clear_all_debts(self) -> bool:
        """Обнулить ВСЕ долги всех админов (пометить как погашенные)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE admin_products 
                SET settled = TRUE
                WHERE settled = FALSE
            ''')
            
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"✅ All debts cleared ({affected} records)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error clearing all debts: {e}")
            return False
    
    def format_products_list(self) -> str:
        """Форматирование списка товаров"""
        products = self.list_products()
        
        if not products:
            return "📭 Нет товаров в базе"
        
        text = "📦 СПИСОК ТОВАРОВ\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for prod in products:
            text += f"🔹 {prod['name']}\n"
            text += f"   💰 Себестоимость: {prod['cost_price']:,.0f} ₽\n"
            text += f"   🆔 ID: {prod['id']}\n\n"
        
        return text
    
    def format_admin_debt_report(self, admin_id: int) -> str:
        """Форматирование отчёта по долгу админа"""
        products = self.get_admin_products(admin_id, settled=False)
        total_debt = self.get_admin_debt(admin_id)
        
        if not products:
            return "✅ Нет долгов"
        
        text = "💳 МОЙ ДОЛГ ПО ТОВАРАМ\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Группируем по товарам
        grouped = {}
        for prod in products:
            name = prod['product_name']
            if name not in grouped:
                grouped[name] = {
                    'quantity': 0,
                    'debt': 0,
                    'price': prod['cost_price']
                }
            grouped[name]['quantity'] += prod['quantity']
            grouped[name]['debt'] += prod['total_debt']
        
        for name, data in grouped.items():
            text += f"📦 {name}\n"
            text += f"   Количество: {data['quantity']} шт\n"
            text += f"   Цена: {data['price']:,.0f} ₽/шт\n"
            text += f"   Сумма: {data['debt']:,.0f} ₽\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💰 ИТОГО К ОПЛАТЕ: {total_debt:,.0f} ₽"
        
        return text
    
    def format_all_debts_report(self, sort_by: str = 'debt') -> str:
        """Форматирование отчёта по всем долгам
        
        Args:
            sort_by: 'debt' - сортировка по сумме долга
                    'name' - сортировка по имени админа
        """
        debts = self.get_all_debts(sort_by=sort_by)
        
        if not debts:
            return "✅ Нет долгов"
        
        sort_label = "по сумме долга" if sort_by == 'debt' else "по имени"
        
        text = f"💳 ДОЛГИ АДМИНОВ ПО ТОВАРАМ (сортировка {sort_label})\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_all = 0
        
        for admin_id, data in debts.items():
            text += f"👤 {data['name']}\n"
            text += f"   💰 Долг: {data['total']:,.0f} ₽\n\n"
            total_all += data['total']
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💎 ВСЕГО ДОЛГОВ: {total_all:,.0f} ₽"
        
        return text
    
    def format_products_report(self, start_date: str = None, end_date: str = None, sort_by: str = 'admin') -> str:
        """Форматирование отчёта по товарам за период
        
        Args:
            start_date: начальная дата периода
            end_date: конечная дата периода
            sort_by: 'admin' - группировка по админам
                    'product' - группировка по товарам
        """
        report = self.get_products_report(start_date, end_date, sort_by=sort_by)
        
        if not report:
            return "📭 Нет данных за период"
        
        period_text = ""
        if start_date and end_date:
            period_text = f" с {start_date[:10]} по {end_date[:10]}"
        elif start_date:
            period_text = f" с {start_date[:10]}"
        
        sort_label = "по админам" if sort_by == 'admin' else "по товарам"
        
        text = f"📊 ОТЧЁТ ПО ТОВАРАМ{period_text} ({sort_label})\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if sort_by == 'product':
            # Группировка по товарам
            current_product = None
            product_total = 0
            
            for item in report:
                if current_product != item['product_name']:
                    if current_product:
                        text += f"   💰 Итого: {product_total:,.0f} ₽\n\n"
                    
                    current_product = item['product_name']
                    product_total = 0
                    text += f"📦 {current_product}\n"
                
                text += f"   👤 {item['admin_name']}: {item['total_quantity']} шт × "
                text += f"{item['total_debt']/item['total_quantity']:,.0f} ₽ = "
                text += f"{item['total_debt']:,.0f} ₽\n"
                
                product_total += item['total_debt']
            
            if current_product:
                text += f"   💰 Итого: {product_total:,.0f} ₽\n"
        else:
            # Группировка по админам
            current_admin = None
            admin_total = 0
            
            for item in report:
                if current_admin != item['admin_name']:
                    if current_admin:
                        text += f"   💰 Итого: {admin_total:,.0f} ₽\n\n"
                    
                    current_admin = item['admin_name']
                    admin_total = 0
                    text += f"👤 {current_admin}\n"
                
                text += f"   📦 {item['product_name']}: {item['total_quantity']} шт × "
                text += f"{item['total_debt']/item['total_quantity']:,.0f} ₽ = "
                text += f"{item['total_debt']:,.0f} ₽\n"
                
                admin_total += item['total_debt']
            
            if current_admin:
                text += f"   💰 Итого: {admin_total:,.0f} ₽\n"
        
        return text
    
    def format_products_summary_report(self, start_date: str = None, end_date: str = None) -> str:
        """Форматирование сводного отчёта по товарам (общие количества)
        
        Args:
            start_date: начальная дата периода
            end_date: конечная дата периода
            
        Returns:
            Строка формата "12 Gorilla, 14 Redbull за период"
        """
        summary = self.get_products_summary(start_date, end_date)
        
        if not summary:
            return "📭 Нет данных за период"
        
        period_text = ""
        if start_date and end_date:
            period_text = f" с {start_date[:10]} по {end_date[:10]}"
        elif start_date:
            period_text = f" с {start_date[:10]}"
        
        text = f"📊 СВОДКА ПО ТОВАРАМ{period_text}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Создаём строку в формате "12 Gorilla, 14 Redbull"
        products_list = []
        total_debt = 0
        
        for item in summary:
            products_list.append(f"{item['total_quantity']} {item['product_name']}")
            total_debt += item['total_debt']
        
        text += "📦 " + ", ".join(products_list) + "\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # Детальная разбивка
        text += "\nДетально:\n"
        for item in summary:
            text += f"  • {item['product_name']}: {item['total_quantity']} шт = {item['total_debt']:,.0f} ₽\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💰 ВСЕГО: {total_debt:,.0f} ₽"
        
        return text
    
    def format_detailed_debts_report(self) -> str:
        """Форматирование детального отчёта с разбивкой по админам и товарам
        
        Returns:
            Строка формата "Vanya: 2 Redbull, 4 Bulmeni = 300₽"
        """
        report = self.get_products_report(sort_by='admin')
        
        if not report:
            return "✅ Нет долгов"
        
        text = "💳 ДЕТАЛЬНЫЕ ДОЛГИ АДМИНОВ\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        current_admin = None
        admin_products = []
        admin_total = 0
        grand_total = 0
        
        for item in report:
            if current_admin != item['admin_name']:
                # Выводим предыдущего админа
                if current_admin and admin_products:
                    text += f"👤 {current_admin}: "
                    text += ", ".join(admin_products)
                    text += f" = {admin_total:,.0f} ₽\n\n"
                
                # Начинаем нового админа
                current_admin = item['admin_name']
                admin_products = []
                admin_total = 0
            
            admin_products.append(f"{item['total_quantity']} {item['product_name']}")
            admin_total += item['total_debt']
            grand_total += item['total_debt']
        
        # Выводим последнего админа
        if current_admin and admin_products:
            text += f"👤 {current_admin}: "
            text += ", ".join(admin_products)
            text += f" = {admin_total:,.0f} ₽\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💎 ВСЕГО ДОЛГОВ: {grand_total:,.0f} ₽"
        
        return text


    def get_all_admin_debts(self) -> List[Dict]:
        """Получить список всех админов с долгами"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    admin_id,
                    admin_name,
                    SUM(total_debt) as total_debt
                FROM admin_products
                WHERE settled = 0
                GROUP BY admin_id, admin_name
                HAVING SUM(total_debt) > 0
                ORDER BY total_debt DESC
            ''')
            
            debts = []
            for row in cursor.fetchall():
                debts.append({
                    'admin_id': row['admin_id'],
                    'admin_name': row['admin_name'],
                    'total_debt': row['total_debt']
                })
            
            conn.close()
            return debts
            
        except Exception as e:
            logger.error(f"Error getting admin debts: {e}")
            return []
    
    def get_admin_debt_details(self, admin_id: int) -> Optional[Dict]:
        """Получить детальную информацию о долге конкретного админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Получаем все неоплаченные товары
            cursor.execute('''
                SELECT 
                    id,
                    admin_name,
                    product_name,
                    quantity,
                    cost_price,
                    total_debt,
                    taken_at,
                    payment_proof_photo
                FROM admin_products
                WHERE admin_id = ? AND settled = 0
                ORDER BY taken_at DESC
            ''', (admin_id,))
            
            items = []
            total_debt = 0
            admin_name = None
            
            for row in cursor.fetchall():
                if not admin_name:
                    admin_name = row['admin_name']
                
                items.append({
                    'id': row['id'],
                    'product_name': row['product_name'],
                    'quantity': row['quantity'],
                    'cost_price': row['cost_price'],
                    'total_debt': row['total_debt'],
                    'taken_at': row['taken_at'],
                    'payment_proof_photo': row['payment_proof_photo']
                })
                total_debt += row['total_debt']
            
            conn.close()
            
            if not admin_name:
                return None
            
            return {
                'admin_id': admin_id,
                'admin_name': admin_name,
                'total_debt': total_debt,
                'items': items
            }
            
        except Exception as e:
            logger.error(f"Error getting admin debt details: {e}")
            return None
    
    def settle_admin_debt(self, admin_id: int) -> bool:
        """Списать весь долг админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE admin_products
                SET settled = 1, paid_at = ?
                WHERE admin_id = ? AND settled = 0
            ''', (datetime.now().isoformat(), admin_id))
            
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            
            logger.info(f"✅ Settled debt for admin {admin_id}, {affected} items marked as paid")
            return True
            
        except Exception as e:
            logger.error(f"Error settling admin debt: {e}")
            return False
    
    def submit_payment_proof(self, admin_id: int, photo_file_id: str) -> bool:
        """Прикрепить доказательство оплаты (фото чека)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Обновляем все неоплаченные записи админа
            cursor.execute('''
                UPDATE admin_products
                SET payment_proof_photo = ?
                WHERE admin_id = ? AND settled = 0
            ''', (photo_file_id, admin_id))
            
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            
            logger.info(f"✅ Payment proof submitted for admin {admin_id}, {affected} items updated")
            return True
            
        except Exception as e:
            logger.error(f"Error submitting payment proof: {e}")
            return False
