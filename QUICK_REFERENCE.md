# Hotfix Quick Reference

## Quick Commands (Owner Only)

```bash
# Apply pending migrations
/apply_migrations

# Download migration files
/migration

# Create and download backup
/backup

# Admin management panel
/admins
```

## New Features at a Glance

### 1. Bottom Keyboard (Reply Keyboard)
- **📊 Статистика** - Show bot statistics
- **❓ Помощь** - Show help
- **💰 Сдать смену** - Start shift submission wizard

### 2. Owner Commands
- **/apply_migrations** - Apply pending DB migrations and runtime fixes
- **/migration** - Download migration SQL files (tar.gz)
- **/backup** - Download complete backup (DB + data)

### 3. Shift Wizard
- Works in both club chats (auto-detect by chat ID)
- No longer crashes if pytz is missing
- Optional Google Sheets duty detection
- Shows previous balances before data entry

### 4. Admin Panel
- "Назад" button now navigates back (doesn't close window)
- Roles and permissions persist correctly
- Clear visual feedback

## Configuration (.env)

```bash
# Required for owner commands
OWNER_TG_IDS=123456789,987654321

# Optional - Google Sheets duty detection
GOOGLE_SA_JSON=/path/to/service-account.json
FINMON_SHEET_NAME=ClubFinance

# Optional - Backup configuration
BACKUP_DIR=./backups
BACKUP_INTERVAL_DAYS=14
```

## First-Time Setup

```bash
# 1. Set owner IDs in .env
echo "OWNER_TG_IDS=your_telegram_id" >> .env

# 2. Restart bot
systemctl restart club_assistant

# 3. From bot chat (as owner):
/apply_migrations

# 4. Test shift wizard
/shift
```

## Troubleshooting

### "Module unavailable" when clicking shift button
- Check bot logs for FinMon registration errors
- Verify owner IDs are configured
- Restart bot

### "Access denied" for owner commands
- Verify your Telegram ID is in OWNER_TG_IDS
- Check .env file is loaded
- Look for owner ID parsing errors in logs

### Migration fails
- Check database file permissions
- Verify migrations/ directory exists
- Check logs for SQL errors

### Admin panel "Назад" still closes
- Verify modules/admins/wizard.py was updated
- Restart bot
- Clear cache

## Log Messages to Look For

```
✅ Shift wizard registered
   Commands: /shift, /balances, /movements
   Button: 💰 Сдать смену (reply keyboard)

✅ Backup commands module registered
✅ Admin Management module registered

📋 Registered commands summary:
   Core: /start, /help, /stats
   ...

✅ Scheduled migration sending enabled (every 14 days)
```

## Security Notes

- All owner commands check OWNER_TG_IDS
- Backup includes config.json (may contain sensitive data)
- Migration files sent only to owners
- V2Ray commands protected by owner_ids

## Support

For detailed documentation:
- HOTFIX_DEPLOYMENT.md - Complete deployment guide
- HOTFIX_SUMMARY.md - Technical details
- .env.example - Configuration template
