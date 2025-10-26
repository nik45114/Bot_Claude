# FinMon Simple - Setup Guide

## Overview

FinMon Simple is a lightweight financial monitoring system for computer clubs that uses JSON for balance storage and CSV for transaction logs. It integrates with Google Sheets for automatic duty detection.

## Features

- **No Database Required**: Uses `finmon_balances.json` and `finmon_log.csv` for data persistence
- **One-Message Paste**: Submit shift data by pasting all numbers in a single message
- **Auto Club Detection**: Chat ID automatically determines the club (Rio or Sever)
- **Auto Shift Time Detection**: Automatically detects morning/evening shift based on MSK time
- **Google Sheets Integration**: Optional duty schedule lookup from Google Sheets
- **Owner-Only Controls**: `/admins` and `/v2ray` commands restricted to owners
- **Inline Confirmation**: Review shift data before submission with ✅/❌ buttons

## Commands

### Regular Commands
- `/shift` - Start shift submission process
- `/balances` - Show current balances for all clubs
- `/movements` - Show recent movements (filtered by chat if in mapped chat)
- `/cancel` - Cancel current shift submission

### Owner-Only Commands
- `/admins` - Admin management panel (OWNER_TG_IDS only)
- `/v2ray` - V2Ray VPN management (OWNER_TG_IDS only)

## Setup

### 1. Environment Variables

Add these to your `.env` file:

```bash
# Required: Owner Telegram IDs (comma-separated)
OWNER_TG_IDS=123456789,987654321

# Optional: Google Service Account JSON path for duty detection
GOOGLE_SA_JSON=/path/to/service-account.json
```

### 2. Chat-to-Club Mapping

The following chat IDs are hardcoded to auto-detect clubs:

- `5329834944` → Рио (Rio)
- `5992731922` → Север (Sever)

To modify these mappings, edit `modules/finmon_simple.py`:

```python
CHAT_TO_CLUB = {
    5329834944: "Рио",
    5992731922: "Север"
}
```

### 3. Google Sheets Integration (Optional)

#### 3.1. Create Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **Credentials** → **Create Credentials** → **Service Account**
5. Fill in the service account details
6. Click **Create and Continue**
7. Skip roles (click Continue)
8. Click **Done**

#### 3.2. Generate JSON Key

1. Click on the created service account
2. Go to **Keys** tab
3. Click **Add Key** → **Create New Key**
4. Select **JSON** format
5. Download the JSON file
6. Save it securely (e.g., `/opt/club_assistant/service-account.json`)

#### 3.3. Share Google Sheet

1. Open your duty schedule Google Sheet
2. Click **Share** button
3. Copy the `client_email` from your service account JSON (looks like `xxx@xxx.iam.gserviceaccount.com`)
4. Add it to the sheet with **Editor** permissions
5. Click **Send** (uncheck "Notify people")

#### 3.4. Schedule Sheet Format

Your Google Sheet should have this format:

```
Row 1 (Header):  A        B        C        D        E        ...
                 Name     25.10    26.10    27.10    28.10    ...

Row 2:           Иванов   д(р)     н(с)     -        д(р)     ...
Row 3:           Петров   н(р)     д(с)     н(р)     -        ...
...
```

**Shift Codes:**
- `д(р)` - Day shift Rio
- `д(с)` - Day shift Sever
- `н(р)` - Night shift Rio
- `н(с)` - Night shift Sever

**Important Notes:**
- Column A contains staff full names
- Row 1 contains dates in `DD.MM` format (e.g., `25.10`, `26.10`)
- Cells contain shift codes
- Morning close (10:00) → looks for night shift codes (`н(р)`, `н(с)`)
- Evening close (22:00) → looks for day shift codes (`д(р)`, `д(с)`)

#### 3.5. Configure Environment

Set the service account JSON path:

```bash
export GOOGLE_SA_JSON=/opt/club_assistant/service-account.json
```

Or add to `.env`:

```
GOOGLE_SA_JSON=/opt/club_assistant/service-account.json
```

## Shift Submission Flow

### 1. Start Shift Submission

Use `/shift` command in:
- A mapped chat (auto-detects club)
- Any chat (prompts for club name on first line)

### 2. Paste Shift Data

Send all data in one message. Example format:

