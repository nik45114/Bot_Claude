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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица товаров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                cost_price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица взятых товаров админами
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
        
        conn.commit()
        conn.close()
        logger.info("✅ Product Manager database initialized")
    
    def add_product(self, name: str, cost_price: float) -> bool:
        """Добавить новый товар"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO products (name, cost_price)
                VALUES (?, ?)
            ''', (name, cost_price))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Product added: {name} - {cost_price} ₽")
            return True
            
        except sqlite3.IntegrityError:
            logger.error(f"❌ Product {name} already exists")
            return False
        except Exception as e:
            logger.error(f"❌ Error adding product: {e}")
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
    
    def get_all_debts(self) -> Dict:
        """Получить долги всех админов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT admin_id, admin_name, SUM(total_debt) as total
                FROM admin_products
                WHERE settled = FALSE
                GROUP BY admin_id
                ORDER BY total DESC
            ''')
            
            debts = {}
            for row in cursor.fetchall():
                admin_id, admin_name, total = row
                debts[admin_id] = {
                    'name': admin_name,
                    'total': total
                }
            
            conn.close()
            return debts
            
        except Exception as e:
            logger.error(f"❌ Error getting all debts: {e}")
            return {}
    
    def get_products_report(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Получить отчёт по товарам за период"""
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
            
            query += ' GROUP BY admin_id, product_name ORDER BY admin_name, product_name'
            
            cursor.execute(query, params)
            
            report = []
            for row in cursor.fetchall():
                report.append({
                    'admin_id': row[0],
                    'admin_name': row[1],
                    'product_name': row[2],
                    'total_quantity': row[3],
                    'total_debt': row[4]
                })
            
            conn.close()
            return report
            
        except Exception as e:
            logger.error(f"❌ Error getting products report: {e}")
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
    
    def format_all_debts_report(self) -> str:
        """Форматирование отчёта по всем долгам"""
        debts = self.get_all_debts()
        
        if not debts:
            return "✅ Нет долгов"
        
        text = "💳 ДОЛГИ АДМИНОВ ПО ТОВАРАМ\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_all = 0
        
        for admin_id, data in debts.items():
            text += f"👤 {data['name']}\n"
            text += f"   💰 Долг: {data['total']:,.0f} ₽\n\n"
            total_all += data['total']
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💎 ВСЕГО ДОЛГОВ: {total_all:,.0f} ₽"
        
        return text
    
    def format_products_report(self, start_date: str = None, end_date: str = None) -> str:
        """Форматирование отчёта по товарам за период"""
        report = self.get_products_report(start_date, end_date)
        
        if not report:
            return "📭 Нет данных за период"
        
        period_text = ""
        if start_date and end_date:
            period_text = f" с {start_date[:10]} по {end_date[:10]}"
        elif start_date:
            period_text = f" с {start_date[:10]}"
        
        text = f"📊 ОТЧЁТ ПО ТОВАРАМ{period_text}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
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
