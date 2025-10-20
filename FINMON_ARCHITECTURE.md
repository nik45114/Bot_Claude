# FinMon Module Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Telegram Bot                             │
│                        (bot.py main)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ registers module
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FinMon Module                                 │
│                 (modules/finmon/)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │              │      │              │      │              │ │
│  │   models.py  │─────▶│   wizard.py  │─────▶│   sheets.py  │ │
│  │              │      │              │      │              │ │
│  │  Pydantic    │      │ Conversation │      │   Google     │ │
│  │  Models      │      │   Handler    │      │   Sheets     │ │
│  │              │      │              │      │   Sync       │ │
│  └──────────────┘      └───────┬──────┘      └──────────────┘ │
│                                │                                │
│                                ▼                                │
│                        ┌──────────────┐                         │
│                        │              │                         │
│                        │    db.py     │                         │
│                        │              │                         │
│                        │  FinMonDB    │                         │
│                        │  Class       │                         │
│                        └───────┬──────┘                         │
│                                │                                │
└────────────────────────────────┼────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │    SQLite Database     │
                    │   (knowledge.db)       │
                    ├────────────────────────┤
                    │  finmon_clubs          │
                    │  finmon_shifts         │
                    │  finmon_cashes         │
                    └────────────────────────┘
```

## Data Flow - Shift Submission

```
User sends /shift
       │
       ▼
┌──────────────────┐
│  SELECT CLUB     │  ←─ 4 clubs (Рио/Мичуринская × офиц/коробка)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  SELECT TIME     │  ←─ morning/evening
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  ENTER REVENUE   │  ←─ fact_cash, fact_card, qr, card2
│  (4 steps)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  ENTER CASHES    │  ←─ safe_cash_end, box_cash_end, goods_cash
│  (3 steps)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  ENTER EXPENSES  │  ←─ compensations, salary_payouts, other_expenses
│  (3 steps)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  ENTER INVENTORY │  ←─ joysticks (total/repair/need), games_count
│  (4 steps)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  ENTER SUPPLIES  │  ←─ toilet_paper, paper_towels
│  (2 steps)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  ENTER NOTES     │  ←─ Optional text
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  SHOW SUMMARY    │  ←─ Formatted preview
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  CONFIRM & SAVE  │
└────────┬─────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
   ┌─────────┐      ┌─────────────┐
   │ SQLite  │      │   Google    │
   │   DB    │      │   Sheets    │
   └─────────┘      └─────────────┘
```

## Class Relationships

```
┌─────────────────────────┐
│      Club Model         │
├─────────────────────────┤
│ - id: int               │
│ - name: str             │
│ - type: str             │
│ - created_at: datetime  │
└─────────────────────────┘
           △
           │ has many
           │
┌─────────────────────────┐         ┌──────────────────────┐
│     Shift Model         │         │  CashBalance Model   │
├─────────────────────────┤         ├──────────────────────┤
│ - id: int               │         │ - id: int            │
│ - club_id: int          │◀────────│ - club_id: int       │
│ - shift_date: date      │         │ - cash_type: str     │
│ - shift_time: str       │         │ - balance: float     │
│ - admin_tg_id: int      │         │ - updated_at: ...    │
│ - fact_cash: float      │         └──────────────────────┘
│ - fact_card: float      │
│ - qr: float             │
│ - ... (15+ fields)      │
└─────────────────────────┘
```

## Permission System

```
┌─────────────────────────────────────────┐
│            User Request                  │
│         (Telegram message)               │
└────────────────┬────────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │  Check Owner  │
         │  (OWNER_IDs)  │
         └───────┬───────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   ┌─────────┐      ┌──────────┐
   │ Owner   │      │  Admin   │
   │ Access  │      │  Access  │
   └────┬────┘      └────┬─────┘
        │                │
        ▼                ▼
  ┌──────────┐    ┌────────────┐
  │ See ALL  │    │ See OWN    │
  │ shifts   │    │ shifts     │
  └──────────┘    │ only       │
                  └────────────┘
```

## Database Schema

```
┌────────────────────────────────────┐
│        finmon_clubs                │
├────────────────────────────────────┤
│ id          INTEGER PK             │
│ name        TEXT                   │
│ type        TEXT (official/box)    │
│ created_at  TIMESTAMP              │
└────────────────────────────────────┘
                △
                │ FK
                │
