#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Product Commands - Команды управления товарами
Для владельца и админов
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# Состояния conversation handler
PRODUCT_ENTER_NAME, PRODUCT_ENTER_PRICE, PRODUCT_SELECT, PRODUCT_ENTER_QUANTITY = range(4)
PRODUCT_EDIT_PRICE = 5


class ProductCommands:
    """Обработчик команд управления товарами"""
    
    def __init__(self, product_manager, admin_manager, owner_id: int):
        self.product_manager = product_manager
        self.admin_manager = admin_manager
        self.owner_id = owner_id
    
    def is_owner(self, user_id: int) -> bool:
        """Проверка что пользователь - владелец"""
        return user_id == self.owner_id
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка что пользователь - админ"""
        return self.admin_manager.is_admin(user_id)
    
    async def show_product_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню товаров"""
        query = update.callback_query
        
        if query:
            user_id = query.from_user.id
            await query.answer()
        else:
            user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            text = "❌ Доступно только админам"
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        keyboard = []
        
        # Кнопка для админов
        keyboard.append([InlineKeyboardButton("📦 Записать товар на себя", callback_data="product_take")])
        keyboard.append([InlineKeyboardButton("💳 Мой долг", callback_data="product_my_debt")])
        
        # Кнопки для владельца
        if self.is_owner(user_id):
            keyboard.append([InlineKeyboardButton("📊 Отчёт по товарам", callback_data="product_report")])
            keyboard.append([InlineKeyboardButton("💰 Долги админов", callback_data="product_all_debts")])
            keyboard.append([InlineKeyboardButton("➕ Добавить товар", callback_data="product_add")])
            keyboard.append([InlineKeyboardButton("✏️ Изменить цену", callback_data="product_edit_price")])
            keyboard.append([InlineKeyboardButton("🗑️ Обнулить долг", callback_data="product_clear_debt")])
            keyboard.append([InlineKeyboardButton("🧹 Обнулить списанное", callback_data="product_clear_settled")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "📦 УПРАВЛЕНИЕ ТОВАРАМИ\n\n"
        text += "Система учёта товара на себестоимости"
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def show_my_debt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать долг админа"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Доступно только админам")
            return
        
        text = self.product_manager.format_admin_debt_report(user_id)
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="product_my_debt")],
            [InlineKeyboardButton("◀️ Назад", callback_data="product_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_all_debts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать долги всех админов (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        # Определяем режим сортировки из callback_data
        sort_by = 'debt'  # по умолчанию
        if query.data == 'product_all_debts_by_name':
            sort_by = 'name'
        
        text = self.product_manager.format_all_debts_report(sort_by=sort_by)
        
        keyboard = [
            [
                InlineKeyboardButton("📊 По долгу", callback_data="product_all_debts"),
                InlineKeyboardButton("👤 По имени", callback_data="product_all_debts_by_name")
            ],
            [InlineKeyboardButton("📋 Детальный отчёт", callback_data="product_detailed_debts")],
            [InlineKeyboardButton("◀️ Назад", callback_data="product_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def start_take_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать запись товара на админа"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Доступно только админам")
            return ConversationHandler.END
        
        products = self.product_manager.list_products()
        
        if not products:
            await query.edit_message_text(
                "❌ Нет товаров в базе. Обратитесь к владельцу.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="product_menu")
                ]])
            )
            return ConversationHandler.END
        
        # Создаём кнопки с товарами
        keyboard = []
        for prod in products:
            keyboard.append([InlineKeyboardButton(
                f"{prod['name']} - {prod['cost_price']:,.0f} ₽",
                callback_data=f"product_select_{prod['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="product_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📦 Выберите товар:",
            reply_markup=reply_markup
        )
        
        return PRODUCT_SELECT
    
    async def select_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор товара"""
        query = update.callback_query
        await query.answer()
        
        # Извлекаем ID товара из callback_data
        product_id = int(query.data.split('_')[-1])
        context.user_data['product_id'] = product_id
        
        product = self.product_manager.get_product(product_id)
        
        if not product:
            await query.edit_message_text("❌ Товар не найден")
            return ConversationHandler.END
        
        await query.edit_message_text(
            f"Товар: {product['name']}\n"
            f"Цена: {product['cost_price']:,.0f} ₽\n\n"
            "Введите количество:"
        )
        
        return PRODUCT_ENTER_QUANTITY
    
    async def enter_quantity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ввод количества"""
        try:
            quantity = int(update.message.text)
            
            if quantity <= 0:
                await update.message.reply_text("❌ Количество должно быть больше 0")
                return PRODUCT_ENTER_QUANTITY
            
            product_id = context.user_data['product_id']
            user_id = update.effective_user.id
            user_name = update.effective_user.full_name or update.effective_user.username or str(user_id)
            
            success = self.product_manager.record_admin_product(
                admin_id=user_id,
                admin_name=user_name,
                product_id=product_id,
                quantity=quantity
            )
            
            if success:
                product = self.product_manager.get_product(product_id)
                total = product['cost_price'] * quantity
                new_debt = self.product_manager.get_admin_debt(user_id)
                
                text = f"✅ Записано\n\n"
                text += f"📦 {product['name']}\n"
                text += f"🔢 Количество: {quantity} шт\n"
                text += f"💰 Сумма: {total:,.0f} ₽\n\n"
                text += f"💳 Ваш общий долг: {new_debt:,.0f} ₽"
            else:
                text = "❌ Ошибка записи"
            
            keyboard = [[InlineKeyboardButton("◀️ В меню товаров", callback_data="product_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup)
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return PRODUCT_ENTER_QUANTITY
    
    async def start_add_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать добавление товара (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return ConversationHandler.END
        
        await query.edit_message_text("Введите название товара:")
        
        return PRODUCT_ENTER_NAME
    
    async def enter_product_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ввод названия товара"""
        name = update.message.text
        context.user_data['product_name'] = name
        
        await update.message.reply_text(
            f"Товар: {name}\n\n"
            "Введите себестоимость (в рублях):"
        )
        
        return PRODUCT_ENTER_PRICE
    
    async def enter_product_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ввод цены товара"""
        try:
            price = float(update.message.text.replace(',', '.').replace(' ', ''))
            
            if price <= 0:
                await update.message.reply_text("❌ Цена должна быть больше 0")
                return PRODUCT_ENTER_PRICE
            
            name = context.user_data['product_name']
            
            success = self.product_manager.add_product(name, price)
            
            if success:
                text = f"✅ Товар добавлен\n\n"
                text += f"📦 {name}\n"
                text += f"💰 Себестоимость: {price:,.0f} ₽"
            else:
                text = "❌ Ошибка: товар с таким названием уже существует"
            
            keyboard = [[InlineKeyboardButton("◀️ В меню товаров", callback_data="product_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup)
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return PRODUCT_ENTER_PRICE
    
    async def show_products_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать отчёт по товарам (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        # Определяем режим сортировки из callback_data
        sort_by = 'admin'  # по умолчанию
        if query.data == 'product_report_by_product':
            sort_by = 'product'
        
        text = self.product_manager.format_products_report(sort_by=sort_by)
        
        keyboard = [
            [
                InlineKeyboardButton("👤 По админам", callback_data="product_report"),
                InlineKeyboardButton("📦 По товарам", callback_data="product_report_by_product")
            ],
            [InlineKeyboardButton("📊 Сводка", callback_data="product_summary")],
            [InlineKeyboardButton("◀️ Назад", callback_data="product_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_products_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать сводку по товарам (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        text = self.product_manager.format_products_summary_report()
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="product_summary")],
            [InlineKeyboardButton("◀️ К отчётам", callback_data="product_report")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_detailed_debts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать детальный отчёт по долгам (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        text = self.product_manager.format_detailed_debts_report()
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="product_detailed_debts")],
            [InlineKeyboardButton("◀️ К долгам", callback_data="product_all_debts")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def clear_settled_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обнулить списанные товары (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        deleted = self.product_manager.clear_settled_products()
        
        text = f"✅ Удалено {deleted} записей о списанных товарах"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="product_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def start_clear_debt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать обнуление долга админа (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        debts = self.product_manager.get_all_debts()
        
        if not debts:
            await query.edit_message_text(
                "✅ Нет долгов",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="product_menu")
                ]])
            )
            return
        
        keyboard = []
        
        # Кнопка для обнуления ВСЕХ долгов
        keyboard.append([InlineKeyboardButton(
            "🔄 ОБНУЛИТЬ ВСЕ ДОЛГИ",
            callback_data="product_clear_all_confirm"
        )])
        
        # Кнопки для каждого админа
        for admin_id, data in debts.items():
            keyboard.append([InlineKeyboardButton(
                f"{data['name']} - {data['total']:,.0f} ₽",
                callback_data=f"product_clear_{admin_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="product_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите админа для обнуления долга или обнулите все:",
            reply_markup=reply_markup
        )
    
    async def clear_all_debts_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение обнуления всех долгов"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, обнулить ВСЕ долги", callback_data="product_clear_all_execute")],
            [InlineKeyboardButton("❌ Отмена", callback_data="product_clear_debt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ ВНИМАНИЕ!\n\n"
            "Вы собираетесь обнулить долги ВСЕХ администраторов.\n"
            "Это действие нельзя отменить.\n\n"
            "Продолжить?",
            reply_markup=reply_markup
        )
    
    async def clear_all_debts_execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выполнение обнуления всех долгов"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        success = self.product_manager.clear_all_debts()
        
        if success:
            text = "✅ Все долги обнулены!"
        else:
            text = "❌ Ошибка при обнулении долгов"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="product_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
        
        await query.edit_message_text(
            "Выберите админа для обнуления долга:",
            reply_markup=reply_markup
        )
    
    async def clear_admin_debt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обнулить долг конкретного админа"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        # Извлекаем ID админа из callback_data
        admin_id = int(query.data.split('_')[-1])
        
        success = self.product_manager.clear_admin_debt(admin_id)
        
        if success:
            text = "✅ Долг обнулён"
        else:
            text = "❌ Ошибка"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="product_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def start_edit_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать изменение цены товара (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return ConversationHandler.END
        
        products = self.product_manager.list_products()
        
        if not products:
            await query.edit_message_text(
                "❌ Нет товаров в базе",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="product_menu")
                ]])
            )
            return ConversationHandler.END
        
        # Создаём кнопки с товарами
        keyboard = []
        for prod in products:
            keyboard.append([InlineKeyboardButton(
                f"{prod['name']} - {prod['cost_price']:,.0f} ₽",
                callback_data=f"product_price_{prod['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="product_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✏️ Выберите товар для изменения цены:",
            reply_markup=reply_markup
        )
        
        return PRODUCT_EDIT_PRICE
    
    async def select_product_for_price_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор товара для изменения цены"""
        query = update.callback_query
        await query.answer()
        
        # Извлекаем ID товара из callback_data
        product_id = int(query.data.split('_')[-1])
        context.user_data['edit_price_product_id'] = product_id
        
        product = self.product_manager.get_product(product_id)
        
        if not product:
            await query.edit_message_text("❌ Товар не найден")
            return ConversationHandler.END
        
        await query.edit_message_text(
            f"Товар: {product['name']}\n"
            f"Текущая цена: {product['cost_price']:,.0f} ₽\n\n"
            "Введите новую себестоимость:"
        )
        
        return PRODUCT_ENTER_PRICE
    
    async def enter_new_product_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ввод новой цены товара"""
        try:
            price = float(update.message.text.replace(',', '.').replace(' ', ''))
            
            if price <= 0:
                await update.message.reply_text("❌ Цена должна быть больше 0")
                return PRODUCT_ENTER_PRICE
            
            product_id = context.user_data['edit_price_product_id']
            product = self.product_manager.get_product(product_id)
            
            success = self.product_manager.update_product_price(product_id, price)
            
            if success:
                text = f"✅ Цена обновлена\n\n"
                text += f"📦 {product['name']}\n"
                text += f"Старая цена: {product['cost_price']:,.0f} ₽\n"
                text += f"Новая цена: {price:,.0f} ₽"
            else:
                text = "❌ Ошибка обновления цены"
            
            keyboard = [[InlineKeyboardButton("◀️ В меню товаров", callback_data="product_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup)
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return PRODUCT_ENTER_PRICE
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена операции"""
        context.user_data.clear()
        await self.show_product_menu(update, context)
        return ConversationHandler.END

