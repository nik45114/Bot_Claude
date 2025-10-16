# 🚀 Обновление до v4.13 - Улучшенная система отчетов и V2Ray

## 📦 Что нового в v4.13

### ✨ Улучшенная система расходов

**Новые возможности:**

1. **Улучшенный парсинг расходов** - распознает разные форматы:
   - `- 4500 вика зп`
   - `( - 4500 вика зп)`
   - `зп вика 4500`
   - `закупка 1500 monster`
   - `инкассация 10000`

2. **Автоматическое определение получателя**:
   - "- 4500 вика зп" → получатель: "вика", категория: "зарплата"
   - "закупка 1500 monster" → категория: "закупка", описание: "monster"

3. **Расширенные категории расходов**:
   - 👤 Зарплата (salary)
   - 🛒 Закупки (purchase)
   - 🏦 Инкассация (collection)
   - 🔧 Ремонт (repair)
   - 🔌 Коммунальные (utility)
   - 💰 Прочее (other)

4. **Новые команды и методы**:
   - `add_expense()` - добавить расход к смене
   - `get_expenses_stats()` - статистика расходов за период
   - `get_expenses_history()` - история расходов
   - Улучшенная `get_club_stats()` с учетом расходов

5. **Улучшенное форматирование отчетов**:
   - Расходы группируются по категориям
   - Отображается получатель (если указан)
   - Подсчет общей суммы расходов
   - Красивые эмодзи для каждой категории

### 🔐 Полный V2Ray Manager с REALITY

**Новый модуль `v2ray_manager.py`:**

1. **SSH управление серверами**:
   - Автоматическое подключение
   - Выполнение команд
   - Передача файлов

2. **Установка Xray**:
   - Автоматическая установка на Ubuntu
   - Проверка статуса
   - Управление сервисом

3. **REALITY протокол**:
   - Генерация ключей (x25519)
   - Настройка маскировки
   - Vision flow для обхода DPI

4. **Управление пользователями**:
   - Добавление с генерацией UUID
   - Генерация VLESS ссылок
   - Удаление пользователей

5. **База данных**:
   - Хранение серверов и ключей
   - Хранение пользователей и ссылок
   - История операций

---

## 🔧 Установка обновления

### Шаг 1: Резервное копирование

```bash
cd /opt/club_assistant

# Останови бота
systemctl stop club_assistant

# Создай бэкап
cp club_manager.py club_manager.py.backup
cp knowledge.db knowledge.db.backup
```

### Шаг 2: Обновление файлов

```bash
# Скачай новые файлы из репозитория
git pull origin main

# Или вручную замени файлы:
# 1. Скопируй club_manager_v2.py → club_manager.py
# 2. Скопируй v2ray_manager.py в директорию бота
# 3. Обнови v2ray_commands.py (если нужно)
```

### Шаг 3: Установка зависимостей

```bash
# Активируй виртуальное окружение
source venv/bin/activate

# Установи paramiko для SSH
pip install paramiko

# Опционально: установи xray локально для генерации ключей
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

deactivate
```

### Шаг 4: Миграция базы данных

База данных обновится автоматически при первом запуске. Но если хочешь проверить:

```bash
sqlite3 knowledge.db

-- Проверь новые поля в shift_expenses
.schema shift_expenses

-- Должно быть:
-- recipient TEXT,
-- notes TEXT,

-- Проверь таблицы V2Ray
.schema v2ray_servers
.schema v2ray_users

.exit
```

### Шаг 5: Обновление bot.py

Убедись, что в `bot.py` импортированы новые модули:

```python
from club_manager import ClubManager  # Обновленная версия
from v2ray_manager import V2RayManager  # Новый модуль
from v2ray_commands import V2RayCommands  # Обновленный модуль
```

И инициализированы:

```python
# В main():
club_manager = ClubManager(db_path='knowledge.db')
v2ray_manager = V2RayManager(db_path='knowledge.db')
v2ray_commands = V2RayCommands(v2ray_manager, admin_manager, OWNER_ID)
```

### Шаг 6: Запуск

```bash
# Запусти бота
systemctl start club_assistant

# Проверь логи
journalctl -u club_assistant -f
```

---

## 📋 Примеры использования

### Расходы в отчетах

**Старый формат (все еще работает):**
```
Вечер 15.10
Факт нал 3940 / 20703
( - 4500 вика зп, - 4500 ваня зп)
```

