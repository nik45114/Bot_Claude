# FinMon Simple - Quick Start Guide

## 🚀 Quick Start

### 1. Set Environment Variables

```bash
# Required: Owner Telegram IDs (comma-separated)
export OWNER_TG_IDS=123456789,987654321

# Optional: Google Sheets integration
export GOOGLE_SA_JSON=/path/to/service-account.json
```

### 2. How to Submit a Shift

1. **Start**: Send `/shift` in your club's chat
2. **Paste data** in one message:
   ```
   Факт нал: 3 440
   Факт карта: 12 345
   QR: 0
   Карта2: не работает
   Сейф: 5 000
   Коробка: 2 000
   ```
3. **Review** the summary (includes duty person if configured)
4. **Confirm** with ✅ or cancel with ❌

### 3. Check Balances

```
/balances - Show all club balances
/movements - Show recent transactions
```

## 📊 What Gets Tracked

### JSON File (`finmon_balances.json`)
```json
{
  "Рио": {"official": 5000, "box": 2000},
  "Север": {"official": 3000, "box": 1500}
}
```

### CSV Log (`finmon_log.csv`)
Each shift creates a row with:
- Timestamp, club, date, shift time
- Admin ID and username
- **Duty name from schedule** (if Google Sheets configured)
- Cash positions (safe/official, box)
- **Deltas** (change from previous shift)
- Revenue breakdown (cash, card, QR, card2)

## 🏢 Club Auto-Detection

The bot automatically knows which club based on chat ID:
- Chat `5329834944` → **Рио** (Rio)
- Chat `5992731922` → **Север** (Sever)

If `/shift` is used in an unmapped chat, add club name on first line:
```
Рио
Факт нал: 3 440
...
```

## ⏰ Auto Time Detection

The bot knows which shift to close based on Moscow time:

| Time Window | Closes | Notes |
|-------------|--------|-------|
| 09:00-11:00 | Night shift | Official: 10:00 |
| 21:00-23:00 | Day shift | Official: 22:00 |
| 00:00-00:30 | Previous day's evening | For late closes |

## 👤 Google Sheets Integration

If configured, the bot automatically finds who's on duty:

### Sheet Format
```
     A         B      C      D      ...
  Name     25.10  26.10  27.10   ...
  Иванов   д(р)   н(с)    -      ...
  Петров   н(р)   д(с)   н(р)    ...
```

**Codes:**
- `д(р)` = Day Rio
- `д(с)` = Day Sever  
- `н(р)` = Night Rio
- `н(с)` = Night Sever

The duty name appears in the shift summary and CSV log.

### Setup (3 steps)
1. Create Google Service Account → Download JSON
2. Share your schedule sheet with service account email
3. Set `GOOGLE_SA_JSON=/path/to/file.json`

**Note:** If not configured, everything still works (just no duty names).

## 🔐 Owner-Only Commands

These commands now require `OWNER_TG_IDS`:
- `/admins` - Admin management panel
- `/v2ray` - VPN management

Multiple owners supported:
```bash
export OWNER_TG_IDS=111111111,222222222,333333333
```

## 💡 Tips

### Number Formats (all work)
```
3 440    → 3440
3,440    → 3440
3440     → 3440
```

### Zero Alternatives (all mean 0)
```
0
нет
не работает
-
```

### Field Names (flexible)
```
Факт нал / Факт наличка / Наличка факт
Факт карта / Факт карточка / Карта факт
Сейф / Офиц / Safe
Коробка / Box / Ящик
```

## 🐛 Troubleshooting

### /shift doesn't respond
- ✓ Check chat is mapped or add club name
- ✓ Verify data format has all required fields
- ✓ Look at bot logs

### Duty name not showing
- ✓ Check `GOOGLE_SA_JSON` is set
- ✓ Verify sheet is shared with service account
- ✓ Check date format in sheet is `DD.MM`
- ✓ Look for `⚠️` warnings in logs
- **Note:** Bot works fine without this feature

### /admins or /v2ray denied
- ✓ Check your Telegram ID is in `OWNER_TG_IDS`
- ✓ Verify env variable format: `123,456,789`
- ✓ Restart bot after changing env

## 📁 File Locations

```
/path/to/bot/
  ├── finmon_balances.json  (current balances)
  ├── finmon_log.csv        (transaction history)
  └── service-account.json  (optional, for Google Sheets)
```

**Important:** Add these to `.gitignore` (already done):
```
finmon_balances.json
finmon_log.csv
```

## 🔄 Backup Recommendations

```bash
# Daily backup script example
#!/bin/bash
DATE=$(date +%Y%m%d)
cp finmon_balances.json backups/balances_$DATE.json
cp finmon_log.csv backups/log_$DATE.csv
```

## 📊 Example Workflow

1. **Manager arrives (morning)**: `/shift`
2. Bot shows: "Morning shift (night closing), Club: Rio, Time: 10:00, Duty: Иванов"
3. Manager pastes numbers from previous shift
4. Bot shows summary with Иванов as duty
5. Manager confirms ✅
6. Bot updates balances and logs transaction with deltas

Later:
- `/balances` - See current cash positions
- `/movements` - Review recent shifts

## 🎯 What's Next

This is v1 (no database). Future enhancements:
- SQLite migration (separate PR)
- Web dashboard
- Analytics and reports
- Automated daily summaries

For detailed setup: See `FINMON_SIMPLE_SETUP.md`
