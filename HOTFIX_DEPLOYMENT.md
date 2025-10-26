# Hotfix Deployment Guide

This document describes the deployment steps after merging this hotfix PR.

## Overview

This PR addresses critical deployment issues and adds essential bot management features:

1. **Database Migration System** - Resilient migrations with runtime schema fixes
2. **Shift Wizard Improvements** - Reliable /shift command with bottom button UI
3. **Owner Commands** - /apply_migrations, /migration, /backup with scheduled tasks
4. **Admin Panel Fixes** - Proper "Назад" navigation and role/permissions enforcement
5. **Owner Gates** - OWNER_TG_IDS protection for sensitive commands

## Post-Merge Deployment Steps

### 1. Configure Environment Variables

Add the following to your `.env` file:

```bash
# Owner Telegram IDs (comma-separated list)
OWNER_TG_IDS=123456789,987654321

# Database path (default: knowledge.db)
DB_PATH=knowledge.db

# Backup configuration
BACKUP_DIR=./backups
BACKUP_INTERVAL_DAYS=14

# FinMon Module Configuration
FINMON_DB_PATH=knowledge.db

# Optional: Google Sheets for duty detection
GOOGLE_SA_JSON=/opt/club_assistant/service-account.json
FINMON_SHEET_NAME=ClubFinance
```

**Important:** If `OWNER_TG_IDS` is not set, the bot will fall back to the single `owner_id` from `config.json`, but with reduced functionality.

### 2. Apply Database Migrations

From the bot chat (as owner), run:

```
/apply_migrations
```

This command will:
- Detect and add any missing `ts` columns in finmon tables
- Apply all pending SQL migrations from the `migrations/` directory
- Report results with clear success/failure messages

Expected output:
```
📋 Результаты миграции:

✅ finmon_001_init.sql
✅ admins_001_init.sql

✅ Миграции применены успешно
```

### 3. Verify Shift Module Registration

Check the bot logs for the following lines at startup:

```
✅ Shift wizard registered
   Commands: /shift, /balances, /movements
   Button: 💰 Сдать смену (reply keyboard)
```

### 4. Test Bottom Keyboard

In a club chat (mapped to a club in the database):
1. Send `/start` to the bot
2. Verify the reply keyboard appears with three buttons:
   - 📊 Статистика
   - ❓ Помощь
   - 💰 Сдать смену (replaces old "Мои долги")
3. Click "💰 Сдать смену" to test the shift wizard

### 5. Test Shift Wizard in Both Clubs

The shift wizard should auto-detect the club based on chat ID mapping:
- Chat ID `5329834944` → Рио
- Chat ID `5992731922` → Север

Run `/shift` in both club chats to verify:
1. Shift time selection appears
2. Previous balances are shown
3. Input fields work correctly
4. Data is saved to database

### 6. Optional: Configure Google Sheets Duty Detection

If you want automatic duty detection from Google Sheets:

1. Create a Google Service Account and download JSON credentials
2. Place the JSON file at `/opt/club_assistant/service-account.json`
3. Share your Google Sheet with the service account email
4. Set environment variables:
   ```bash
   GOOGLE_SA_JSON=/opt/club_assistant/service-account.json
   FINMON_SHEET_NAME=ClubFinance
   ```
5. Restart the bot

The sheet should have columns recognizing duty codes:
- д(р) - duty at Rio
- д(с) - duty at Sever
- н(р) - night at Rio
- н(с) - night at Sever

If the configuration is missing or invalid, the bot will log a warning but continue to work without duty detection.

### 7. Verify Owner Commands

As owner, test the following commands:

```
/apply_migrations    - Apply pending migrations
/migration          - Receive migration files archive
/backup             - Receive backup archive (DB + FinMon data)
/admins             - Admin management panel (owner only)
```

### 8. Verify Scheduled Tasks

The migration archive will be automatically sent to all owner IDs every 14 days (configurable via `BACKUP_INTERVAL_DAYS`).

Check logs for:
```
✅ Scheduled migration sending enabled (every 14 days)
```

## Troubleshooting

### Migration Fails

If `/apply_migrations` reports errors:
1. Check database file permissions
2. Verify SQL syntax in `migrations/*.sql` files
3. Check logs for detailed error messages

### Shift Wizard Not Available

If clicking "💰 Сдать смену" returns "Module unavailable":
1. Check logs for FinMon registration errors
2. Verify pytz or zoneinfo is available (should fallback gracefully)
3. Check owner IDs configuration

### Admin Panel "Назад" Issues

If the "Назад" button still closes the window:
1. Verify `modules/admins/wizard.py` was updated
2. Check for callback handler conflicts
3. Restart the bot

### Owner Commands Not Working

If owner commands return "Access denied":
1. Verify your Telegram ID is in `OWNER_TG_IDS`
2. Check `.env` file is loaded correctly
3. Check logs for owner IDs parsing errors

## Features Summary

### New Commands (Owner Only)

- `/apply_migrations` - Apply database migrations and runtime fixes
- `/migration` - Download migration SQL files as tar.gz archive
- `/backup` - Download complete backup (DB + FinMon data + config)

### Improved Commands

- `/shift` - Now works reliably with button-based wizard
- `/balances` - View current club balances
- `/movements` - View recent balance changes
- `/admins` - Enhanced with OWNER_TG_IDS support

### UI Changes

- Bottom keyboard with persistent buttons (reply keyboard)
- "💰 Сдать смену" button replaces "Мои долги"
- Admin Panel "Назад" properly navigates back instead of closing

### Technical Improvements

- Optional pytz dependency (falls back to zoneinfo or naive datetime)
- Runtime schema migrations for fixing partial database states
- Scheduled migration archive delivery every 14 days
- Clear startup logging for registered commands
- Owner gates with proper feedback when OWNER_TG_IDS is missing

## Rollback Procedure

If issues arise after deployment:

1. Stop the bot
2. Restore database from backup: `cp backups/backup_TIMESTAMP.tar.gz .`
3. Extract: `tar -xzf backup_TIMESTAMP.tar.gz`
4. Checkout previous commit: `git checkout <previous_commit>`
5. Restart the bot

Always test in a development environment before deploying to production!