**Новые форматы:**

1. **Зарплаты:**
```
Вечер 15.10
Факт нал 3940
зп вика 4500
зп ваня 4500
аванс петя 3000
```

2. **Закупки:**
```
закупка 1500 monster
товар 2000 снеки
```

3. **Инкассация:**
```
инкассация 10000
сдача в банк 15000
```

4. **Смешанный формат:**
```
Вечер 15.10
Факт нал 3940

- 4500 вика зп
- 4500 ваня зп
закупка 1500 monster
инкассация 10000
```

**Результат:**

```
💸 РАСХОДЫ
━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 Зарплата:
  👤 зп (вика): 4,500 ₽
  👤 зп (ваня): 4,500 ₽

🛒 Закупки:
  🛒 закупка monster: 1,500 ₽

🏦 Инкассация:
  🏦 инкассация: 10,000 ₽

📊 Всего расходов: 20,500 ₽
```

### Новые команды для аналитики расходов

**В bot.py добавь:**

```python
async def cmd_expenses_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика расходов: /expenses [club_id] [days]"""
    if not is_owner(update.effective_user.id):
        return
    
    club_id = int(context.args[0]) if len(context.args) > 0 else None
    days = int(context.args[1]) if len(context.args) > 1 else 30
    
    stats = club_manager.get_expenses_stats(club_id, days)
    
    text = f"📊 Статистика расходов за {days} дней:\n\n"
    
    for category, data in stats['by_category'].items():
        emoji = {
            'salary': '👤',
            'purchase': '🛒',
            'collection': '🏦',
            'repair': '🔧',
            'utility': '🔌',
            'other': '💰'
        }.get(category, '💰')
        
        text += f"{emoji} {category.title()}:\n"
        text += f"   Сумма: {data['total']:,} ₽\n"
        text += f"   Операций: {data['count']}\n"
        text += f"   Средняя: {data['average']:,.0f} ₽\n\n"
    
    text += f"💰 Всего: {stats['total']:,} ₽"
    text += f"\n📝 Операций: {stats['count']}"
    
    await update.message.reply_text(text)

# Зарегистрируй команду
app.add_handler(CommandHandler("expenses", cmd_expenses_stats))
```

### V2Ray с REALITY

**Полный цикл настройки:**

```bash
# 1. Добавь сервер (с SNI по умолчанию rutube.ru)
/v2add main 45.144.54.117 root MyPass123

# Или с кастомным SNI
/v2add main 45.144.54.117 root MyPass123 youtube.com

# 2. Установи Xray (2-3 минуты)
/v2setup main

# Бот ответит:
✅ Xray установлен на main!

🔐 Протокол: REALITY
🌐 Маскировка: rutube.ru

Теперь можешь добавлять пользователей:
/v2user main <user_id> [email]

# 3. Добавь пользователя
/v2user main @username Вася

# Бот ответит:
✅ Пользователь добавлен!

👤 ID: @username
📧 Email: Вася
🔑 UUID: d25e2d90-2ee8-48a2-83f4-5af0bff8e82f
🌐 SNI: rutube.ru

🔗 VLESS ссылка (REALITY):
vless://d25e2d90-2ee8-48a2-83f4-5af0bff8e82f@45.144.54.117:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=rutube.ru&fp=chrome&type=tcp&pbk=tC5EjUIeCYfMPp-cPfteC_3GuRG3fFG_cnwOAri_E04&sid=42b4137294a4fc79#Вася

# 4. Измени SNI (если нужно)
/v2sni main youtube.com

# Бот ответит:
✅ Маскировка изменена на youtube.com!

⚠️ Все пользователи должны обновить свои ссылки.
Создай новые: /v2user main <user_id>
```

**Популярные SNI для маскировки:**
- `rutube.ru` - хороший выбор для России
- `youtube.com` - работает везде
- `google.com` - надежный вариант
- `yandex.ru` - альтернатива для России
- `vk.com` - российская соцсеть

---

## 🔍 Тестирование

### Тест отчетов с расходами

```bash
# Отправь тестовый отчет:
/report Центральный

# Затем отправь текст:
Вечер 15.10
Факт нал 3940 / 20703
Наличка в сейфе 927

- 4500 вика зп
- 4500 ваня зп
закупка 1500 monster
инкассация 10000

# Проверь, что расходы правильно распарсены и отображены
```

