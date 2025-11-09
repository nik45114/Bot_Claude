# Анализ функциональности списания денег со смены

## 1. ФУНКЦИИ И ОБРАБОТЧИКИ СПИСАНИЯ

### A. Списание общих расходов (EXPENSE)

#### Основная функция запуска:
- **cmd_expense()** - строка 1743 в `/opt/club_assistant/modules/finmon_shift_wizard.py`
  - Запускает диалог списания расходов со смены
  - Проверяет наличие открытой смены
  - Просит выбрать источник кассы (основная касса или коробка)

#### Обработчики состояний диалога:
1. **expense_select_cash_source()** - строка 1785
   - Обрабатывает выбор источника (expense_main или expense_box)
   - Параметры: cash_source ('main' или 'box')
   - Просит введести сумму списания

2. **expense_receive_amount()** - строка 1817
   - Получает и валидирует сумму (> 0)
   - Просит введести причину списания

3. **expense_receive_reason()** - строка 1849
   - Получает и валидирует причину (1-200 символов)
   - Показывает экран подтверждения

4. **expense_confirm()** - строка 1883
   - Сохраняет списание в БД через ShiftManager.add_expense()
   - Уведомляет владельца о списании
   - Отправляет уведомление с деталями

#### Сохранение в БД:
- **ShiftManager.add_expense()** - строка 186 в `/opt/club_assistant/modules/shift_manager.py`
  ```python
  def add_expense(self, shift_id: int, cash_source: str, amount: float, reason: str) -> bool:
      # INSERT INTO shift_expenses (shift_id, cash_source, amount, reason)
  ```

### B. Снятие наличных/зарплата (WITHDRAWAL)

#### Основная функция запуска:
- **start_cash_withdrawal()** - строка 2428 в `/opt/club_assistant/modules/finmon_shift_wizard.py`
  - Запускает диалог снятия зарплаты с кассы
  - Проверяет наличие активной смены
  - Просит введести сумму для снятия

#### Обработчики состояний:
1. **receive_withdrawal_amount()** - строка 2470
   - Получает и валидирует сумму (> 0)
   - Показывает экран подтверждения

2. **handle_withdrawal_confirmation()** - строка 2518
   - Обрабатывает подтверждение (withdrawal_confirm)
   - Сохраняет запись в БД через SalaryCalculator.record_cash_withdrawal()
   - Уведомляет владельца о снятии

#### Сохранение в БД:
- **SalaryCalculator.record_cash_withdrawal()** - строка 384 в `/opt/club_assistant/modules/salary_calculator.py`
  ```python
  def record_cash_withdrawal(self, shift_id: int, admin_id: int, amount: float, reason: str = 'salary') -> int:
      # INSERT INTO shift_cash_withdrawals (shift_id, admin_id, amount, reason)
  ```

---

## 2. КНОПКИ И CALLBACK-ОБРАБОТЧИКИ

### Кнопки в главном меню (строка 2237 в bot.py):
```
💸 Списать с кассы    (callback_data="shift_expense")
💰 Взять зарплату     (callback_data="shift_salary")
```

### Регистрация обработчиков в bot.py (строки 4770-4813):

#### Обработчик списания расходов:
```python
# bot.py строки 4768-4792
expense_handler = ConversationHandler(
    entry_points=[
        CommandHandler("expense", shift_wizard.cmd_expense),
        MessageHandler(filters.TEXT & filters.Regex("^💸 Списать с кассы$"), shift_wizard.cmd_expense),
        CallbackQueryHandler(shift_wizard.start_expense, pattern="^shift_expense$")
    ],
    states={
        EXPENSE_SELECT_CASH_SOURCE: [
            CallbackQueryHandler(shift_wizard.expense_select_cash_source, pattern="^expense_")
        ],
        EXPENSE_ENTER_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.expense_receive_amount)
        ],
        EXPENSE_ENTER_REASON: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.expense_receive_reason)
        ],
        EXPENSE_CONFIRM: [
            CallbackQueryHandler(shift_wizard.expense_confirm, pattern="^expense_")
        ]
    },
    fallbacks=[CommandHandler("cancel", shift_wizard.cancel_command)]
)
```

