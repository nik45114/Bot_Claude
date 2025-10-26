# FinMon Simple - Usage Examples

## Example 1: Standard Shift Submission (Mapped Chat)

### User in Rio chat (5329834944):
```
User: /shift
```

### Bot Response:
```
📋 Сдача смены

🏢 Клуб: Рио
⏰ Время: вечер (дневная смена)
📅 Дата: 26.10.2024

Вставьте данные смены одним сообщением:

Пример формата:
Факт нал: 3 440
Факт карта: 12 345
QR: 0
Карта2: не работает
Сейф: 5 000
Коробка: 2 000
```

### User Pastes Data:
```
Факт нал: 3 440
Факт карта: 12 345
QR: 0
Карта2: не работает
Сейф: 5 000
Коробка: 2 000
```

### Bot Shows Summary:
```
📊 Сводка смены

🏢 Клуб: Рио

👤 Дежурный по графику: Иванов Иван

💰 Выручка:
  • Наличка факт: 3,440
  • Карта факт: 12,345
  • QR: 0
  • Карта2: 0

🔐 Остатки:
  • Сейф (офиц): 5,000
  • Коробка: 2,000

[✅ Подтвердить] [❌ Отменить]
```

### User Clicks ✅ Подтвердить

### Bot Confirms:
```
✅ Смена успешно сдана!

🏢 Рио
💰 Остатки:
  • Офиц (сейф): 5,000
  • Коробка: 2,000
```

### Behind the Scenes:

**finmon_balances.json updated:**
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

**finmon_log.csv appended:**
```csv
2024-10-26T22:15:00,Рио,2024-10-26,evening,123456789,manager,Иванов Иван,5000,2000,5000,2000,3440,12345,0,0
```

---

## Example 2: Unmapped Chat (Manual Club Entry)

### User in unmapped chat:
```
User: /shift
```

### Bot Response:
```
📋 Сдача смены

⚠️ Клуб не определён автоматически
Укажите клуб на первой строке (Рио или Север)

⏰ Время: вечер (дневная смена)
📅 Дата: 26.10.2024

Вставьте данные смены одним сообщением:

Пример формата:
Рио
Факт нал: 3 440
Факт карта: 12 345
QR: 0
Карта2: не работает
Сейф: 5 000
Коробка: 2 000
```

### User Pastes with Club Name:
```
Север
Факт нал: 1 200
Факт карта: 5 600
QR: 300
Карта2: 0
Сейф: 3 500
Коробка: 1 800
```

### Rest of flow same as Example 1...

---

## Example 3: Number Format Variations

All of these work:

### Standard with spaces:
```
Факт нал: 3 440
Факт карта: 12 345
```

### With commas:
```
Факт нал: 3,440
Факт карта: 12,345
```

### No spaces:
```
Факт нал: 3440
Факт карта: 12345
```

### Mixed:
```
Факт нал: 3 440
Факт карта: 12,345
QR: 500
```

### Zero alternatives:
```
QR: 0
Карта2: нет
QR: не работает
Карта2: -
```

All parse to correct numbers!

---

## Example 4: Morning Shift (Night Closing)

### At 09:30 MSK:
```
User: /shift
```

### Bot Response:
```
📋 Сдача смены

🏢 Клуб: Рио
⏰ Время: утро (ночная смена)
📅 Дата: 26.10.2024

Вставьте данные смены одним сообщением:
...
```

Note: **Morning = Night shift closing**, **Evening = Day shift closing**

---

## Example 5: Check Balances

### User:
```
/balances
```

### Bot Response:
```
💰 Текущие остатки

🏢 Рио:
  • Офиц (сейф): 5,000
  • Коробка: 2,000

🏢 Север:
  • Офиц (сейф): 3,000
  • Коробка: 1,500
```

---

## Example 6: View Movements

### User in Rio chat:
```
/movements
```

### Bot Response:
```
📝 Последние движения - Рио

📅 2024-10-26 (evening)
👤 Иванов Иван
  Δ Офиц: +5,000
  Δ Коробка: +2,000

📅 2024-10-25 (evening)
👤 Петров Петр
  Δ Офиц: +3,200
  Δ Коробка: +1,500

📅 2024-10-25 (morning)
👤 Сидоров Сидор
  Δ Офиц: -1,500
  Δ Коробка: +500
```

---

## Example 7: Owner-Only Command

### Regular admin tries:
```
Admin: /admins
```

### Bot Response:
```
❌ Доступ запрещён
```