### Тест V2Ray

```bash
# 1. Проверь список серверов
/v2list

# 2. Проверь статистику
/v2stats main

# 3. Попробуй подключиться с сгенерированной ссылкой
# Используй любой V2Ray клиент (v2rayNG, ShadowRocket, etc.)
```

---

## ⚠️ Известные проблемы и решения

### Проблема: "paramiko not found"

```bash
source venv/bin/activate
pip install paramiko
deactivate
systemctl restart club_assistant
```

### Проблема: "xray command not found" при генерации ключей

**Решение 1:** Установи xray локально:
```bash
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
```

**Решение 2:** Ключи будут генерироваться на сервере автоматически

### Проблема: Расходы не парсятся

Проверь форматы:
- ✅ `- 4500 вика зп`
- ✅ `зп вика 4500`
- ❌ `вика 4500` (без указания типа)

Если расход не распознается, добавь в `_categorize_expense()` новые ключевые слова.

### Проблема: V2Ray не устанавливается

1. Проверь подключение к серверу: `ssh root@IP`
2. Проверь доступность портов: `netstat -tulpn | grep :443`
3. Проверь логи установки в боте

---

## 📊 Статистика и аналитика

### Команды для владельца

```python
# Добавь в bot.py:

@app.command("expenses")
async def expenses_command(update, context):
    """Статистика расходов"""
    stats = club_manager.get_expenses_stats(days=30)
    # Форматирование и отправка

@app.command("expenses_history")
async def expenses_history_command(update, context):
    """История расходов"""
    history = club_manager.get_expenses_history(days=30)
    # Форматирование и отправка
```

### Интеграция с кнопками

Для удобного ввода расходов можно добавить Inline кнопки:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def report_callback(update, context):
    query = update.callback_query
    
    if query.data == "add_expense":
        # Показать кнопки с типами расходов
        keyboard = [
            [
                InlineKeyboardButton("👤 Зарплата", callback_data="expense_salary"),
                InlineKeyboardButton("🛒 Закупка", callback_data="expense_purchase")
            ],
            [
                InlineKeyboardButton("🏦 Инкассация", callback_data="expense_collection"),
                InlineKeyboardButton("🔧 Ремонт", callback_data="expense_repair")
            ]
        ]
        
        await query.message.reply_text(
            "Выбери тип расхода:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
```

---

## 🎯 Итоговый чеклист

После обновления проверь:

- [ ] База данных обновлена (новые поля в shift_expenses)
- [ ] Таблицы V2Ray созданы (v2ray_servers, v2ray_users)
- [ ] paramiko установлен
- [ ] Бот запускается без ошибок
- [ ] Команды /v2ray и /clubs работают
- [ ] Отчеты с расходами парсятся корректно
- [ ] V2Ray сервер устанавливается
- [ ] VLESS ссылки генерируются правильно
- [ ] Логи чистые, без критических ошибок

---

## 📝 Changelog v4.13

**Добавлено:**
- Улучшенный парсинг расходов (5+ форматов)
- Автоопределение получателя расходов
- Расширенные категории (6 типов)
- Полный V2Ray Manager с SSH
- REALITY протокол с генерацией ключей
- Методы для статистики расходов
- История расходов
- Красивое форматирование по категориям

**Изменено:**
- `shift_expenses` table: добавлены `recipient`, `notes`
- `format_report()`: группировка расходов по категориям
- `get_club_stats()`: учет расходов в статистике

**Исправлено:**
- Дубликаты расходов при парсинге
- Кодировка русских символов
- Генерация ключей REALITY

---

## 🚀 Что дальше?

**Планы на v4.14:**
- Inline кнопки для ввода отчетов
- Напоминания админам о сдаче отчетов
- Автоматическая аналитика расходов
- Интеграция с графиками (matplotlib)
- Экспорт отчетов в Excel
- Telegram Web App для отчетов

---

## 📞 Поддержка

Если возникли проблемы:

1. Проверь логи: `journalctl -u club_assistant -f`
2. Проверь базу: `sqlite3 knowledge.db ".schema"`
3. Проверь версию: посмотри VERSION в bot.py
4. Создай issue на GitHub с логами

**Версия:** v4.13  
**Дата:** 2025-10-16  
**Совместимость:** Python 3.8+, SQLite 3, Ubuntu 20.04+
