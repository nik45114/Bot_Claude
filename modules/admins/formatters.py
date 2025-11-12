#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Management UI Formatters
Formats admin cards, lists, and UI elements for the Telegram bot
"""

from typing import List, Dict, Optional
from datetime import datetime


def format_admin_display_name(admin: Dict) -> str:
    """Get display name for admin with priority: full_name > username > user_id"""
    if admin.get('full_name'):
        return admin['full_name']
    if admin.get('username'):
        return f"@{admin['username']}"
    return f"ID: {admin['user_id']}"


def format_role_emoji(role: str) -> str:
    """Get emoji for role"""
    role_emojis = {
        'owner': '👑',
        'manager': '🔑',
        'moderator': '⚔️',
        'staff': '👤'
    }
    return role_emojis.get(role, '👤')


def format_role_name(role: str) -> str:
    """Get display name for role"""
    role_names = {
        'owner': 'Владелец',
        'manager': 'Менеджер',
        'moderator': 'Модератор',
        'staff': 'Сотрудник'
    }
    return role_names.get(role, 'Сотрудник')


def format_permission_name(permission: str) -> str:
    """Get display name for permission"""
    permission_names = {
        'cash_view': '💰 Просмотр финансов',
        'cash_edit': '💵 Управление финансами',
        'products_view': '📦 Просмотр товаров',
        'products_edit': '✏️ Управление товарами',
        'issues_view': '🐛 Просмотр проблем',
        'issues_edit': '🔧 Управление проблемами',
        'v2ray_view': '🔐 Просмотр VPN',
        'v2ray_manage': '🛡️ Управление VPN',
        'content_generate': '🎨 Генерация контента',
        'can_manage_admins': '👥 Управление админами'
    }
    return permission_names.get(permission, permission)


def format_admin_card(admin: Dict, permissions: Dict[str, bool] = None) -> str:
    """Format admin card with all details"""
    lines = []
    
    # Header
    role_emoji = format_role_emoji(admin.get('role', 'staff'))
    role_name = format_role_name(admin.get('role', 'staff'))
    display_name = format_admin_display_name(admin)
    
    lines.append(f"{role_emoji} {display_name}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    
    # Basic info
    lines.append(f"🔖 Роль: {role_name}")
    
    if admin.get('username'):
        lines.append(f"👤 Username: @{admin['username']}")
    
    lines.append(f"🆔 ID: {admin['user_id']}")

    # Gender
    gender = admin.get('gender')
    if gender == 'male':
        lines.append(f"⚧ Пол: ♂️ Мужской")
    elif gender == 'female':
        lines.append(f"⚧ Пол: ♀️ Женский")
    else:
        lines.append(f"⚧ Пол: не указан")

    # Status
    status = "✅ Активен" if admin.get('active', 1) == 1 else "❌ Деактивирован"
    lines.append(f"📊 Статус: {status}")
    
    # Permissions
    if permissions:
        lines.append("")
        lines.append("🔐 Права доступа:")
        
        perm_groups = {
            '💰 Финансы': ['cash_view', 'cash_edit'],
            '📦 Товары': ['products_view', 'products_edit'],
            '🐛 Проблемы': ['issues_view', 'issues_edit'],
            '🔐 VPN': ['v2ray_view', 'v2ray_manage'],
            '🎨 Контент': ['content_generate'],
            '👥 Админы': ['can_manage_admins']
        }
        
        for group_name, group_perms in perm_groups.items():
            group_status = []
            for perm in group_perms:
                if perm in permissions:
                    status_emoji = "✅" if permissions[perm] else "❌"
                    group_status.append(status_emoji)
            
            if group_status:
                status_str = " ".join(group_status)
                lines.append(f"  {group_name}: {status_str}")
    
    # Notes
    if admin.get('notes'):
        lines.append("")
        lines.append(f"📝 Заметки: {admin['notes']}")
    
    # Timestamps
    if admin.get('created_at'):
        created = format_datetime(admin['created_at'])
        lines.append("")
        lines.append(f"📅 Добавлен: {created}")
    
    if admin.get('updated_at'):
        updated = format_datetime(admin['updated_at'])
        lines.append(f"🔄 Обновлён: {updated}")
    
    return '\n'.join(lines)


def format_admin_list_item(admin: Dict, index: int) -> str:
    """Format single admin in a list"""
    role_emoji = format_role_emoji(admin.get('role', 'staff'))
    display_name = format_admin_display_name(admin)
    status = "✅" if admin.get('active', 1) == 1 else "❌"
    
    return f"{index}. {role_emoji} {display_name} {status}"


def format_admin_list(admins: List[Dict], page: int, total: int, per_page: int = 20) -> str:
    """Format list of admins with pagination info"""
    if not admins:
        return "📭 Список админов пуст"
    
    lines = []
    lines.append("👥 Список админов")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    start_idx = (page - 1) * per_page + 1
    for i, admin in enumerate(admins, start=start_idx):
        lines.append(format_admin_list_item(admin, i))
    
    # Pagination info
    total_pages = (total + per_page - 1) // per_page
    lines.append("")
    lines.append(f"📄 Страница {page}/{total_pages} (всего: {total})")
    
    return '\n'.join(lines)


def format_invite_card(invite: Dict, creator_name: str = None) -> str:
    """Format invite card"""
    lines = []
    
    lines.append("📨 Приглашение")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    
    # Status
    status_emojis = {
        'pending': '⏳',
        'accepted': '✅',
        'expired': '⏰',
        'revoked': '❌'
    }
    status_names = {
        'pending': 'Ожидает',
        'accepted': 'Принято',
        'expired': 'Истекло',
        'revoked': 'Отозвано'
    }
    
    status = invite.get('status', 'pending')
    status_emoji = status_emojis.get(status, '❓')
    status_name = status_names.get(status, status)
    
    lines.append(f"{status_emoji} Статус: {status_name}")
    
    # Role
    role_emoji = format_role_emoji(invite.get('role_default', 'staff'))
    role_name = format_role_name(invite.get('role_default', 'staff'))
    lines.append(f"{role_emoji} Роль: {role_name}")
    
    # Target username
    if invite.get('target_username'):
        lines.append(f"👤 Для: @{invite['target_username']}")
    
    # Creator
    if creator_name:
        lines.append(f"👨‍💼 Создал: {creator_name}")
    
    # Expiration
    if invite.get('expires_at'):
        expires = format_datetime(invite['expires_at'])
        lines.append(f"⏰ Истекает: {expires}")
    
    # Created
    if invite.get('created_at'):
        created = format_datetime(invite['created_at'])
        lines.append(f"📅 Создано: {created}")
    
    # Token (shortened)
    token = invite.get('token', '')
    short_token = f"{token[:8]}...{token[-8:]}" if len(token) > 16 else token
    lines.append("")
    lines.append(f"🔑 Токен: {short_token}")
    
    return '\n'.join(lines)


def format_request_card(request: Dict) -> str:
    """Format admin request card"""
    lines = []
    
    lines.append("📨 Запрос на админа")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    
    # User info
    if request.get('full_name'):
        lines.append(f"👤 Имя: {request['full_name']}")
    
    if request.get('username'):
        lines.append(f"📛 Username: @{request['username']}")
    
    lines.append(f"🆔 ID: {request['user_id']}")
    
    # Message
    if request.get('message'):
        lines.append("")
        lines.append(f"💬 Сообщение:\n{request['message']}")
    
    # Status
    status_emojis = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌'
    }
    status_names = {
        'pending': 'Ожидает',
        'approved': 'Одобрено',
        'rejected': 'Отклонено'
    }
    
    status = request.get('status', 'pending')
    status_emoji = status_emojis.get(status, '❓')
    status_name = status_names.get(status, status)
    
    lines.append("")
    lines.append(f"{status_emoji} Статус: {status_name}")
    
    # Timestamps
    if request.get('created_at'):
        created = format_datetime(request['created_at'])
        lines.append(f"📅 Создано: {created}")
    
    if request.get('reviewed_at'):
        reviewed = format_datetime(request['reviewed_at'])
        lines.append(f"✅ Рассмотрено: {reviewed}")
    
    return '\n'.join(lines)


def format_datetime(dt_str: str) -> str:
    """Format datetime string for display"""
    try:
        # Try parsing different datetime formats
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S']:
            try:
                dt = datetime.strptime(dt_str, fmt)
                return dt.strftime('%d.%m.%Y %H:%M')
            except ValueError:
                continue
        
        # If parsing fails, return original string
        return dt_str
    except Exception:
        return dt_str


def format_audit_log_entry(log: Dict, actor_name: str = None, target_name: str = None) -> str:
    """Format audit log entry"""
    action_emojis = {
        'add': '➕',
        'remove': '🗑️',
        'set_role': '🔖',
        'set_permissions': '🔐',
        'activate': '✅',
        'deactivate': '❌',
        'invite_create': '📨',
        'invite_revoke': '🚫',
        'request_approve': '✔️',
        'request_reject': '✖️'
    }
    
    action_names = {
        'add': 'Добавил админа',
        'remove': 'Удалил админа',
        'set_role': 'Изменил роль',
        'set_permissions': 'Изменил права',
        'activate': 'Активировал',
        'deactivate': 'Деактивировал',
        'invite_create': 'Создал приглашение',
        'invite_revoke': 'отозвал приглашение',
        'request_approve': 'Одобрил запрос',
        'request_reject': 'Отклонил запрос'
    }
    
    action = log.get('action', '')
    emoji = action_emojis.get(action, '📝')
    action_name = action_names.get(action, action)
    
    actor = actor_name or f"ID:{log.get('actor_user_id')}"
    target = target_name or f"ID:{log.get('target_user_id')}" if log.get('target_user_id') else ""
    
    timestamp = format_datetime(log.get('created_at', ''))
    
    result = f"{emoji} {actor} — {action_name}"
    if target:
        result += f" ({target})"
    
    result += f"\n   📅 {timestamp}"
    
    # Add details if present
    if log.get('details'):
        details = log['details']
        if isinstance(details, dict):
            detail_str = ', '.join([f"{k}: {v}" for k, v in details.items()])
            if detail_str:
                result += f"\n   ℹ️ {detail_str}"
    
    return result


def format_pagination_buttons(page: int, total_pages: int, callback_prefix: str) -> List[List]:
    """Generate pagination button layout"""
    buttons = []
    nav_row = []
    
    if page > 1:
        nav_row.append({"text": "⬅️ Пред.", "callback_data": f"{callback_prefix}_{page - 1}"})
    
    nav_row.append({"text": f"📄 {page}/{total_pages}", "callback_data": "noop"})
    
    if page < total_pages:
        nav_row.append({"text": "След. ➡️", "callback_data": f"{callback_prefix}_{page + 1}"})
    
    if nav_row:
        buttons.append(nav_row)
    
    return buttons
