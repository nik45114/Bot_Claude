# V2Ray User Management Workflow

## 1. View All Users Workflow

```
User Action: /v2ray → Серверы → [Select Server] → Пользователи
     ↓
bot.py: _show_server_users()
     ↓
v2ray_manager.py: get_users(server_name)
     ↓
SSH Connect to Server
     ↓
Read /usr/local/etc/xray/config.json
     ↓
Parse clients[] array
     ↓
Return list of ALL users
     ↓
Display in Telegram with buttons
```

**Key Improvement**: Now reads from actual server config, not just database!

---

## 2. Delete User Workflow

```
User Action: Click on user → 🗑️ Удалить → ✅ Да, удалить
     ↓
bot.py: _confirm_delete_user()
     ↓
v2ray_manager.py: delete_user(server_name, uuid)
     ↓
┌─────────────────────────────────┐
│ Step 1: Delete from Server      │
├─────────────────────────────────┤
│ • SSH Connect                   │
│ • Read config.json              │
│ • Remove user from clients[]    │
│ • Save config.json              │
│ • systemctl restart xray        │
└─────────────────────────────────┘
     ↓
┌─────────────────────────────────┐
│ Step 2: Delete from Database    │
├─────────────────────────────────┤
│ • DELETE FROM v2ray_users       │
│ • DELETE FROM v2ray_temp_access │
└─────────────────────────────────┘
     ↓
Success! User completely removed
```

**Key Improvement**: Now deletes from BOTH server and database!

---

## 3. Temporary Access Workflow

### Setting Temporary Access

```
User Action: Click user → ⏰ Временный доступ → Select days (e.g., 7 дней)
     ↓
bot.py: _set_temp_access(server_name, uuid, days=7)
     ↓
Calculate expires_at = now + 7 days
     ↓
v2ray_manager.py: set_temp_access(server_name, uuid, expires_at)
     ↓
INSERT INTO v2ray_temp_access (server_name, uuid, expires_at)
     ↓
Display confirmation with expiration date
```

### Checking Expiration

```
Automated Background Process (scheduled)
     ↓
v2ray_manager.py: cleanup_expired_users()
     ↓
get_expired_users() → Find users where expires_at < now
     ↓
For each expired user:
     ↓
delete_user(server_name, uuid)
     ↓
User removed from server and database
```

**Key Feature**: Automatic lifecycle management!

---

## 4. User Detail View Workflow

```
User Action: Click on user in list
     ↓
bot.py: _show_user_detail(server_name, uuid)
     ↓
┌─────────────────────────────────┐
│ Fetch Data:                     │
├─────────────────────────────────┤
│ • Get user from server config   │
│ • Get temp access from DB       │
│ • Calculate days remaining      │
└─────────────────────────────────┘
     ↓
Display User Details:
━━━━━━━━━━━━━━━━━━━━━━
📧 Email: user@example.com
🔑 UUID: 12345678-1234-...
⚡ Flow: xtls-rprx-vision
🖥️ Сервер: main
⏰ Истекает: 2024-10-25 12:00
   Осталось: 7 дней
━━━━━━━━━━━━━━━━━━━━━━

[⏰ Временный доступ] [🗑️ Удалить]
[◀️ К списку]
```

---

## 5. Database Schema

```
┌─────────────────────────────────────────┐
│ v2ray_servers                           │
├─────────────────────────────────────────┤
│ id, name, host, port, username,         │
│ password, sni, public_key, private_key, │
│ short_id, is_active, created_at         │
└─────────────────────────────────────────┘
              ↓ (FOREIGN KEY)
┌─────────────────────────────────────────┐
│ v2ray_users                             │
├─────────────────────────────────────────┤
│ id, server_name, user_id, uuid,         │
│ comment, sni, is_active, created_at     │
└─────────────────────────────────────────┘
              ↓ (FOREIGN KEY)
┌─────────────────────────────────────────┐
│ v2ray_temp_access          (NEW!)       │
├─────────────────────────────────────────┤
│ id, server_name, uuid, expires_at,      │
│ created_at                              │
└─────────────────────────────────────────┘
```

---

## 6. User Interface Flow

```
Main Menu (/v2ray)
    │
    ├─ 📡 Серверы
    │   │
    │   └─ [Server Name]
    │       │
    │       ├─ 👥 Пользователи ────────────────┐
    │       │   │                              │
    │       │   ├─ [User 1] ──→ User Detail   │
    │       │   │   │                          │
    │       │   │   ├─ ⏰ Временный доступ     │ NEW!
    │       │   │   │   │                      │
    │       │   │   │   ├─ 1 день              │
    │       │   │   │   ├─ 3 дня               │
    │       │   │   │   ├─ 7 дней              │
    │       │   │   │   ├─ 14 дней             │
    │       │   │   │   ├─ 30 дней             │
    │       │   │   │   └─ 90 дней             │
    │       │   │   │                          │
    │       │   │   ├─ 🗑️ Удалить              │ IMPROVED!
    │       │   │   │   └─ ✅ Да, удалить      │
    │       │   │   │                          │
    │       │   │   └─ ◀️ К списку             │
    │       │   │                              │
    │       │   ├─ [User 2]                    │ NEW!
    │       │   ├─ [User 3]                    │ Shows ALL
    │       │   │                              │ users from
    │       │   ├─ ➕ Добавить                  │ server!
    │       │   └─ 🔄 Обновить                 │
    │       │
    │       ├─ ➕ Добавить
    │       ├─ 🔧 Установить Xray
    │       ├─ 🔍 Диагностика
    │       ├─ 📊 Статистика
    │       └─ 🗑️ Удалить сервер
    │
    ├─ 👤 Пользователи
    └─ 📖 Справка по командам
```

---

## Benefits Summary

### Before
- ❌ Only showed users in database
- ❌ Delete only removed from database
- ❌ No temporary access
- ❌ Limited user information

### After
- ✅ Shows ALL users from server config
- ✅ Delete removes from server AND database
- ✅ Temporary access with auto-expiration
- ✅ Detailed user information and management
- ✅ Interactive UI with confirmation dialogs
- ✅ Automatic cleanup of expired users

---

## Security Features

1. **Owner-only access**: Only bot owner can manage users
2. **Confirmation dialogs**: Prevents accidental deletions
3. **SSH security**: Secure connections to servers
4. **Database integrity**: Foreign key constraints
5. **Audit trail**: created_at timestamps for tracking