#### Обработчик снятия наличных:
```python
# bot.py строки 4794-4813
withdrawal_handler = ConversationHandler(
    entry_points=[
        CommandHandler("withdrawal", shift_wizard.start_cash_withdrawal),
        MessageHandler(filters.TEXT & filters.Regex("^💰 Взять зарплату$"), shift_wizard.start_cash_withdrawal),
        CallbackQueryHandler(shift_wizard.start_cash_withdrawal, pattern="^shift_salary$")
    ],
    states={
        WITHDRAWAL_ENTER_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_withdrawal_amount)
        ],
        WITHDRAWAL_CONFIRM: [
            CallbackQueryHandler(shift_wizard.handle_withdrawal_confirmation, pattern="^withdrawal_")
        ]
    },
    fallbacks=[CommandHandler("cancel", shift_wizard.cancel_command)]
)
```

### Callback-параметры:
- `shift_expense` - запуск диалога списания
- `expense_main` - выбор основной кассы
- `expense_box` - выбор коробки
- `expense_cancel` - отмена списания
- `expense_confirm` - подтверждение списания
- `shift_salary` - запуск диалога снятия
- `withdrawal_confirm` - подтверждение снятия
- `withdrawal_cancel` - отмена снятия

---

## 3. УВЕДОМЛЕНИЯ О СПИСАНИИ

### В expense_confirm() (строки 1914-1930):
```python
notify_msg = f"💸 Списание в смене #{shift_id}\n\n"
notify_msg += f"🏢 {club} | {source_label}\n"
notify_msg += f"💰 {amount:,.0f} ₽\n"
notify_msg += f"📝 {reason}\n\n"
notify_msg += f"👤 {user.full_name or 'Неизвестно'}"
```

### В handle_withdrawal_confirmation() (строки 2567-2580):
```python
notify_msg = f"💰 Снятие зарплаты с кассы\n\n"
notify_msg += f"👤 {admin_name} (ID: {user_id})\n"
notify_msg += f"🏢 Клуб: {active_shift['club']}\n"
notify_msg += f"🆔 Смена: #{active_shift['id']}\n"
notify_msg += f"💵 Сумма: {amount:,.0f} ₽\n"
notify_msg += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
```

---

## 4. ХРАНИЛИЩЕ ИНФОРМАЦИИ О СПИСАНИЯХ

### Таблица shift_expenses (для расходов)
Файл: `/opt/club_assistant/migrations/add_shift_management.sql` (строки 16-25)
```sql
CREATE TABLE IF NOT EXISTS shift_expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shift_id INTEGER NOT NULL,
  cash_source TEXT NOT NULL,  -- 'main' или 'box'
  amount REAL NOT NULL,
  reason TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (shift_id) REFERENCES active_shifts(id)
);
```

**Индекс:** `idx_shift_expenses_shift ON shift_expenses(shift_id)`

### Таблица shift_cash_withdrawals (для снятия зарплаты)
Файл: `/opt/club_assistant/migrations/add_salary_system.sql` (строки 27-37)
```sql
CREATE TABLE IF NOT EXISTS shift_cash_withdrawals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shift_id INTEGER NOT NULL,
  admin_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  reason TEXT DEFAULT 'salary',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (shift_id) REFERENCES active_shifts(id),
  FOREIGN KEY (admin_id) REFERENCES admins(user_id)
);
```

**Индексы:**
- `idx_shift_cash_withdrawals_shift ON shift_cash_withdrawals(shift_id)`
- `idx_shift_cash_withdrawals_admin ON shift_cash_withdrawals(admin_id)`