┌────────────────────────────────────┐
│        finmon_shifts               │
├────────────────────────────────────┤
│ id              INTEGER PK         │
│ club_id         INTEGER FK         │
│ shift_date      DATE               │
│ shift_time      TEXT (morn/eve)    │
│ admin_tg_id     INTEGER            │
│ admin_username  TEXT               │
│ fact_cash       REAL               │
│ fact_card       REAL               │
│ qr              REAL               │
│ card2           REAL               │
│ safe_cash_end   REAL               │
│ box_cash_end    REAL               │
│ goods_cash      REAL               │
│ compensations   REAL               │
│ salary_payouts  REAL               │
│ other_expenses  REAL               │
│ joysticks_*     INTEGER (x3)       │
│ games_count     INTEGER            │
│ toilet_paper    BOOLEAN            │
│ paper_towels    BOOLEAN            │
│ notes           TEXT               │
│ created_at      TIMESTAMP          │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│        finmon_cashes               │
├────────────────────────────────────┤
│ id          INTEGER PK             │
│ club_id     INTEGER FK             │
│ cash_type   TEXT (official/box)    │
│ balance     REAL                   │
│ updated_at  TIMESTAMP              │
│ UNIQUE(club_id, cash_type)         │
└────────────────────────────────────┘
```

## Configuration Flow

```
┌─────────────┐
│  .env file  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────┐
│  Environment Variables           │
├──────────────────────────────────┤
│  FINMON_DB_PATH                  │
│  FINMON_SHEET_NAME               │
│  GOOGLE_SA_JSON                  │
│  OWNER_TG_IDS                    │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────┐
│  register_finmon()   │
│  (modules/finmon/    │
│   __init__.py)       │
└────────┬─────────────┘
         │
         ├──────────────┬──────────────┬─────────────┐
         ▼              ▼              ▼             ▼
    ┌────────┐    ┌─────────┐    ┌────────┐   ┌────────┐
    │FinMonDB│    │ Wizard  │    │ Sheets │   │ Bot    │
    │        │    │         │    │  Sync  │   │ App    │
    └────────┘    └─────────┘    └────────┘   └────────┘
```

## Google Sheets Integration (Optional)

```
                Shift Submitted
                       │
                       ▼
              ┌─────────────────┐
              │  append_shift() │
              └────────┬────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │   Google Sheets API     │
         └─────────────────────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
    ┌──────────────┐      ┌──────────────┐
    │   "Shifts"   │      │  "Balances"  │
    │   Sheet      │      │   Sheet      │
    └──────────────┘      └──────────────┘
    │ Дата         │      │ Клуб         │
    │ Время        │      │ Тип кассы    │
    │ Клуб         │      │ Баланс       │
    │ Админ        │      │ Обновлено    │
    │ Факт нал     │      └──────────────┘
    │ Факт б/н     │
    │ QR           │
    │ ... (18 cols)│
    └──────────────┘
```

## Error Handling

```
┌─────────────────┐
│  User Action    │
└────────┬────────┘
         │
         ▼
    ┌─────────┐
    │  Try    │
    └────┬────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
┌────────┐  ┌──────────┐
│Success │  │  Error   │
└───┬────┘  └────┬─────┘
    │            │
    │            ▼
    │       ┌────────────┐
    │       │   Log      │
    │       │  Error     │
    │       └─────┬──────┘
    │             │
    │             ▼
    │       ┌────────────┐
    │       │  Graceful  │
    │       │  Fallback  │
    │       └────────────┘
    │
    ▼
┌────────────┐
│  Continue  │
└────────────┘
```

## Testing Architecture

```
┌──────────────────────────────────┐
│       test_finmon.py             │
├──────────────────────────────────┤
│                                  │
│  1. Import Tests                 │
│  2. Database Tests               │
│  3. Model Tests                  │
│  4. Shift Operations             │
│  5. Balance Operations           │
│  6. Google Sheets (graceful)     │
│  7. Wizard Functions             │
│  8. Cleanup                      │
│                                  │
└────────────┬─────────────────────┘
             │
             ▼
       ┌──────────┐
       │  Result  │
       └────┬─────┘
            │
       ✅ PASS
```
