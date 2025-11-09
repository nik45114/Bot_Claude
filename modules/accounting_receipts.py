#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для отправки чеков и накладных в бухгалтерскую систему
"""

import aiohttp
import logging
import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Настройки API
ACCOUNTING_API_URL = "http://64.188.83.12:8000"
API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"

# States for conversation handlers
RECEIPT_ENTER_QR, RECEIPT_ENTER_CATEGORY, RECEIPT_CONFIRM = range(3)
INVOICE_ENTER_SUPPLIER, INVOICE_ENTER_AMOUNT, INVOICE_UPLOAD_PHOTO, INVOICE_ENTER_DESCRIPTION, INVOICE_CONFIRM = range(5)


class AccountingReceipts:
    """Класс для работы с чеками и накладными"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Инициализация таблиц БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Таблица для хранения отправленных чеков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sent_receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qr_data TEXT NOT NULL,
                    total_amount REAL,
                    seller TEXT,
                    category TEXT,
                    sent_by INTEGER,
                    sent_by_name TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fns_url TEXT,
                    notes TEXT
                )
            ''')

            # Таблица для хранения накладных
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT,
                    photo_file_id TEXT,
                    sent_by INTEGER,
                    sent_by_name TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            ''')

            conn.commit()
            conn.close()
            logger.info("✅ Accounting receipts DB initialized")
        except Exception as e:
            logger.error(f"❌ Failed to init receipts DB: {e}")

    async def send_receipt(
        self,
        qr_data: str,
        category: Optional[str] = None,
        notes: Optional[str] = None,
        sent_by: Optional[int] = None,
        sent_by_name: Optional[str] = None
    ) -> dict:
        """
        Отправить чек в бухгалтерию

        Args:
            qr_data: Данные QR-кода с чека
            category: Категория расхода
            notes: Примечания
            sent_by: ID отправителя
            sent_by_name: Имя отправителя

        Returns:
            dict с результатом
        """
        url = f"{ACCOUNTING_API_URL}/api/receipt"

        payload = {
            "qr_data": qr_data,
            "category": category,
            "notes": notes
        }

        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.info(f"✅ Receipt sent: {result}")

                        # Сохраняем в БД
                        if result.get("status") == "success":
                            data = result.get("data", {})
                            self._save_receipt_to_db(
                                qr_data=qr_data,
                                total_amount=data.get("total_amount"),
                                seller=data.get("seller"),
                                category=category,
                                sent_by=sent_by,
                                sent_by_name=sent_by_name,
                                fns_url=data.get("fns_url"),
                                notes=notes
                            )

                        return result
                    else:
                        error = await resp.text()
                        logger.error(f"❌ Error sending receipt {resp.status}: {error}")
                        return {"status": "error", "message": error}

        except Exception as e:
            logger.error(f"❌ Exception sending receipt: {e}")
            return {"status": "error", "message": str(e)}

    def _save_receipt_to_db(
        self,
        qr_data: str,
        total_amount: Optional[float],
        seller: Optional[str],
        category: Optional[str],
        sent_by: Optional[int],
        sent_by_name: Optional[str],
        fns_url: Optional[str],
        notes: Optional[str]
    ):
        """Сохранить чек в БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO sent_receipts
                (qr_data, total_amount, seller, category, sent_by, sent_by_name, fns_url, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (qr_data, total_amount, seller, category, sent_by, sent_by_name, fns_url, notes))

            conn.commit()
            conn.close()
            logger.info("✅ Receipt saved to DB")
        except Exception as e:
            logger.error(f"❌ Failed to save receipt to DB: {e}")

    async def save_invoice(
        self,
        supplier: str,
        amount: float,
        description: Optional[str],
        photo_file_id: Optional[str],
        sent_by: Optional[int],
        sent_by_name: Optional[str],
        notes: Optional[str]
    ) -> bool:
        """
        Сохранить накладную в БД

        Args:
            supplier: Поставщик
            amount: Сумма
            description: Описание
            photo_file_id: ID фото накладной
            sent_by: ID отправителя
            sent_by_name: Имя отправителя
            notes: Примечания

        Returns:
            bool - успешно или нет
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO invoices
                (supplier, amount, description, photo_file_id, sent_by, sent_by_name, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (supplier, amount, description, photo_file_id, sent_by, sent_by_name, notes))

            conn.commit()
            conn.close()
            logger.info("✅ Invoice saved to DB")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save invoice to DB: {e}")
            return False

    def get_recent_receipts(self, limit: int = 10) -> List[Dict]:
        """Получить последние отправленные чеки"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM sent_receipts
                ORDER BY sent_at DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Failed to get receipts: {e}")
            return []

    def get_recent_invoices(self, limit: int = 10) -> List[Dict]:
        """Получить последние накладные"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM invoices
                ORDER BY sent_at DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Failed to get invoices: {e}")
            return []


