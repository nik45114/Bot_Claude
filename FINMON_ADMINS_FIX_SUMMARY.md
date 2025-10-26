# FinMon + Admins: Implementation Summary

## Changes Made

### 1. Fixed /admins Button
**Problem**: The "👥 Управление админами" button in the main menu was not working because the callback handler was registered after the general callback handler.

**Solution**:
- Moved `register_admins()` call to execute BEFORE the general `CallbackQueryHandler`
- This ensures that admin module's callback pattern `^adm_` is handled correctly
- The button now opens the full admin management wizard

### 2. Enabled FinMon Module
**Problem**: FinMon module was commented out and marked as "in development"

**Solution**:
- Uncommented `register_finmon()` in bot.py
- Module now initializes and registers all handlers
- Placed after admin module but before general callback handler

### 3. Chat → Club Mapping
**Problem**: Users had to manually select club every time they used `/shift`

**Solution**:
- Created new table `finmon_chat_club_map` in migration `finmon_002_chat_club_mapping.sql`
- Added "Север" club to database (previously only had "Рио" and "Мичуринская")
- Pre-configured mappings:
  - Chat `5329834944` → Рио (official)
  - Chat `5992731922` → Север (official)

**New Commands** (owner-only):
- `/finmon_map` - Show all chat-club mappings
- `/finmon_bind <chat_id> <club_id>` - Bind a chat to a club
- `/finmon_bind_here <club_id>` - Bind current chat to a club
- `/finmon_unbind <chat_id>` - Remove chat mapping

**Updated Behavior**:
- When `/shift` is called in a mapped chat, it automatically selects the club and skips to time selection
- Saves time and reduces errors

### 4. Google Sheets Schedule Integration
**Problem**: No automatic determination of who was scheduled to be on duty

**Solution**:
- Added `get_duty_admin_for_shift()` method to `GoogleSheetsSync` class
- Reads from "Schedule" worksheet with columns: Дата, Клуб, Смена, Админ
- Automatically adds scheduled duty admin to shift notes
- Shows duty admin in confirmation message

**New Command**:
- `/finmon_schedule_setup` - Shows instructions for setting up Google Sheets schedule
  - Provides service account email
  - Explains table structure
  - Gives examples

**Schedule Table Format**:
```
Дата       | Клуб | Смена | Админ
01.01.2024 | Рио  | Утро  | Иван
01.01.2024 | Рио  | Вечер | Мария
```

## Database Schema Changes

### New Table: finmon_chat_club_map
```sql
CREATE TABLE finmon_chat_club_map (
    chat_id INTEGER PRIMARY KEY,
    club_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (club_id) REFERENCES finmon_clubs(id)
);
```

### New Clubs
- Север (official) - ID: 5
- Север (box) - ID: 6

## Testing Instructions

### Test /admins Button
1. Start bot and use `/start` command
2. If you're the owner, you should see "👥 Управление админами" button
3. Click the button - should open admin management wizard with list of admins

### Test Chat Mapping
1. In chat `5329834944`, run `/shift`
   - Should auto-select "Рио official" and skip to time selection
2. In chat `5992731922`, run `/shift`
   - Should auto-select "Север official" and skip to time selection
3. In any other chat, run `/shift`
   - Should show club selection menu (normal behavior)

### Test Google Sheets Schedule (requires credentials)
1. Set up GOOGLE_SA_JSON environment variable with service account credentials
2. Run `/finmon_schedule_setup` to get setup instructions
3. Create "Schedule" sheet and add test data
4. Complete a shift - confirmation should show scheduled duty admin

### Test Mapping Commands (owner only)
1. `/finmon_map` - View all mappings
2. `/finmon_bind_here 1` - Bind current chat to Рио official
3. `/finmon_unbind 5329834944` - Remove mapping
4. `/finmon_bind 5329834944 1` - Re-add mapping

## Environment Variables

Add to `.env`:
```
OWNER_TG_IDS=123456789,987654321
GOOGLE_SA_JSON=/path/to/service-account.json
FINMON_SHEET_NAME=ClubFinance
```

## Files Changed
- `bot.py` - Moved module registrations, enabled FinMon
- `modules/finmon/__init__.py` - Added mapping commands
- `modules/finmon/db.py` - Added chat-club mapping methods
- `modules/finmon/wizard.py` - Auto-select club, duty admin integration, mapping commands
- `modules/finmon/sheets.py` - Added schedule reading, service account email retrieval
- `migrations/finmon_002_chat_club_mapping.sql` - New migration for mappings and Север club

## Security Notes
- All mapping commands are owner-only (checked via OWNER_TG_IDS)
- Google Sheets service account requires explicit sharing
- Chat mappings stored in database, not hardcoded
- No sensitive data exposed in commands
