# Deployment Guide: FinMon + Admins Fixes

## Overview
This deployment adds three major features:
1. Fixed /admins button functionality
2. Automatic chat→club mapping for FinMon
3. Google Sheets schedule integration for duty admin tracking

## Pre-Deployment Checklist

### Required
- [x] Code merged to main branch
- [ ] Database backup created
- [ ] `.env` file updated with `OWNER_TG_IDS`

### Optional (for Google Sheets)
- [ ] Google Service Account created
- [ ] Service account JSON file available
- [ ] `GOOGLE_SA_JSON` path configured in `.env`
- [ ] `FINMON_SHEET_NAME` configured (default: "ClubFinance")

## Deployment Steps

### 1. Backup Current Database
```bash
cp knowledge.db knowledge.db.backup.$(date +%Y%m%d_%H%M%S)
```

### 2. Update Environment Variables

Add to your `.env` file:
```env
# Owner telegram IDs (comma-separated)
OWNER_TG_IDS=123456789,987654321

# Google Sheets (optional)
GOOGLE_SA_JSON=/path/to/service-account.json
FINMON_SHEET_NAME=ClubFinance
```

### 3. Stop the Bot
```bash
# If using systemd
sudo systemctl stop bot_claude

# Or if running manually
pkill -f bot.py
```

### 4. Pull Latest Changes
```bash
cd /path/to/Bot_Claude
git pull origin main
```

### 5. Apply Database Migrations

Migrations will run automatically on first bot start. The bot will:
- Create `finmon_chat_club_map` table
- Add "Север" club
- Set up initial chat mappings

### 6. Start the Bot
```bash
# If using systemd
sudo systemctl start bot_claude

# Or run manually
python3 bot.py
```

### 7. Verify Deployment

#### Test 1: /admins Button
1. Start bot: `/start`
2. Check for "👥 Управление админами" button (owner only)
3. Click button → should show admin management menu

#### Test 2: Chat Mapping
1. In chat 5329834944, run `/shift`
   - Should auto-select "Рио official"
2. In chat 5992731922, run `/shift`
   - Should auto-select "Север official"

#### Test 3: Mapping Commands (Owner Only)
```
/finmon_map                  # View current mappings
/finmon_bind_here 1          # Bind current chat to club ID 1
/finmon_unbind 5329834944    # Remove mapping
```

#### Test 4: Google Sheets Setup (Optional)
```
/finmon_schedule_setup       # Get setup instructions
```

## Post-Deployment Configuration

### Configure Chat Mappings

If you need different mappings than the defaults:

```
# View current mappings
/finmon_map

# Bind a specific chat to a club
/finmon_bind <chat_id> <club_id>

# Or bind the current chat
/finmon_bind_here <club_id>
```

**Club IDs:**
- 1: Рио (official)
- 2: Рио (box)
- 3: Мичуринская (official)
- 4: Мичуринская (box)
- 5: Север (official)
- 6: Север (box)

### Configure Google Sheets Schedule (Optional)

1. Get service account email:
   ```
   /finmon_schedule_setup
   ```

2. Create/open your Google Sheet

3. Add a worksheet named "Schedule"

4. Create table with these columns:
   | Дата       | Клуб | Смена | Админ |
   |------------|------|-------|-------|
   | 01.01.2024 | Рио  | Утро  | Иван  |
   | 01.01.2024 | Рио  | Вечер | Мария |

5. Share the sheet with the service account email (from step 1)
   - Give "Editor" or "Viewer" permissions

6. Test by completing a shift - duty admin should appear in confirmation

## Rollback Procedure

If you need to rollback:

### 1. Stop the Bot
```bash
sudo systemctl stop bot_claude
```

### 2. Restore Database
```bash
cp knowledge.db.backup.<timestamp> knowledge.db
```

### 3. Revert Code
```bash
git revert HEAD~3..HEAD  # Reverts last 3 commits
# Or checkout previous version
git checkout <previous-commit-hash>
```

### 4. Restart Bot
```bash
sudo systemctl start bot_claude
```

## Troubleshooting

### Issue: /admins button not appearing
**Solution:** Check that your user ID is in `OWNER_TG_IDS`

### Issue: Chat mapping not working
**Check:**
1. Is migration applied? Check `finmon_chat_club_map` table exists
2. Run `/finmon_map` to see if mapping exists
3. Check bot logs for errors

### Issue: Google Sheets not working
**Check:**
1. Is `GOOGLE_SA_JSON` path correct?
2. Is service account email added to sheet?
3. Does sheet have "Schedule" worksheet?
4. Are column names exact: Дата, Клуб, Смена, Админ?
5. Check bot logs for Google Sheets errors

### Issue: Database migration failed
**Solution:**
1. Check bot logs for specific error
2. Manually run migration:
   ```bash
   sqlite3 knowledge.db < migrations/finmon_002_chat_club_mapping.sql
   ```
3. If fails, restore backup and contact support

## Monitoring

After deployment, monitor:
1. Bot logs for errors
2. `/shift` command usage in mapped chats
3. Google Sheets sync (if configured)
4. Admin management usage

## Support

If you encounter issues:
1. Check bot logs: `journalctl -u bot_claude -f`
2. Review troubleshooting section above
3. Check FINMON_ADMINS_FIX_SUMMARY.md for detailed documentation

## Success Criteria

Deployment is successful when:
- [x] Bot starts without errors
- [x] /admins button appears and works for owner
- [x] /shift auto-selects club in mapped chats
- [x] Chat mapping commands work for owner
- [x] Google Sheets integration works (if configured)
- [x] No errors in logs
