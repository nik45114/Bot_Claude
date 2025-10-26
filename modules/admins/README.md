# Admin Management Module

## Overview

The Admin Management Module provides a comprehensive system for managing bot administrators with roles, permissions, invites, and audit logging. It includes a user-friendly Telegram interface for all administrative operations.

## Features

### 1. Role-Based Access Control

Four predefined roles with different permission levels:
- **👑 Owner** - Full access to all features
- **🔑 Manager** - Can manage finances, products, issues, and content
- **⚔️ Moderator** - Can view finances, manage products and issues
- **👤 Staff** - Basic access to view products and issues

### 2. Granular Permissions

Individual permission flags that can override role defaults:
- `cash_view`, `cash_edit` - Financial monitoring
- `products_view`, `products_edit` - Product management
- `issues_view`, `issues_edit` - Issue tracking
- `v2ray_view`, `v2ray_manage` - VPN management
- `content_generate` - AI content generation
- `can_manage_admins` - Admin management

### 3. Multiple Admin Onboarding Methods

- **By @username** - Add admins by their Telegram username (creates pending entry until user interacts with bot)
- **By reply (/promote)** - Reply to a user's message with `/promote` command
- **Invite links** - Generate deep-link invites with default role and expiration
- **Admin requests** - Users can request admin access via `/request_admin`
- **Bulk add** - Add multiple admins at once by pasting usernames

### 4. Admin Management UI

Accessible via `/admins` command or "👥 Управление админами" button (owner only):
- 📋 **List admins** - Paginated list with filters (active/inactive, by role)
- 🔎 **Search** - Find admins by username, name, or ID
- 👁️ **View admin** - Detailed admin card with all information
- ⚙️ **Manage** - Change role, toggle permissions, activate/deactivate, add notes
- 🗑️ **Remove** - Delete admin (with confirmation)

### 5. Invites and Requests

- Create invite links with custom role and expiration
- View pending invites and revoke them
- Review and approve/reject admin requests
- Automatic invite expiration

### 6. Audit Logging

All admin actions are logged:
- Add/remove admin
- Role changes
- Permission changes
- Activate/deactivate
- Invite creation/revocation
- Request approval/rejection

## Installation

### 1. Apply Database Migration

```bash
cd /opt/club_assistant
sqlite3 knowledge.db < migrations/admins_001_init.sql
```

This will:
- Extend the `admins` table with new columns
- Create `admin_invites`, `admin_requests`, and `admin_audit_logs` tables
- Add indexes for performance

### 2. Configure Environment Variables

Add to `.env` file:
```bash
OWNER_TG_IDS=123456789,987654321
```

Or configure in `config.json`:
```json
{
  "owner_id": 123456789,
  ...
}
```

### 3. Restart Bot

```bash
systemctl restart club_assistant.service
```

## Usage

### Commands

- `/admins` - Open admin management menu (owner and managers only)
- `/promote` - Promote user by replying to their message (owner only)
- `/request_admin` - Request admin access (any user)

### Admin Management Flow

1. **Owner opens admin menu**: `/admins` or click "👥 Управление админами"
2. **Choose action**:
   - ➕ Add admin
   - 👥 View list
   - 🔎 Search
   - 📨 Requests/Invites

3. **Add admin** (multiple methods):
   - Enter `@username` - creates pending admin or shows existing
   - Use `/promote` - reply to user's message to instantly add them
   - Create invite link - share with user to join
   - Review requests - approve/reject pending requests

4. **Manage admin**:
   - Click on admin in list
   - View details and permissions
   - Change role (owner, manager, moderator, staff)
   - Toggle individual permissions
   - Activate/deactivate
   - Add notes
   - Remove (with confirmation)

### Creating Invite Links

1. Go to `/admins` → "📨 Запросы/приглашения" → "🔗 Приглашения"
2. Click "📨 Создать приглашение"
3. Choose default role
4. Share the generated link: `https://t.me/botname?start=admin_invite_TOKEN`

### Handling Admin Requests

1. User runs `/request_admin` with optional message
2. Owner sees request in "📨 Запросы/приглашения"
3. Owner can approve (adds as staff) or reject

## API Reference

### Database Operations (`modules/admins/db.py`)

```python
from modules.admins.db import AdminDB

db = AdminDB('knowledge.db')

# Admin CRUD
admin = db.get_admin(user_id)
admins, total = db.list_admins(role='manager', active=1, page=1, per_page=20)
db.set_role(user_id, 'manager')
db.set_permissions(user_id, {'cash_view': True, 'cash_edit': False})
db.set_active(user_id, 1)

# Invites
token = db.create_invite(created_by, target_username='user', role_default='staff')
invite = db.get_invite(token)
db.revoke_invite(invite_id)

# Requests
db.create_request(user_id, username, full_name, message)
requests, total = db.list_requests(status='pending')
db.approve_request(request_id, reviewed_by, role='staff')

# Audit
db.log_action(actor_user_id, 'add', target_user_id, details={'role': 'staff'})
logs, total = db.get_audit_logs(user_id=user_id)
```

### Integration (`modules/admins/__init__.py`)

```python
from modules.admins import register_admins

# Register admin module with bot
admin_db, admin_wizard = register_admins(
    application,
    config,
    db_path='knowledge.db',
    bot_username='your_bot'
)
```

## Database Schema

### Extended `admins` Table

```sql
ALTER TABLE admins ADD COLUMN role TEXT DEFAULT 'staff';
ALTER TABLE admins ADD COLUMN permissions TEXT NULL;  -- JSON
ALTER TABLE admins ADD COLUMN active INTEGER DEFAULT 1;
ALTER TABLE admins ADD COLUMN notes TEXT NULL;
ALTER TABLE admins ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
```

### `admin_invites` Table

```sql
CREATE TABLE admin_invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    created_by INTEGER NOT NULL,
    target_username TEXT NULL,
    role_default TEXT DEFAULT 'staff',
    expires_at TIMESTAMP NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `admin_requests` Table

```sql
CREATE TABLE admin_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NULL,
    full_name TEXT NULL,
    message TEXT NULL,
    status TEXT DEFAULT 'pending',
    reviewed_by INTEGER NULL,
    reviewed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `admin_audit_logs` Table

```sql
CREATE TABLE admin_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_user_id INTEGER NULL,
    details TEXT NULL,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Security

- Only owners (or users with `can_manage_admins` permission) can access admin management
- All destructive actions require confirmation
- All admin operations are logged in audit trail
- Invite links can expire and be revoked
- Admins can be deactivated without deletion

## Testing

Run the test suite:

```bash
python3 test_admin_management.py
```

This tests:
- Module imports
- Database operations (CRUD, invites, requests, audit)
- Formatter functions

## Troubleshooting

### "Admin module failed to register"

Check logs for detailed error. Common issues:
- Database migration not applied
- Missing dependencies (`python-telegram-bot`)
- Database file permissions

### "I can't see the admin management button"

- Only owners see the button in the main menu
- Check `OWNER_TG_IDS` environment variable
- Or check `owner_id` in config.json

### "Invite link doesn't work"

- Check bot username is set correctly
- Verify invite hasn't expired or been revoked
- Check invite status in database

## Future Enhancements

Potential improvements:
- Integration with FinMon for shift handover data
- Admin activity statistics and reports
- Permission groups/templates
- Scheduled permission grants (temporary access)
- Admin hierarchy (managers can only manage certain admins)