# ===== Обработчики для отправки чеков =====

async def start_send_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс отправки чека"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "📸 Отправка чека в бухгалтерию\n\n"
            "Сканируйте QR-код с чека и отправьте текст.\n\n"
            "QR-код выглядит примерно так:\n"
            "<code>t=20240115T1530&s=1500.00&fn=9999078900004792&i=12345&fp=3522207165&n=1</code>\n\n"
            "Или отправьте /cancel для отмены",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "📸 Отправка чека в бухгалтерию\n\n"
            "Сканируйте QR-код с чека и отправьте текст.\n\n"
            "QR-код выглядит примерно так:\n"
            "<code>t=20240115T1530&s=1500.00&fn=9999078900004792&i=12345&fp=3522207165&n=1</code>\n\n"
            "Или отправьте /cancel для отмены",
            parse_mode="HTML"
        )

    return RECEIPT_ENTER_QR


async def receipt_enter_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить QR-код чека"""
    qr_data = update.message.text.strip()

    # Проверка что это похоже на QR-код
    if not (qr_data.startswith("t=") or qr_data.startswith("http")):
        await update.message.reply_text(
            "❌ Это не похоже на QR-код с чека.\n\n"
            "QR-код должен начинаться с 't=' или быть ссылкой.\n\n"
            "Попробуйте еще раз или /cancel"
        )
        return RECEIPT_ENTER_QR

    # Сохраняем QR-код
    context.user_data['receipt_qr'] = qr_data

    # Предлагаем выбрать категорию
    keyboard = [
        [InlineKeyboardButton("🍕 Продукты/Еда", callback_data="receipt_cat_food")],
        [InlineKeyboardButton("🧹 Хозтовары", callback_data="receipt_cat_household")],
        [InlineKeyboardButton("🔧 Ремонт", callback_data="receipt_cat_repair")],
        [InlineKeyboardButton("💡 Другое", callback_data="receipt_cat_other")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data="receipt_cat_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "✅ QR-код получен!\n\n"
        "Выберите категорию расхода:",
        reply_markup=reply_markup
    )

    return RECEIPT_ENTER_CATEGORY


async def receipt_select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрать категорию чека"""
    query = update.callback_query
    await query.answer()

    category_map = {
        "receipt_cat_food": "Продукты/Еда",
        "receipt_cat_household": "Хозтовары",
        "receipt_cat_repair": "Ремонт",
        "receipt_cat_other": "Другое",
        "receipt_cat_skip": None
    }

    category = category_map.get(query.data)
    context.user_data['receipt_category'] = category

    # Подтверждение
    qr_data = context.user_data.get('receipt_qr')

    msg = "📋 Подтверждение отправки чека\n\n"
    msg += f"📝 QR-код: <code>{qr_data[:50]}...</code>\n"
    if category:
        msg += f"📁 Категория: {category}\n"
    msg += "\nОтправить в бухгалтерию?"

    keyboard = [
        [InlineKeyboardButton("✅ Отправить", callback_data="receipt_confirm_yes")],
        [InlineKeyboardButton("❌ Отменить", callback_data="receipt_confirm_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="HTML")

    return RECEIPT_CONFIRM


async def receipt_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и отправка чека"""
    query = update.callback_query
    await query.answer()

    if query.data == "receipt_confirm_no":
        await query.edit_message_text("❌ Отправка чека отменена")
        context.user_data.clear()
        return ConversationHandler.END

    # Отправляем чек
    qr_data = context.user_data.get('receipt_qr')
    category = context.user_data.get('receipt_category')

    user = query.from_user

    await query.edit_message_text("⏳ Отправляю чек в бухгалтерию...")

    # Получаем экземпляр AccountingReceipts из context
    accounting_receipts = context.bot_data.get('accounting_receipts')

    if not accounting_receipts:
        await query.edit_message_text("❌ Модуль чеков не инициализирован")
        context.user_data.clear()
        return ConversationHandler.END

    result = await accounting_receipts.send_receipt(
        qr_data=qr_data,
        category=category,
        notes=f"Отправлено через бот от {user.full_name}",
        sent_by=user.id,
        sent_by_name=user.full_name
    )

    if result.get("status") == "success":
        data = result.get("data", {})
        msg = "✅ Чек успешно отправлен!\n\n"
        msg += f"💰 Сумма: {data.get('total_amount', 'N/A')} ₽\n"
        msg += f"🏪 Продавец: {data.get('seller', 'N/A')}\n"
        if data.get('fns_url'):
            msg += f"🔗 Ссылка на чек: {data.get('fns_url')}\n"
        msg += "\nЧек добавлен в бухгалтерию."

        await query.edit_message_text(msg)
    else:
        await query.edit_message_text(
            f"❌ Ошибка при отправке чека:\n{result.get('message', 'Неизвестная ошибка')}"
        )

    context.user_data.clear()
    return ConversationHandler.END


# ===== Обработчики для отправки накладных =====

async def start_send_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс отправки накладной"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "📦 Отправка накладной\n\n"
            "Введите название поставщика:"
        )
    else:
        await update.message.reply_text(
            "📦 Отправка накладной\n\n"
            "Введите название поставщика:"
        )

    return INVOICE_ENTER_SUPPLIER


async def invoice_enter_supplier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод поставщика"""
    supplier = update.message.text.strip()
    context.user_data['invoice_supplier'] = supplier

    await update.message.reply_text(
        f"✅ Поставщик: {supplier}\n\n"
        "Введите сумму накладной (в рублях):"
    )

    return INVOICE_ENTER_AMOUNT


async def invoice_enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод суммы"""
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        context.user_data['invoice_amount'] = amount

        await update.message.reply_text(
            f"✅ Сумма: {amount:,.2f} ₽\n\n"
            "Отправьте фото накладной или /skip чтобы пропустить:"
        )

        return INVOICE_UPLOAD_PHOTO
    except ValueError:
        await update.message.reply_text(
            "❌ Неверная сумма. Введите число:\n\n"
            "Пример: 5000 или 5000.50"
        )
        return INVOICE_ENTER_AMOUNT


async def invoice_upload_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Загрузка фото накладной"""
    if update.message.photo:
        # Получаем файл самого большого размера
        photo = update.message.photo[-1]
        context.user_data['invoice_photo_id'] = photo.file_id

        await update.message.reply_text(
            "✅ Фото получено!\n\n"
            "Введите описание (необязательно) или /skip:"
        )
    else:
        context.user_data['invoice_photo_id'] = None
        await update.message.reply_text(
            "Введите описание (необязательно) или /skip:"
        )

    return INVOICE_ENTER_DESCRIPTION


async def invoice_enter_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод описания"""
    if update.message.text and update.message.text.strip().lower() == "/skip":
        description = None
    else:
        description = update.message.text.strip() if update.message.text else None

    context.user_data['invoice_description'] = description

    # Подтверждение
    supplier = context.user_data.get('invoice_supplier')
    amount = context.user_data.get('invoice_amount')
    has_photo = context.user_data.get('invoice_photo_id') is not None

    msg = "📋 Подтверждение накладной\n\n"
    msg += f"🏪 Поставщик: {supplier}\n"
    msg += f"💰 Сумма: {amount:,.2f} ₽\n"
    msg += f"📸 Фото: {'✅ Да' if has_photo else '❌ Нет'}\n"
    if description:
        msg += f"📝 Описание: {description}\n"
    msg += "\nСохранить накладную?"

    keyboard = [
        [InlineKeyboardButton("✅ Сохранить", callback_data="invoice_confirm_yes")],
        [InlineKeyboardButton("❌ Отменить", callback_data="invoice_confirm_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(msg, reply_markup=reply_markup)

    return INVOICE_CONFIRM


async def invoice_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и сохранение накладной"""
    query = update.callback_query
    await query.answer()

    if query.data == "invoice_confirm_no":
        await query.edit_message_text("❌ Сохранение накладной отменено")
        context.user_data.clear()
        return ConversationHandler.END

    # Сохраняем накладную
    supplier = context.user_data.get('invoice_supplier')
    amount = context.user_data.get('invoice_amount')
    description = context.user_data.get('invoice_description')
    photo_id = context.user_data.get('invoice_photo_id')

    user = query.from_user

    await query.edit_message_text("⏳ Сохраняю накладную...")

    # Получаем экземпляр AccountingReceipts из context
    accounting_receipts = context.bot_data.get('accounting_receipts')

    if not accounting_receipts:
        await query.edit_message_text("❌ Модуль накладных не инициализирован")
        context.user_data.clear()
        return ConversationHandler.END

    success = await accounting_receipts.save_invoice(
        supplier=supplier,
        amount=amount,
        description=description,
        photo_file_id=photo_id,
        sent_by=user.id,
        sent_by_name=user.full_name,
        notes=f"Отправлено через бот от {user.full_name}"
    )

    if success:
        msg = "✅ Накладная успешно сохранена!\n\n"
        msg += f"🏪 Поставщик: {supplier}\n"
        msg += f"💰 Сумма: {amount:,.2f} ₽\n"
        msg += "\nНакладная добавлена в систему."

        await query.edit_message_text(msg)
    else:
        await query.edit_message_text("❌ Ошибка при сохранении накладной")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    await update.message.reply_text("❌ Операция отменена")
    context.user_data.clear()
    return ConversationHandler.END
