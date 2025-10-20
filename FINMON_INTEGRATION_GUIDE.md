# 🔧 FinMon Integration Guide

Quick guide for enabling and using the FinMon module in your bot.

## ✅ Prerequisites

1. **Python 3.12+** with pydantic
2. **SQLite database** (knowledge.db)
3. **Telegram Bot** with python-telegram-bot 20.7+
4. *(Optional)* **Google Service Account** for Sheets sync

## 📦 Installation Steps

### 1. Install Dependencies

```bash
# System package (Ubuntu/Debian)
sudo apt-get install python3-pydantic

# Or via pip
pip install pydantic>=2.0.0 gspread>=5.0.0 oauth2client>=4.1.3
```

### 2. Apply Database Migration

The database migration is automatically applied on first use. You can also run it manually:

```bash
sqlite3 knowledge.db < migrations/finmon_001_init.sql
```

This creates:
- `finmon_clubs` - Club definitions
- `finmon_shifts` - Shift records
- `finmon_cashes` - Cash balances

### 3. Enable Module in Bot

The module is already enabled in `bot.py`:

```python
# FinMon module - Financial Monitoring
try:
    from modules.finmon import register_finmon
    finmon_config = {
        'db_path': DB_PATH,
        'google_sa_json': os.getenv('GOOGLE_SA_JSON'),
        'sheet_name': os.getenv('FINMON_SHEET_NAME', 'ClubFinance'),
        'owner_ids': str(self.owner_id)
    }
    register_finmon(application, finmon_config)
    logger.info("✅ FinMon module registered")
except Exception as e:
    logger.warning(f"⚠️ FinMon module registration failed: {e}")
```

### 4. Configure Environment Variables

Create or update your `.env` file:

```env
# Required for owner-only commands
OWNER_TG_IDS=123456789

# Optional - for Google Sheets sync
GOOGLE_SA_JSON=/path/to/service-account.json
FINMON_SHEET_NAME=ClubFinance
```

### 5. Start the Bot

```bash
python3 bot.py
```

The module will:
- ✅ Create database tables
- ✅ Initialize default clubs (Рио, Мичуринская)
- ✅ Register all commands
- ✅ Connect to Google Sheets (if configured)

## 🎯 Using the Commands

### For All Admins

**Start a shift submission:**
```
/shift
```
Follow the step-by-step wizard to submit a shift report.

**View cash balances:**
```
/balances
```
Shows current balances of all cash registers.

**View recent shifts:**
```
/shifts
```
Shows your last 10 submitted shifts (or all if you're an owner).

### For Owners Only

**View financial summary:**
```
/summary
```
Choose a period (today/week/month/all) to see aggregated financial data.

## 🔒 Access Control

The module implements role-based access:

| Command | Admins | Owners |
|---------|--------|--------|
| `/shift` | ✅ | ✅ |
| `/balances` | ✅ | ✅ |
| `/shifts` | ✅ (own only) | ✅ (all) |
| `/summary` | ❌ | ✅ |

Configure owners in `.env`:
```env
OWNER_TG_IDS=123456789,987654321
```

## 📊 Google Sheets Integration (Optional)

### Setup

1. **Create a Google Cloud Project**
2. **Enable Google Sheets API**
3. **Create Service Account**
4. **Download JSON credentials**
5. **Share your spreadsheet** with the service account email

### Configuration

```env
GOOGLE_SA_JSON=/opt/club_assistant/google-service-account.json
FINMON_SHEET_NAME=ClubFinance
```

### Sheets Structure

The module automatically creates three sheets:

**Shifts Sheet:**
- Date, Time, Club, Admin
- Revenue (Cash, Card, QR, New)
- Balances (Safe, Box, Goods)
- Expenses (Comp, Salary, Other)
- Inventory (Joysticks, Games)
- Supplies (Toilet paper, Towels)
- Notes

**Balances Sheet:**
- Club, Type, Balance, Updated

**Summary Sheet:**
- Auto-calculated totals and analytics

## 🧪 Testing

Run the included tests:

```bash
# Basic functionality test (no telegram required)
python3 test_finmon_basic.py

# Demo reports
python3 demo_finmon_reports.py
```

Both should output:
```
✅ ALL TESTS PASSED!
```

## 🐛 Troubleshooting

### Module Not Loading

**Error:** `No module named 'telegram'`

**Solution:** Install python-telegram-bot:
```bash
pip install python-telegram-bot==20.7
```

### Database Error

**Error:** `no such table: finmon_clubs`

**Solution:** Apply migration:
```bash
sqlite3 knowledge.db < migrations/finmon_001_init.sql
```

### Google Sheets Not Syncing

**Error:** `Google Sheets sync disabled`

**This is normal** if you haven't configured Google Sheets. The module works without it.

To enable:
1. Check `GOOGLE_SA_JSON` path is correct
2. Verify service account has access to spreadsheet
3. Check bot logs for specific error

### Permission Denied on /summary

**Error:** `❌ Команда доступна только владельцам`

**Solution:** Add your Telegram ID to `OWNER_TG_IDS`:
```env
OWNER_TG_IDS=YOUR_TELEGRAM_ID
```

Find your ID by sending any message to the bot and checking logs.

## 📈 Customization

### Adding New Clubs

Edit `migrations/finmon_001_init.sql`:

```sql
INSERT OR IGNORE INTO finmon_clubs (id, name, type) VALUES
    (5, 'NewClub', 'official'),
    (6, 'NewClub', 'box');
```

Or insert directly:
```sql
sqlite3 knowledge.db
> INSERT INTO finmon_clubs (name, type) VALUES ('NewClub', 'official');
```

### Custom Report Format

Edit `modules/finmon/formatters.py` to customize report appearance.

### Additional Fields

1. Update `models.py` - Add field to Shift model
2. Update `migrations/finmon_001_init.sql` - Add column
3. Update `wizard.py` - Add input step
4. Update `formatters.py` - Display in reports

## 🚀 Production Deployment

1. **Backup database** before updating:
   ```bash
   cp knowledge.db knowledge.db.backup
   ```

2. **Pull updates:**
   ```bash
   git pull origin main
   ```

3. **Apply migrations:**
   ```bash
   sqlite3 knowledge.db < migrations/finmon_001_init.sql
   ```

4. **Restart bot:**
   ```bash
   systemctl restart club_assistant.service
   ```

5. **Verify:**
   - Check logs: `journalctl -u club_assistant -f`
   - Test `/shift` command
   - Verify database: `sqlite3 knowledge.db ".tables"`

## 📞 Support

For issues or questions:
1. Check logs: `journalctl -u club_assistant -f`
2. Verify configuration: `.env` file
3. Test database: `python3 test_finmon_basic.py`
4. Review documentation: `FINMON_README.md`

## 🎓 Architecture

```
┌─────────────┐
│   bot.py    │  Main bot application
└──────┬──────┘
       │
       ├──────────────────────────────────────┐
       │                                      │
┌──────▼─────────┐                    ┌──────▼─────┐
│ FinMon Module  │                    │  Database  │
├────────────────┤                    ├────────────┤
│ • __init__.py  │◄───────────────────┤ knowledge.db│
│ • wizard.py    │  SQLite operations │            │
│ • db.py        │                    │ • clubs    │
│ • models.py    │                    │ • shifts   │
│ • formatters.py│                    │ • cashes   │
│ • sheets.py    │                    └────────────┘
└────────┬───────┘
         │
         │ (optional)
         ▼
┌─────────────────┐
│ Google Sheets   │
└─────────────────┘
```

---

**Version:** 1.0  
**Last Updated:** October 2025