### Owner tries:
```
Owner: /admins
```

### Bot Response:
```
👥 Админ-панель

[Shows full admin list with stats]
```

Same for `/v2ray` commands.

---

## Example 8: Without Google Sheets

If `GOOGLE_SA_JSON` not configured:

### Bot shows in summary:
```
📊 Сводка смены

🏢 Клуб: Рио

💰 Выручка:
  • Наличка факт: 3,440
  • Карта факт: 12,345
  ...
```

**Note:** No "👤 Дежурный по графику" line - that's OK!

### In CSV log:
```csv
...,duty_name,...
...,,5000,2000,...
```

Empty duty_name column - bot works fine without it.

---

## Example 9: Google Sheets Working

If properly configured:

### Bot shows in summary:
```
📊 Сводка смены

🏢 Клуб: Рио

👤 Дежурный по графику: Иванов Иван Петрович

💰 Выручка:
  ...
```

### In CSV log:
```csv
...,duty_name,...
...,Иванов Иван Петрович,5000,2000,...
```

---

## Example 10: Shift Window Detection

### At 21:30 MSK (early close):
```
User: /shift

Bot: 
📋 Сдача смены
🏢 Клуб: Рио
⏰ Время: вечер (дневная смена)
📅 Дата: 26.10.2024
```
✅ Within window (21:00-23:00)

### At 22:00 MSK (official time):
✅ Within window

### At 22:45 MSK (grace period):
✅ Within window (grace until 23:00)

### At 00:15 MSK (next day, late close):
```
⏰ Время: вечер (дневная смена)
📅 Дата: 25.10.2024
```
✅ Closing previous day's evening shift

### At 03:00 MSK (outside windows):
```
User: /shift

Bot:
📋 Сдача смены
⚠️ Клуб не определён автоматически
```
⚠️ No auto time detection, defaults to evening

---

## Error Scenarios

### Invalid data format:
```
User: random text without numbers

Bot: 
❌ Не удалось разобрать данные
Проверьте формат и попробуйте снова или используйте /cancel
```

### User clicks Cancel:
```
User: [clicks ❌ Отменить]

Bot:
❌ Сдача смены отменена
```

### Google Sheets unavailable:
```
[In logs:]
⚠️ Could not connect to schedule sheet: Permission denied
⚠️ Duty detection will be disabled...

[Bot continues working without duty names]
```

---

## Typical Daily Workflow

**Morning (09:30 - 10:30):**
1. Night shift manager: `/shift`
2. Bot: Shows morning window, requests data
3. Manager: Pastes numbers
4. Bot: Shows summary with night duty person
5. Manager: Confirms ✅
6. Bot: Updates balances, logs transaction

**Evening (21:30 - 22:30):**
1. Day shift manager: `/shift`
2. Bot: Shows evening window, requests data
3. Manager: Pastes numbers
4. Bot: Shows summary with day duty person
5. Manager: Confirms ✅
6. Bot: Updates balances, logs transaction

**Anytime:**
- `/balances` - Check current cash positions
- `/movements` - Review recent shifts
- Owner: `/admins` - Manage admins
- Owner: `/v2ray` - Manage VPN

---

## Tips

### Fast submission in mapped chat:
1. `/shift` → Enter
2. Paste data → Enter
3. Click ✅

**3 interactions = shift submitted!**

### Keep a template:
```
Факт нал: 
Факт карта: 
QR: 
Карта2: 
Сейф: 
Коробка: 
```
Fill in numbers, paste, done!

### Check before confirming:
- ✓ All numbers correct?
- ✓ Duty person correct?
- ✓ Club correct?
- ✓ Date/time correct?

Then ✅ Подтвердить

---

## Common Questions

**Q: What if I make a mistake?**
A: Click ❌ Отменить and start over with `/shift`

**Q: Can I edit after submitting?**
A: Not in this version. Submit a new shift or edit CSV manually.

**Q: Where's my data stored?**
A: `finmon_balances.json` and `finmon_log.csv` in bot directory

**Q: Can I use in multiple chats?**
A: Yes! Each mapped chat auto-detects its club.

**Q: Do I need Google Sheets?**
A: No! It's optional. Bot works fine without it.

**Q: What if Google Sheets breaks?**
A: Bot continues working, just without duty names.

---

For more details, see:
- `FINMON_SIMPLE_SETUP.md` - Complete setup
- `FINMON_QUICKSTART.md` - Quick reference