### Связанная таблица active_shifts
```sql
CREATE TABLE IF NOT EXISTS active_shifts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admin_id INTEGER NOT NULL,
  club TEXT NOT NULL,
  shift_type TEXT NOT NULL,      -- 'morning' или 'evening'
  opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  confirmed_by INTEGER,
  status TEXT DEFAULT 'open'      -- 'open', 'closed'
);
```

---

## 5. СОСТОЯНИЯ ДИАЛОГА (ConversationHandler)

### Для списания расходов (finmon_shift_wizard.py, строки 61):
```python
(EXPENSE_SELECT_CASH_SOURCE, EXPENSE_ENTER_AMOUNT, EXPENSE_ENTER_REASON, EXPENSE_CONFIRM) = range(14, 18)
```
- EXPENSE_SELECT_CASH_SOURCE = 14
- EXPENSE_ENTER_AMOUNT = 15
- EXPENSE_ENTER_REASON = 16
- EXPENSE_CONFIRM = 17

### Для снятия наличных (finmon_shift_wizard.py, строки 64):
```python
(WITHDRAWAL_ENTER_AMOUNT, WITHDRAWAL_CONFIRM) = range(18, 20)
```
- WITHDRAWAL_ENTER_AMOUNT = 18
- WITHDRAWAL_CONFIRM = 19

---

## 6. ПОЛУЧЕНИЕ ИНФОРМАЦИИ О СПИСАНИЯХ

### ShiftManager.get_shift_expenses() - строка 218
```python
def get_shift_expenses(self, shift_id: int) -> List[Dict]:
    # SELECT id, shift_id, cash_source, amount, reason, created_at
    # FROM shift_expenses WHERE shift_id = ? ORDER BY created_at ASC
```

### ShiftManager.get_expenses_summary() - строка 249
```python
def get_expenses_summary(self, shift_id: int) -> Dict[str, float]:
    # Возвращает {'main': 0.0, 'box': 0.0, 'total': 0.0}
```

### SalaryCalculator.get_cash_withdrawals() - строка 123
```python
def get_cash_withdrawals(self, admin_id: int, period_start: date, period_end: date) -> float:
    # SELECT SUM(amount) FROM shift_cash_withdrawals
```

---

## 7. СКВОЗНОЙ ПРОЦЕСС СПИСАНИЯ

### Для расходов (EXPENSE):
1. Пользователь нажимает кнопку "💸 Списать с кассы" (callback_data="shift_expense")
2. Вызывается `start_expense()` → `cmd_expense()`
3. Выбирает источник: main (💰) или box (📦)
4. Вводит сумму (валидация > 0)
5. Вводит причину (валидация 1-200 символов)
6. Подтверждает списание
7. `expense_confirm()` вызывает `ShiftManager.add_expense()` → INSERT в shift_expenses
8. Отправляет уведомление владельцу

### Для снятия наличных (WITHDRAWAL):
1. Пользователь нажимает кнопку "💰 Взять зарплату" (callback_data="shift_salary")
2. Вызывается `start_cash_withdrawal()`
3. Вводит сумму (валидация > 0)
4. Подтверждает снятие
5. `handle_withdrawal_confirmation()` вызывает `SalaryCalculator.record_cash_withdrawal()` → INSERT в shift_cash_withdrawals
6. Отправляет уведомление владельцу

---

## 8. ФАЙЛЫ, УЧАСТВУЮЩИЕ В ФУНКЦИОНАЛЬНОСТИ

- `/opt/club_assistant/modules/finmon_shift_wizard.py` - основной модуль диалогов
- `/opt/club_assistant/modules/shift_manager.py` - управление сменами и расходами
- `/opt/club_assistant/modules/salary_calculator.py` - расчет зарплаты и запись снятий
- `/opt/club_assistant/bot.py` - регистрация обработчиков в боте
- `/opt/club_assistant/migrations/add_shift_management.sql` - структура таблиц расходов
- `/opt/club_assistant/migrations/add_salary_system.sql` - структура таблиц снятий

