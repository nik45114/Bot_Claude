#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Management Wizard
Conversation handlers and callbacks for admin management UI
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from typing import Optional, List
import re

from .db import AdminDB, ROLE_PERMISSIONS, PERMISSIONS
from .formatters import (
    format_admin_card, format_admin_list, format_admin_display_name,
    format_invite_card, format_request_card, format_pagination_buttons,
    format_role_name, format_role_emoji, format_permission_name,
    format_audit_log_entry
)


# Conversation states
(WAITING_USERNAME, WAITING_BULK_USERNAMES, WAITING_NOTES,
 WAITING_SEARCH_QUERY, WAITING_INVITE_ROLE, WAITING_REQUEST_MESSAGE, 
 WAITING_EDIT_NAME) = range(7)


class AdminWizard:
    """Admin management wizard with all UI handlers"""
    
    def __init__(self, db: AdminDB, owner_ids: List[int], bot_username: str = None):
        self.db = db
        self.owner_ids = owner_ids
        self.bot_username = bot_username
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        return user_id in self.owner_ids
    
    def can_manage_admins(self, user_id: int) -> bool:
        """Check if user can manage admins"""
        return self.is_owner(user_id) or self.db.has_permission(user_id, 'can_manage_admins')
    
    # ===== Main Menu =====
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main admin management menu"""
        user_id = update.effective_user.id
        
        if not self.can_manage_admins(user_id):
            await update.message.reply_text("❌ У вас нет прав для управления админами")
            return
        
        text = """👥 Управление админами