```
Факт нал: 3 440
Факт карта: 12 345
QR: 0
Карта2: не работает
Сейф: 5 000
Коробка: 2 000
```

Or if club not auto-detected, add club name on first line:

```
Рио
Факт нал: 3 440
Факт карта: 12 345
QR: 0
Карта2: не работает
Сейф: 5 000
Коробка: 2 000
```

**Flexible Formatting:**
- Spaces in numbers are OK: `3 440` → `3440`
- Commas work: `3,440` → `3440`
- Zero alternatives: `0`, `нет`, `не работает` → `0`
- Field names are flexible (partial match)

### 3. Review Summary

Bot shows a summary including:
- Club name
- Duty person (from Google Sheets if available)
- Revenue (cash, card, QR, card2)
- Cash positions (safe/official, box)

### 4. Confirm or Cancel

Use buttons:
- **✅ Подтвердить** - Confirm and save shift
- **❌ Отменить** - Cancel submission

Upon confirmation:
- Balances updated in `finmon_balances.json`
- Transaction logged to `finmon_log.csv` with deltas
- Success message shows new balances

## Shift Time Windows (MSK)

### Morning Shift Close
- **Official Time**: 10:00 MSK
- **Early Close Window**: 09:00 - 10:00
- **Grace Period**: 10:00 - 11:00
- **Closes**: Night shift from previous day

### Evening Shift Close
- **Official Time**: 22:00 MSK
- **Early Close Window**: 21:00 - 22:00
- **Grace Period**: 22:00 - 23:00
- **Special Late Window**: 00:00 - 00:30 next day
- **Closes**: Day shift from current day

## Data Files

### finmon_balances.json

Stores current cash positions:

```json
{
  "Рио": {
    "official": 5000,
    "box": 2000
  },
  "Север": {
    "official": 3000,
    "box": 1500
  }
}
```

### finmon_log.csv

Transaction log with columns:
- `timestamp` - ISO 8601 timestamp
- `club` - Club name
- `shift_date` - Shift date (YYYY-MM-DD)
- `shift_time` - 'morning' or 'evening'
- `admin_tg_id` - Telegram user ID
- `admin_username` - Telegram username
- `duty_name` - Person on duty from schedule
- `safe_cash_end` - Final safe cash amount
- `box_cash_end` - Final box cash amount
- `delta_official` - Change in official cash
- `delta_box` - Change in box cash
- `fact_cash` - Fact cash revenue
- `fact_card` - Fact card revenue
- `qr` - QR payment revenue
- `card2` - Card2 revenue

## Troubleshooting

### Google Sheets Not Working

If duty detection isn't working:

1. **Check logs** for warnings about Google Sheets
2. **Verify service account JSON** exists at `GOOGLE_SA_JSON` path
3. **Check sheet sharing** - service account email must have Editor access
4. **Test manually**:
   ```python
   from modules.finmon_schedule import FinMonSchedule
   from datetime import date
   
   schedule = FinMonSchedule('/path/to/service-account.json')
   duty = schedule.get_duty_name('Рио', date(2024, 10, 26), 'evening')
   print(f"Duty: {duty}")
   ```

**Note**: If Google Sheets fails, the bot continues working without duty detection. This is by design for graceful degradation.

### /shift Not Responding

1. Check if chat is mapped or include club name in message
2. Verify data format matches expected pattern
3. Check bot logs for parsing errors

### Owner Commands Not Working

1. Verify `OWNER_TG_IDS` is set correctly in environment
2. Check your Telegram ID matches one in the list
3. IDs must be comma-separated: `123456789,987654321`

## Migration from DB-based FinMon

If you're migrating from the previous database-based FinMon:

1. **Export current balances** from DB to JSON manually
2. **Keep old data** - FinMon Simple uses separate files
3. **Update gradually** - both systems can coexist temporarily
4. **Future**: SQLite migration planned for separate PR

## Future Enhancements

Planned for future PRs:
- SQLite database migration
- Web dashboard for reports
- Multi-club management commands
- Revenue analytics
- Automated backups

## Support

For issues or questions:
1. Check bot logs: Look for `⚠️` or `❌` messages
2. Test components individually using test scripts
3. Verify environment variables are set correctly
4. Ensure file permissions allow JSON/CSV writes
