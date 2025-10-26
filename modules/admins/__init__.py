#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Management Module
Registers handlers and provides integration with the bot
"""

from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from telegram import Update
from telegram.ext import ContextTypes
import os
import re
from typing import List

from .db import AdminDB
from .wizard import (
    AdminWizard, WAITING_USERNAME, WAITING_BULK_USERNAMES, WAITING_NOTES,
    WAITING_SEARCH_QUERY, WAITING_INVITE_ROLE, WAITING_REQUEST_MESSAGE
)


def get_owner_ids_from_env() -> List[int]:
    """Get owner IDs from environment variable"""
    owner_ids_str = os.getenv('OWNER_TG_IDS', '')
    if owner_ids_str:
        try:
            return [int(id.strip()) for id in owner_ids_str.split(',') if id.strip()]
        except ValueError:
            pass
    return []


def register_admins(application: Application, config: dict, db_path: str, bot_username: str = None):
    """
    Register admin management handlers with the bot
    
    Args:
        application: Telegram bot application
        config: Bot configuration dict
        db_path: Path to SQLite database
        bot_username: Bot username for generating invite links
    """
    
    # Initialize database and wizard
    admin_db = AdminDB(db_path)
    
    # Get owner IDs from env or config
    owner_ids = get_owner_ids_from_env()
    if not owner_ids and config.get('owner_id'):
        owner_ids = [config['owner_id']]
    elif not owner_ids and config.get('admin_ids'):
        # Fallback to first admin if no owner specified
        owner_ids = [config['admin_ids'][0]]
    
    wizard = AdminWizard(admin_db, owner_ids, bot_username)
    
    # ===== Command Handlers =====
    
    async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin management menu"""
        await wizard.show_menu(update, context)
    
    async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Promote user from reply (owner only)"""
        user_id = update.effective_user.id
        
        if not wizard.is_owner(user_id):
            await update.message.reply_text("❌ Эта команда доступна только владельцу")
            return
        
        # Check if reply to message
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Используйте эту команду ответом на сообщение пользователя\n"
                "Например: ответьте на сообщение и напишите /promote"
            )
            return
        
        # Get user from replied message
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
        target_username = target_user.username
        target_full_name = target_user.full_name
        
        # Add admin
        success = admin_db.add_admin(
            target_user_id,
            username=target_username,
            full_name=target_full_name,
            role='staff',
            added_by=user_id,
            active=1
        )
        
        if success:
            # Log action
            admin_db.log_action(user_id, 'add', target_user_id, {
                'method': 'promote',
                'username': target_username
            })
            
            display_name = target_full_name or f"@{target_username}" if target_username else f"ID: {target_user_id}"
            await update.message.reply_text(
                f"✅ {display_name} добавлен как админ (роль: staff)\n\n"
                f"Используйте /admins для управления правами"
            )
        else:
            await update.message.reply_text("❌ Ошибка при добавлении админа")
    
    async def cmd_request_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Request admin access"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        full_name = update.effective_user.full_name
        
        # Check if already admin
        if admin_db.is_active(user_id):
            await update.message.reply_text("ℹ️ Вы уже являетесь админом")
            return
        
        # Get message if provided
        message = ' '.join(context.args) if context.args else None
        
        # Create request
        success = admin_db.create_request(user_id, username, full_name, message)
        
        if success:
            await update.message.reply_text(
                "✅ Запрос на админа отправлен\n\n"
                "Владелец рассмотрит ваш запрос в ближайшее время."
            )
        else:
            await update.message.reply_text(
                "ℹ️ Ваш запрос уже находится на рассмотрении\n\n"
                "Дождитесь решения владельца."
            )
    
    async def handle_admin_invite(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
        """Handle admin invite from deep link"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        full_name = update.effective_user.full_name
        
        # Check if already admin
        if admin_db.is_active(user_id):
            await update.message.reply_text("ℹ️ Вы уже являетесь админом")
            return
        
        # Get invite
        invite = admin_db.get_invite(token)
        
        if not invite:
            await update.message.reply_text("❌ Приглашение не найдено")
            return
        
        if invite['status'] != 'pending':
            status_messages = {
                'accepted': 'Это приглашение уже было использовано',
                'expired': 'Это приглашение истекло',
                'revoked': 'Это приглашение было отозвано'
            }
            await update.message.reply_text(f"❌ {status_messages.get(invite['status'], 'Приглашение недействительно')}")
            return
        
        # Check if invite is for specific username
        if invite['target_username'] and invite['target_username'] != username:
            await update.message.reply_text(
                f"❌ Это приглашение предназначено для @{invite['target_username']}"
            )
            return
        
        # Check expiration
        if invite.get('expires_at'):
            from datetime import datetime
            try:
                expires_at = datetime.strptime(invite['expires_at'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() > expires_at:
                    admin_db.update_invite_status(token, 'expired')
                    await update.message.reply_text("❌ Приглашение истекло")
                    return
            except ValueError:
                pass
        
        # Add admin
        role = invite.get('role_default', 'staff')
        success = admin_db.add_admin(
            user_id,
            username=username,
            full_name=full_name,
            role=role,
            added_by=invite['created_by'],
            active=1
        )
        
        if success:
            # Update invite status
            admin_db.update_invite_status(token, 'accepted')
            
            # Log action
            admin_db.log_action(invite['created_by'], 'add', user_id, {
                'method': 'invite',
                'token': token,
                'role': role
            })
            
            from .formatters import format_role_emoji, format_role_name
            role_emoji = format_role_emoji(role)
            role_name = format_role_name(role)
            
            await update.message.reply_text(
                f"✅ Вы добавлены как админ!\n\n"
                f"🔖 Ваша роль: {role_emoji} {role_name}\n\n"
                f"Используйте /help для просмотра доступных команд"
            )
        else:
            await update.message.reply_text("❌ Ошибка при активации приглашения")
    
    # ===== Callback Query Router =====
    
    async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route callback queries to appropriate handlers"""
        query = update.callback_query
        data = query.data
        
        # Admin menu and navigation
        if data == "adm_menu":
            await wizard.show_menu(update, context)
        elif data == "adm_close":
            await wizard.close_menu(update, context)
        
        # Add admin flows
        elif data == "adm_add_main":
            await wizard.show_add_menu(update, context)
        elif data == "adm_add_by_username":
            await wizard.start_add_by_username(update, context)
        elif data == "adm_add_bulk":
            await wizard.start_add_bulk(update, context)
        
        # Admin list and view
        elif data.startswith("adm_list_"):
            # Parse: adm_list_<page> or adm_list_active_<active>_<page>
            parts = data.split('_')
            if len(parts) == 3:  # adm_list_<page>
                page = int(parts[2])
                await wizard.show_admin_list(update, context, page=page)
            elif len(parts) == 5 and parts[2] == 'active':  # adm_list_active_<active>_<page>
                active = int(parts[3])
                page = int(parts[4])
                await wizard.show_admin_list(update, context, page=page, active=active)
        
        elif data.startswith("adm_view_"):
            user_id = int(data.split('_')[2])
            await wizard.show_admin_view(update, context, user_id)
        
        # Role management
        elif data.startswith("adm_set_role_"):
            user_id = int(data.split('_')[3])
            await wizard.show_role_selection(update, context, user_id)
        elif data.startswith("adm_setrole_"):
            parts = data.split('_')
            user_id = int(parts[2])
            role = parts[3]
            await wizard.set_role(update, context, user_id, role)
        
        # Permission management
        elif data.startswith("adm_perms_"):
            user_id = int(data.split('_')[2])
            await wizard.show_permissions(update, context, user_id)
        elif data.startswith("adm_toggleperm_"):
            parts = data.split('_')
            user_id = int(parts[2])
            permission = parts[3]
            value = bool(int(parts[4]))
            await wizard.toggle_permission(update, context, user_id, permission, value)
        elif data.startswith("adm_resetperms_"):
            user_id = int(data.split('_')[2])
            await wizard.reset_permissions(update, context, user_id)
        
        # Activate/Deactivate
        elif data.startswith("adm_activate_"):
            user_id = int(data.split('_')[2])
            await wizard.activate_admin(update, context, user_id)
        elif data.startswith("adm_deactivate_"):
            user_id = int(data.split('_')[2])
            await wizard.deactivate_admin(update, context, user_id)
        
        # Remove admin
        elif data.startswith("adm_remove_confirm_"):
            user_id = int(data.split('_')[3])
            await wizard.show_remove_confirm(update, context, user_id)
        elif data.startswith("adm_remove_do_"):
            user_id = int(data.split('_')[3])
            await wizard.remove_admin(update, context, user_id)
        
        # Search
        elif data == "adm_search_start":
            await wizard.start_search(update, context)
        
        # Requests and invites
        elif data == "adm_requests_main":
            await wizard.show_requests_main(update, context)
        elif data.startswith("adm_requests_list_"):
            page = int(data.split('_')[3])
            await wizard.show_requests_list(update, context, page)
        elif data.startswith("adm_request_view_"):
            request_id = int(data.split('_')[3])
            await wizard.show_request_view(update, context, request_id)
        elif data.startswith("adm_request_approve_"):
            request_id = int(data.split('_')[3])
            await wizard.approve_request(update, context, request_id)
        elif data.startswith("adm_request_reject_"):
            request_id = int(data.split('_')[3])
            await wizard.reject_request(update, context, request_id)
        
        # Invites
        elif data.startswith("adm_invites_list_"):
            page = int(data.split('_')[3])
            await wizard.show_invites_list(update, context, page)
        elif data.startswith("adm_invite_view_"):
            invite_id = int(data.split('_')[3])
            await wizard.show_invite_view(update, context, invite_id)
        elif data == "adm_invite_create_start":
            await wizard.start_create_invite(update, context)
        elif data.startswith("adm_invite_create_"):
            role = data.split('_')[3]
            await wizard.create_invite(update, context, role)
        elif data.startswith("adm_invite_revoke_"):
            invite_id = int(data.split('_')[3])
            await wizard.revoke_invite(update, context, invite_id)
        elif data.startswith("adm_invite_for_"):
            # Create invite for specific username
            username = data.split('_', 3)[3]
            token = admin_db.create_invite(
                update.effective_user.id,
                target_username=username,
                role_default='staff',
                expires_hours=72
            )
            if token:
                admin_db.log_action(
                    update.effective_user.id,
                    'invite_create',
                    details={'username': username, 'token': token}
                )
                
                invite_link = f"https://t.me/{bot_username}?start=admin_invite_{token}" if bot_username else token
                await query.edit_message_text(
                    f"✅ Приглашение создано для @{username}\n\n"
                    f"🔗 Ссылка:\n{invite_link}\n\n"
                    f"Отправьте эту ссылку пользователю.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ К меню", callback_data="adm_menu")
                    ]])
                )
            else:
                await query.answer("❌ Ошибка при создании приглашения", show_alert=True)
    
    # ===== Conversation Handlers =====
    
    # Add admin by username
    add_by_username_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(wizard.start_add_by_username, pattern="^adm_add_by_username$")],
        states={
            WAITING_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.receive_username)]
        },
        fallbacks=[CommandHandler("cancel", wizard.cancel)]
    )
    
    # Bulk add admins
    bulk_add_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(wizard.start_add_bulk, pattern="^adm_add_bulk$")],
        states={
            WAITING_BULK_USERNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.receive_bulk_usernames)]
        },
        fallbacks=[CommandHandler("cancel", wizard.cancel)]
    )
    
    # Search admins
    search_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(wizard.start_search, pattern="^adm_search_start$")],
        states={
            WAITING_SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.receive_search)]
        },
        fallbacks=[CommandHandler("cancel", wizard.cancel)]
    )
    
    # ===== Register Handlers =====
    
    # Commands
    application.add_handler(CommandHandler("admins", cmd_admins))
    application.add_handler(CommandHandler("promote", cmd_promote))
    application.add_handler(CommandHandler("request_admin", cmd_request_admin))
    
    # Conversation handlers (must be before callback query handler)
    application.add_handler(add_by_username_handler)
    application.add_handler(bulk_add_handler)
    application.add_handler(search_handler)
    
    # Callback query handler for all adm_ callbacks
    application.add_handler(CallbackQueryHandler(callback_router, pattern="^adm_"))
    
    # Modify /start command to handle admin invites
    # This is done by wrapping the existing start handler
    # We'll need to check for admin_invite_ in the start args
    
    # Create a middleware to intercept /start with admin_invite
    async def start_interceptor(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Intercept /start to handle admin invites"""
        if context.args and len(context.args) > 0:
            arg = context.args[0]
            if arg.startswith('admin_invite_'):
                token = arg.replace('admin_invite_', '')
                await handle_admin_invite(update, context, token)
                return True  # Handled
        return False  # Not handled, pass to original handler
    
    # Store the interceptor for use in bot.py
    context_key = 'admin_invite_interceptor'
    application.bot_data[context_key] = start_interceptor
    
    return admin_db, wizard