━━━━━━━━━━━━━━━━━━━━
Выберите действие:"""
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить админа", callback_data="adm_add_main")],
            [InlineKeyboardButton("👥 Список админов", callback_data="adm_list_1")],
            [InlineKeyboardButton("🔎 Поиск", callback_data="adm_search_start")],
            [InlineKeyboardButton("📨 Запросы/Приглашения", callback_data="adm_requests_main")],
        ]
        
        if self.is_owner(user_id):
            keyboard.append([InlineKeyboardButton("⚙️ Роли и права", callback_data="adm_roles_info")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    # ===== Add Admin Flows =====
    
    async def show_add_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show add admin menu with different methods"""
        query = update.callback_query
        await query.answer()
        
        text = """➕ Добавить админа
━━━━━━━━━━━━━━━━━━━━
Выберите способ:"""
        
        keyboard = [
            [InlineKeyboardButton("👤 По @username", callback_data="adm_add_by_username")],
            [InlineKeyboardButton("📝 Несколько (список)", callback_data="adm_add_bulk")],
            [InlineKeyboardButton("📨 Создать приглашение", callback_data="adm_invite_create_start")],
            [InlineKeyboardButton("◀️ Назад", callback_data="adm_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def start_add_by_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start adding admin by username"""
        query = update.callback_query
        await query.answer()
        
        text = """👤 Добавление админа по @username
━━━━━━━━━━━━━━━━━━━━
Отправьте @username админа (с @ или без)
Например: @username или username

Отправьте /cancel для отмены"""
        
        await query.edit_message_text(text)
        return WAITING_USERNAME
    
    async def receive_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive username and add admin"""
        username = update.message.text.strip().lstrip('@')
        user_id = update.effective_user.id
        
        if not username:
            await update.message.reply_text("❌ Неверный формат username. Попробуйте снова или /cancel")
            return WAITING_USERNAME
        
        # Try to find existing user
        existing_admin = self.db.get_admin_by_username(username)
        if existing_admin:
            await update.message.reply_text(
                f"ℹ️ @{username} уже является админом\n\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👁️ Просмотр", callback_data=f"adm_view_{existing_admin['user_id']}")
                ], [
                    InlineKeyboardButton("◀️ Назад", callback_data="adm_menu")
                ]])
            )
            return ConversationHandler.END
        
        # Create pending admin (will be activated when user writes to bot)
        # For now, we'll add with user_id = 0 to mark as pending
        # This is a simplified version - in production, you'd create a pending entry
        
        text = f"""⚠️ Пользователь @{username} не найден в базе
        
Админ будет добавлен когда пользователь напишет боту.
Создать приглашение вместо этого?"""
        
        keyboard = [
            [InlineKeyboardButton("📨 Создать приглашение", callback_data=f"adm_invite_for_{username}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="adm_menu")]
        ]
        
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    
    async def start_add_bulk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start bulk add"""
        query = update.callback_query
        await query.answer()
        
        text = """📝 Добавление нескольких админов
━━━━━━━━━━━━━━━━━━━━
Отправьте список @username, каждый с новой строки:

@username1
@username2
@username3

Отправьте /cancel для отмены"""
        
        await query.edit_message_text(text)
        return WAITING_BULK_USERNAMES
    
    async def receive_bulk_usernames(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive bulk usernames"""
        text = update.message.text.strip()
        usernames = [line.strip().lstrip('@') for line in text.split('\n') if line.strip()]
        
        if not usernames:
            await update.message.reply_text("❌ Не найдено ни одного username. Попробуйте снова или /cancel")
            return WAITING_BULK_USERNAMES
        
        results = []
        for username in usernames:
            existing = self.db.get_admin_by_username(username)
            if existing:
                results.append(f"✅ @{username} - уже админ")
            else:
                results.append(f"📨 @{username} - создано приглашение")
                # Create invite for this username
                token = self.db.create_invite(
                    update.effective_user.id,
                    target_username=username,
                    role_default='staff'
                )
                if token:
                    self.db.log_action(
                        update.effective_user.id,
                        'invite_create',
                        details={'username': username, 'token': token}
                    )
        
        result_text = "📊 Результаты:\n\n" + "\n".join(results)
        await update.message.reply_text(
            result_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к меню", callback_data="adm_menu")
            ]])
        )
        
        return ConversationHandler.END
    
    # ===== Admin List and View =====
    
    async def show_admin_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               page: int = 1, role: str = None, active: int = None):
        """Show paginated admin list"""
        query = update.callback_query
        if query:
            await query.answer()
        
        admins, total = self.db.list_admins(role=role, active=active, page=page, per_page=20)
        
        if not admins:
            text = "📭 Список админов пуст"
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="adm_menu")]]
        else:
            text = format_admin_list(admins, page, total, per_page=20)
            
            # Build keyboard with admin buttons
            keyboard = []
            for admin in admins:
                btn_text = format_admin_display_name(admin)
                keyboard.append([InlineKeyboardButton(
                    btn_text, 
                    callback_data=f"adm_view_{admin['user_id']}"
                )])
            
            # Pagination
            total_pages = (total + 19) // 20
            if total_pages > 1:
                nav_buttons = format_pagination_buttons(page, total_pages, "adm_list")
                keyboard.extend(nav_buttons)
            
            # Filters
            filter_row = []
            if active is None:
                filter_row.append(InlineKeyboardButton("✅ Только активные", callback_data="adm_list_active_1_1"))
            else:
                filter_row.append(InlineKeyboardButton("👥 Все админы", callback_data="adm_list_1"))
            
            if filter_row:
                keyboard.append(filter_row)
            
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def show_admin_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show detailed admin view"""
        query = update.callback_query
        await query.answer()
        
        admin = self.db.get_admin(user_id)
        if not admin:
            await query.edit_message_text(
                "❌ Админ не найден",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="adm_list_1")
                ]])
            )
            return
        
        permissions = self.db.get_permissions(user_id)
        text = format_admin_card(admin, permissions)
        
        # Build action buttons
        keyboard = []
        
        # Role and permissions (owner only)
        if self.is_owner(update.effective_user.id):
            keyboard.append([
                InlineKeyboardButton("🔖 Изменить роль", callback_data=f"adm_set_role_{user_id}"),
                InlineKeyboardButton("🔐 Права", callback_data=f"adm_perms_{user_id}")
            ])
        
        # Activate/Deactivate
        if admin['active'] == 1:
            keyboard.append([InlineKeyboardButton("❌ Деактивировать", callback_data=f"adm_deactivate_{user_id}")])
        else:
            keyboard.append([InlineKeyboardButton("✅ Активировать", callback_data=f"adm_activate_{user_id}")])
        
        # Edit name
        keyboard.append([InlineKeyboardButton("✏️ Редактировать имя", callback_data=f"adm_edit_name_{user_id}")])
        
        # Salary settings (owner only)
        if self.is_owner(update.effective_user.id):
            keyboard.append([InlineKeyboardButton("💰 Настроить зарплату", callback_data=f"adm_salary_{user_id}")])
        
        # Remove (owner only, not self)
        if self.is_owner(update.effective_user.id) and user_id != update.effective_user.id:
            keyboard.append([InlineKeyboardButton("🗑️ Удалить", callback_data=f"adm_remove_confirm_{user_id}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад к списку", callback_data="adm_list_1")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    # ===== Role Management =====
    
    async def show_role_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show role selection menu"""
        query = update.callback_query
        await query.answer()
        
        admin = self.db.get_admin(user_id)
        if not admin:
            await query.edit_message_text("❌ Админ не найден")
            return
        
        text = f"""🔖 Изменить роль
━━━━━━━━━━━━━━━━━━━━
Админ: {format_admin_display_name(admin)}
Текущая роль: {format_role_emoji(admin['role'])} {format_role_name(admin['role'])}

Выберите новую роль:"""
        
        keyboard = []
        for role in ['owner', 'manager', 'moderator', 'staff']:
            emoji = format_role_emoji(role)
            name = format_role_name(role)
            current = " ✓" if admin['role'] == role else ""
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {name}{current}",
                callback_data=f"adm_setrole_{user_id}_{role}"
            )])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"adm_view_{user_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def set_role(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, role: str):
        """Set admin role"""
        query = update.callback_query
        await query.answer()
        
        if self.db.set_role(user_id, role):
            # Log action
            self.db.log_action(
                update.effective_user.id,
                'set_role',
                user_id,
                {'role': role}
            )
            
            await query.answer(f"✅ Роль изменена на {format_role_name(role)}", show_alert=True)
        else:
            await query.answer("❌ Ошибка при изменении роли", show_alert=True)
        
        # Return to admin view
        await self.show_admin_view(update, context, user_id)
    
    # ===== Permission Management =====
    
    async def show_permissions(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show permission management"""
        query = update.callback_query
        await query.answer()
        
        admin = self.db.get_admin(user_id)
        if not admin:
            await query.edit_message_text("❌ Админ не найден")
            return
        
        permissions = self.db.get_permissions(user_id)
        custom_perms = admin.get('permissions')
        
        text = f"""🔐 Управление правами
━━━━━━━━━━━━━━━━━━━━
Админ: {format_admin_display_name(admin)}
Роль: {format_role_emoji(admin['role'])} {format_role_name(admin['role'])}
"""
        
        if custom_perms:
            text += "\n⚙️ Установлены особые права (не по роли)"
        else:
            text += "\n📋 Используются права по роли"
        
        text += "\n\nТекущие права:"
        
        # Group permissions
        perm_groups = {
            '💰 Финансы': ['cash_view', 'cash_edit'],
            '📦 Товары': ['products_view', 'products_edit'],
            '🐛 Проблемы': ['issues_view', 'issues_edit'],
            '🔐 VPN': ['v2ray_view', 'v2ray_manage'],
            '🎨 Контент': ['content_generate'],
            '👥 Админы': ['can_manage_admins']
        }
        
        keyboard = []
        for group_name, group_perms in perm_groups.items():
            for perm in group_perms:
                if perm in permissions:
                    status = "✅" if permissions[perm] else "❌"
                    perm_name = format_permission_name(perm)
                    text += f"\n{status} {perm_name}"
                    
                    # Add toggle button
                    new_value = not permissions[perm]
                    keyboard.append([InlineKeyboardButton(
                        f"{status} {perm_name}",
                        callback_data=f"adm_toggleperm_{user_id}_{perm}_{int(new_value)}"
                    )])
        
        # Reset to role defaults
        if custom_perms:
            keyboard.append([InlineKeyboardButton("🔄 Сбросить к роли", callback_data=f"adm_resetperms_{user_id}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"adm_view_{user_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def toggle_permission(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                user_id: int, permission: str, value: bool):
        """Toggle a permission"""
        query = update.callback_query

        # Check if current user is owner
        if not self.is_owner(update.effective_user.id):
            await query.answer("❌ Только владелец может изменять права", show_alert=True)
            return

        # Check if admin exists
        admin = self.db.get_admin(user_id)
        if not admin:
            await query.answer("❌ Админ не найден", show_alert=True)
            return

        # Validate permission name
        from .db import PERMISSIONS
        if permission not in PERMISSIONS:
            await query.answer("❌ Неверное право", show_alert=True)
            return

        # Get current permissions
        permissions = self.db.get_permissions(user_id)
        permissions[permission] = value

        if self.db.set_permissions(user_id, permissions):
            # Log action
            self.db.log_action(
                update.effective_user.id,
                'set_permissions',
                user_id,
                {permission: value}
            )

            # Обновить интерфейс сразу
            await self.show_permissions(update, context, user_id)
            # Уведомление после обновления
            await query.answer("✅ Права обновлены", show_alert=False)
        else:
            await query.answer("❌ Ошибка при обновлении прав", show_alert=True)
    
    async def reset_permissions(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Reset permissions to role defaults"""
        query = update.callback_query
        await query.answer()
        
        if self.db.reset_permissions(user_id):
            # Log action
            self.db.log_action(
                update.effective_user.id,
                'set_permissions',
                user_id,
                {'reset': True}
            )
            
            await query.answer("✅ Права сброшены к роли", show_alert=True)
        else:
            await query.answer("❌ Ошибка при сбросе прав", show_alert=True)
        
        # Refresh view
        await self.show_permissions(update, context, user_id)
    
    # ===== Activate/Deactivate =====
    
    async def activate_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Activate admin"""
        query = update.callback_query
        await query.answer()
        
        if self.db.set_active(user_id, 1):
            # Log action
            self.db.log_action(update.effective_user.id, 'activate', user_id)
            await query.answer("✅ Админ активирован", show_alert=True)
        else:
            await query.answer("❌ Ошибка при активации", show_alert=True)
        
        # Return to admin view
        await self.show_admin_view(update, context, user_id)
    
    async def deactivate_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Deactivate admin"""
        query = update.callback_query
        await query.answer()
        
        if self.db.set_active(user_id, 0):
            # Log action
            self.db.log_action(update.effective_user.id, 'deactivate', user_id)
            await query.answer("✅ Админ деактивирован", show_alert=True)
        else:
            await query.answer("❌ Ошибка при деактивации", show_alert=True)
        
        # Return to admin view
        await self.show_admin_view(update, context, user_id)
    
    # ===== Remove Admin =====
    
    async def show_remove_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show remove confirmation"""
        query = update.callback_query
        await query.answer()
        
        admin = self.db.get_admin(user_id)
        if not admin:
            await query.edit_message_text("❌ Админ не найден")
            return
        
        text = f"""⚠️ Удалить админа?
━━━━━━━━━━━━━━━━━━━━
{format_admin_display_name(admin)}

Это действие нельзя отменить!"""
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Да, удалить", callback_data=f"adm_remove_do_{user_id}")],
            [InlineKeyboardButton("◀️ Отмена", callback_data=f"adm_view_{user_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def remove_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Remove admin"""
        query = update.callback_query
        await query.answer()
        
        if self.db.remove_admin(user_id):
            # Log action
            self.db.log_action(update.effective_user.id, 'remove', user_id)
            await query.answer("✅ Админ удалён", show_alert=True)
            
            # Return to list
            await self.show_admin_list(update, context, page=1)
        else:
            await query.answer("❌ Ошибка при удалении", show_alert=True)
    
    # ===== Search =====
    
    async def start_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start search"""
        query = update.callback_query
        await query.answer()
        
        text = """🔎 Поиск админов
━━━━━━━━━━━━━━━━━━━━
Введите @username, имя или ID админа

Отправьте /cancel для отмены"""
        
        await query.edit_message_text(text)
        return WAITING_SEARCH_QUERY
    
    async def receive_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive search query"""
        query = update.message.text.strip()
        
        if not query:
            await update.message.reply_text("❌ Пустой запрос. Попробуйте снова или /cancel")
            return WAITING_SEARCH_QUERY
        
        admins, total = self.db.search_admins(query, page=1, per_page=20)
        
        if not admins:
            await update.message.reply_text(
                f"📭 Ничего не найдено по запросу: {query}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="adm_menu")
                ]])
            )
        else:
            text = f"🔎 Результаты поиска: {query}\n━━━━━━━━━━━━━━━━━━━━\nНайдено: {total}\n\n"
            
            keyboard = []
            for admin in admins[:10]:  # Show max 10 results
                btn_text = format_admin_display_name(admin)
                keyboard.append([InlineKeyboardButton(
                    btn_text,
                    callback_data=f"adm_view_{admin['user_id']}"
                )])
            
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_menu")])
            
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        return ConversationHandler.END
    
    # ===== Invites =====
    
    async def show_requests_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show requests and invites menu"""
        query = update.callback_query
        await query.answer()
        
        # Get counts
        requests, req_total = self.db.list_requests(status='pending', page=1, per_page=1)
        invites, inv_total = self.db.list_invites(status='pending', page=1, per_page=1)
        
        text = f"""📨 Запросы и приглашения
━━━━━━━━━━━━━━━━━━━━
⏳ Запросов на рассмотрении: {req_total}
📨 Активных приглашений: {inv_total}"""
        
        keyboard = [
            [InlineKeyboardButton(f"📨 Запросы ({req_total})", callback_data="adm_requests_list_1")],
            [InlineKeyboardButton(f"🔗 Приглашения ({inv_total})", callback_data="adm_invites_list_1")],
            [InlineKeyboardButton("◀️ Назад", callback_data="adm_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_requests_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
        """Show admin requests list"""
        query = update.callback_query
        await query.answer()
        
        requests, total = self.db.list_requests(status='pending', page=page, per_page=10)
        
        if not requests:
            text = "📭 Нет запросов на рассмотрении"
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="adm_requests_main")]]
        else:
            text = f"📨 Запросы на админа\n━━━━━━━━━━━━━━━━━━━━\nВсего: {total}\n"
            
            keyboard = []
            for req in requests:
                user_name = req.get('full_name') or req.get('username') or str(req['user_id'])
                keyboard.append([InlineKeyboardButton(
                    f"👤 {user_name}",
                    callback_data=f"adm_request_view_{req['id']}"
                )])
            
            # Pagination
            total_pages = (total + 9) // 10
            if total_pages > 1:
                nav_buttons = format_pagination_buttons(page, total_pages, "adm_requests_list")
                keyboard.extend(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_requests_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_request_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: int):
        """Show request details"""
        query = update.callback_query
        await query.answer()
        
        # Get request from list
        requests, _ = self.db.list_requests(status='pending', page=1, per_page=100)
        request = next((r for r in requests if r['id'] == request_id), None)
        
        if not request:
            await query.edit_message_text("❌ Запрос не найден")
            return
        
        text = format_request_card(request)
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_request_approve_{request_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_request_reject_{request_id}")
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="adm_requests_list_1")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def approve_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: int):
        """Approve admin request"""
        query = update.callback_query
        await query.answer()
        
        user_id = self.db.approve_request(request_id, update.effective_user.id, role='staff')
        
        if user_id:
            # Log action
            self.db.log_action(update.effective_user.id, 'request_approve', user_id)
            await query.answer("✅ Запрос одобрен, админ добавлен", show_alert=True)
            
            # Return to requests list
            await self.show_requests_list(update, context, page=1)
        else:
            await query.answer("❌ Ошибка при одобрении запроса", show_alert=True)
    
    async def reject_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: int):
        """Reject admin request"""
        query = update.callback_query
        await query.answer()
        
        if self.db.reject_request(request_id, update.effective_user.id):
            # Log action
            self.db.log_action(update.effective_user.id, 'request_reject')
            await query.answer("✅ Запрос отклонён", show_alert=True)
            
            # Return to requests list
            await self.show_requests_list(update, context, page=1)
        else:
            await query.answer("❌ Ошибка при отклонении запроса", show_alert=True)
    
    async def show_invites_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
        """Show invites list"""
        query = update.callback_query
        await query.answer()
        
        invites, total = self.db.list_invites(status='pending', page=page, per_page=10)
        
        if not invites:
            text = "📭 Нет активных приглашений"
            keyboard = [
                [InlineKeyboardButton("📨 Создать приглашение", callback_data="adm_invite_create_start")],
                [InlineKeyboardButton("◀️ Назад", callback_data="adm_requests_main")]
            ]
        else:
            text = f"🔗 Приглашения\n━━━━━━━━━━━━━━━━━━━━\nВсего: {total}\n"
            
            keyboard = []
            for invite in invites:
                target = invite.get('target_username') or 'любой'
                role = format_role_name(invite.get('role_default', 'staff'))
                keyboard.append([InlineKeyboardButton(
                    f"@{target} → {role}",
                    callback_data=f"adm_invite_view_{invite['id']}"
                )])
            
            # Pagination
            total_pages = (total + 9) // 10
            if total_pages > 1:
                nav_buttons = format_pagination_buttons(page, total_pages, "adm_invites_list")
                keyboard.extend(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("📨 Создать", callback_data="adm_invite_create_start")])
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_requests_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_invite_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE, invite_id: int):
        """Show invite details"""
        query = update.callback_query
        await query.answer()
        
        # Get invite
        invites, _ = self.db.list_invites(status='pending', page=1, per_page=100)
        invite = next((i for i in invites if i['id'] == invite_id), None)
        
        if not invite:
            await query.edit_message_text("❌ Приглашение не найдено")
            return
        
        # Get creator name
        creator = self.db.get_admin(invite['created_by'])
        creator_name = format_admin_display_name(creator) if creator else None
        
        text = format_invite_card(invite, creator_name)
        
        # Add invite link
        if self.bot_username:
            invite_link = f"https://t.me/{self.bot_username}?start=admin_invite_{invite['token']}"
            text += f"\n\n🔗 Ссылка:\n{invite_link}"
        
        keyboard = [
            [InlineKeyboardButton("🚫 Отозвать", callback_data=f"adm_invite_revoke_{invite_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="adm_invites_list_1")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def start_create_invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start creating invite"""
        query = update.callback_query
        await query.answer()
        
        text = """📨 Создать приглашение
━━━━━━━━━━━━━━━━━━━━
Выберите роль для нового админа:"""
        
        keyboard = []
        for role in ['staff', 'moderator', 'manager']:
            emoji = format_role_emoji(role)
            name = format_role_name(role)
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {name}",
                callback_data=f"adm_invite_create_{role}"
            )])
        
        keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data="adm_invites_list_1")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def create_invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE, role: str):
        """Create invite"""
        query = update.callback_query
        await query.answer()
        
        token = self.db.create_invite(
            update.effective_user.id,
            role_default=role,
            expires_hours=72  # 3 days
        )
        
        if token:
            # Log action
            self.db.log_action(
                update.effective_user.id,
                'invite_create',
                details={'role': role, 'token': token}
            )
            
            # Generate invite link
            invite_link = f"https://t.me/{self.bot_username}?start=admin_invite_{token}" if self.bot_username else token
            
            text = f"""✅ Приглашение создано!
━━━━━━━━━━━━━━━━━━━━
🔖 Роль: {format_role_emoji(role)} {format_role_name(role)}
⏰ Действует: 72 часа

🔗 Ссылка для приглашения:
{invite_link}

Отправьте эту ссылку новому админу."""
            
            keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data="adm_invites_list_1")]]
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("❌ Ошибка при создании приглашения", show_alert=True)
    
    async def revoke_invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE, invite_id: int):
        """Revoke invite"""
        query = update.callback_query
        await query.answer()
        
        if self.db.revoke_invite(invite_id):
            # Log action
            self.db.log_action(update.effective_user.id, 'invite_revoke')
            await query.answer("✅ Приглашение отозвано", show_alert=True)
            
            # Return to invites list
            await self.show_invites_list(update, context, page=1)
        else:
            await query.answer("❌ Ошибка при отзыве приглашения", show_alert=True)
    
    # ===== Utility =====
    
    # ===== Edit Name =====
    
    async def start_edit_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Start editing admin's display name"""
        query = update.callback_query
        await query.answer()
        
        admin = self.db.get_admin(user_id)
        if not admin:
            await query.edit_message_text("❌ Админ не найден")
            return ConversationHandler.END
        
        # Store user_id in context for later
        context.user_data['editing_admin_id'] = user_id
        
        current_name = admin.get('full_name') or admin.get('username') or str(user_id)
        
        text = f"""✏️ Редактирование имени
━━━━━━━━━━━━━━━━━━━━
Админ: {current_name}
ID: {user_id}

Введите новое отображаемое имя:
(Это имя будет видно в списке админов)

Отправьте /cancel для отмены"""
        
        await query.edit_message_text(text)
        return WAITING_EDIT_NAME
    
    async def receive_edit_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive new name and update admin"""
        new_name = update.message.text.strip()
        user_id = context.user_data.get('editing_admin_id')
        
        if not user_id:
            await update.message.reply_text("❌ Ошибка: не найден ID админа")
            return ConversationHandler.END
        
        if not new_name or len(new_name) > 100:
            await update.message.reply_text(
                "❌ Неверное имя. Должно быть от 1 до 100 символов.\nПопробуйте снова или /cancel",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Отмена", callback_data=f"adm_view_{user_id}")
                ]])
            )
            return WAITING_EDIT_NAME
        
        # Update admin's full_name
        admin = self.db.get_admin(user_id)
        if admin:
            success = self.db.add_admin(
                user_id=user_id,
                username=admin.get('username'),
                full_name=new_name,
                role=admin.get('role', 'staff'),
                added_by=admin.get('added_by', 0),
                active=admin.get('active', 1)
            )
            
            if success:
                # Log action
                self.db.log_action(
                    update.effective_user.id,
                    'edit_name',
                    user_id,
                    {'new_name': new_name}
                )
                
                await update.message.reply_text(
                    f"✅ Имя обновлено: {new_name}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("👁️ Просмотр", callback_data=f"adm_view_{user_id}"),
                        InlineKeyboardButton("◀️ К списку", callback_data="adm_list_1")
                    ]])
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка при обновлении имени",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Назад", callback_data=f"adm_view_{user_id}")
                    ]])
                )
        else:
            await update.message.reply_text("❌ Админ не найден")
        
        # Clear context
        context.user_data.pop('editing_admin_id', None)
        return ConversationHandler.END
    
    # ===== Utility =====
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation"""
        await update.message.reply_text(
            "❌ Отменено",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ К меню", callback_data="adm_menu")
            ]])
        )
        return ConversationHandler.END
    
    # ===== Salary Settings =====
    
    async def show_salary_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show salary settings for admin (owner only)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(update.effective_user.id):
            await query.edit_message_text("❌ Доступ только для владельца")
            return
        
        try:
            admin = self.db.get_admin(user_id)
            if not admin:
                await query.edit_message_text("❌ Администратор не найден")
                return
            
            admin_name = admin.get('full_name') or admin.get('username') or f"ID {user_id}"
            settings = self.db.get_salary_settings(user_id)
            
            # Format employment type
            emp_type_names = {
                'self_employed': 'Самозанятый',
                'staff': 'Штат',
                'gpc': 'ГПХ'
            }
            emp_type_display = emp_type_names.get(settings['employment_type'], settings['employment_type'])
            
            msg = f"💰 Настройки зарплаты\n\n"
            msg += f"👤 {admin_name}\n\n"
            msg += f"💼 Тип занятости: {emp_type_display}\n"
            msg += f"💵 Ставка за смену: {settings['salary_per_shift']:,.0f}₽\n"
            msg += f"📊 Налог: {settings['tax_rate']:.1f}%\n\n"
            msg += "Выберите что изменить:"
            
            keyboard = [
                [InlineKeyboardButton("💼 Тип занятости", callback_data=f"adm_salary_emp_{user_id}")],
                [InlineKeyboardButton("💵 Ставка за смену", callback_data=f"adm_salary_rate_{user_id}")],
                [InlineKeyboardButton("📊 Налог", callback_data=f"adm_salary_tax_{user_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"adm_view_{user_id}")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to show salary settings: {e}")
            await query.edit_message_text(f"❌ Ошибка при получении настроек: {e}")
    
    async def handle_salary_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle salary setting changes"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(update.effective_user.id):
            await query.edit_message_text("❌ Доступ только для владельца")
            return
        
        data = query.data
        parts = data.split('_')
        
        if len(parts) < 4:
            await query.edit_message_text("❌ Ошибка данных")
            return
        
        setting_type = parts[2]
        user_id = int(parts[3])
        
        try:
            admin = self.db.get_admin(user_id)
            admin_name = admin.get('full_name') or admin.get('username') or f"ID {user_id}"
            
            if setting_type == "emp":
                msg = f"💼 Тип занятости\n\n"
                msg += f"👤 {admin_name}\n\n"
                msg += "Выберите тип занятости:"
                
                keyboard = [
                    [InlineKeyboardButton("👤 Самозанятый (6% налог)", callback_data=f"adm_salary_set_emp_self_{user_id}")],
                    [InlineKeyboardButton("🏢 Штат (30% налог)", callback_data=f"adm_salary_set_emp_staff_{user_id}")],
                    [InlineKeyboardButton("📋 ГПХ (15% налог)", callback_data=f"adm_salary_set_emp_gpc_{user_id}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"adm_salary_{user_id}")]
                ]
                
            elif setting_type == "rate":
                msg = f"💵 Ставка за смену\n\n"
                msg += f"👤 {admin_name}\n\n"
                msg += "Выберите ставку:"
                
                keyboard = [
                    [InlineKeyboardButton("1,000₽", callback_data=f"adm_salary_set_rate_1000_{user_id}")],
                    [InlineKeyboardButton("1,500₽", callback_data=f"adm_salary_set_rate_1500_{user_id}")],
                    [InlineKeyboardButton("2,000₽", callback_data=f"adm_salary_set_rate_2000_{user_id}")],
                    [InlineKeyboardButton("2,500₽", callback_data=f"adm_salary_set_rate_2500_{user_id}")],
                    [InlineKeyboardButton("3,000₽", callback_data=f"adm_salary_set_rate_3000_{user_id}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"adm_salary_{user_id}")]
                ]
                
            elif setting_type == "tax":
                msg = f"📊 Налог\n\n"
                msg += f"👤 {admin_name}\n\n"
                msg += "Выберите налог (0 = по умолчанию):"
                
                keyboard = [
                    [InlineKeyboardButton("0% (по умолчанию)", callback_data=f"adm_salary_set_tax_0_{user_id}")],
                    [InlineKeyboardButton("6%", callback_data=f"adm_salary_set_tax_6_{user_id}")],
                    [InlineKeyboardButton("15%", callback_data=f"adm_salary_set_tax_15_{user_id}")],
                    [InlineKeyboardButton("30%", callback_data=f"adm_salary_set_tax_30_{user_id}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"adm_salary_{user_id}")]
                ]
            
            else:
                await query.edit_message_text("❌ Неверный тип настройки")
                return
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Failed to handle salary setting: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")
    
    async def apply_salary_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Apply salary setting change"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(update.effective_user.id):
            await query.edit_message_text("❌ Доступ только для владельца")
            return
        
        data = query.data
        parts = data.split('_')
        
        if len(parts) < 5:
            await query.edit_message_text("❌ Ошибка данных")
            return
        
        setting_type = parts[3]
        value = parts[4]
        user_id = int(parts[5])
        
        try:
            admin = self.db.get_admin(user_id)
            admin_name = admin.get('full_name') or admin.get('username') or f"ID {user_id}"
            
            success = False
            
            if setting_type == "emp":
                emp_type_map = {
                    'self': 'self_employed',
                    'staff': 'staff',
                    'gpc': 'gpc'
                }
                emp_type = emp_type_map.get(value)
                if emp_type:
                    success = self.db.set_employment_type(user_id, emp_type)
                    setting_name = f"тип занятости на {value}"
                    
            elif setting_type == "rate":
                amount = float(value)
                success = self.db.set_salary_per_shift(user_id, amount)
                setting_name = f"ставку на {amount:,.0f}₽"
                
            elif setting_type == "tax":
                rate = float(value)
                success = self.db.set_custom_tax_rate(user_id, rate)
                setting_name = f"налог на {rate}%"
            
            if success:
                await query.edit_message_text(
                    f"✅ Изменено {setting_name} для {admin_name}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"adm_salary_{user_id}")]])
                )
            else:
                await query.edit_message_text(f"❌ Не удалось изменить {setting_name}")
                
        except Exception as e:
            logger.error(f"Failed to apply salary setting: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")
