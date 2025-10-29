# Club Assistant Bot - Справочник проекта

## Быстрая навигация

### Главные компоненты
1. **bot.py** (3772 строк) - основной файл, полный список команд
2. **modules/admins/** - система управления админами
3. **modules/finmon/** - финансовый мониторинг
4. **modules/shift_manager.py** - управление сменами
5. **modules/salary_calculator.py** - расчет зарплат

### Таблица модулей и их статус

```
МОДУЛЬ                          СТАТУС      СТРОК   ПРОБЛЕМЫ/ОСОБЕННОСТИ
────────────────────────────────────────────────────────────────────────

ОСНОВНЫЕ (АКТИВНЫЕ)
bot.py                          ACTIVE      3772    Слишком большой, нужен рефакторинг
modules/admins/__init__.py      ACTIVE      462     ✅ Хорошо структурирован
modules/admins/db.py            ACTIVE      952     ✅ Полный набор функций
modules/admins/wizard.py        ACTIVE      1158    ✅ FSM управление
modules/finmon/__init__.py      ACTIVE      180     ✅ Хорошая регистрация
modules/finmon/db.py            ACTIVE      286     ✅ CRUD операции
modules/finmon/wizard.py        ACTIVE      1165    ✅ Пошаговый ввод
modules/finmon/sheets.py        ACTIVE      279     ⚠️ Требует Google credentials
modules/shift_manager.py        ACTIVE      479     ✅ Управление сменами
modules/salary_calculator.py    ACTIVE      416     ✅ Расчет зарплат
modules/salary_commands.py      ACTIVE      538     ✅ Команды зарплаты
modules/payroll_manager.py      ACTIVE      449     ✅ Управление выплатами

ENHANCED СИСТЕМЫ
modules/enhanced_admin_shift.py        ACTIVE  737     Система с фото
modules/enhanced_shift_submission.py   ACTIVE  552     FSM сдачи смен
modules/enhanced_admin_shift_integration.py ACTIVE 254  Объединение

ВСПОМОГАТЕЛЬНЫЕ
modules/schedule_parser.py      ACTIVE      470     Парсинг расписания
modules/schedule_commands.py    ACTIVE      574     Команды расписания
modules/backup_commands.py      ACTIVE      379     Бэкап и миграции
embeddings.py                   ACTIVE      180     OpenAI embeddings
vector_store.py                 ACTIVE      260     FAISS индекс
draft_queue.py                  ACTIVE      304     Очередь черновиков

LEGACY (ДУБЛИРУЮЩИЕ)
cash_manager.py                 LEGACY      412     ⚠️ ДУБЛИРУЕТ finmon
club_manager.py                 LEGACY      503     ⚠️ ДУБЛИРУЕТ v2
club_manager_v2.py              LEGACY      916     ⚠️ ДУБЛИРУЕТ v1
finmon_shift_wizard.py          LEGACY      1646    ⚠️ ДУБЛИРУЕТ finmon/wizard
finmon_simple.py                LEGACY      379     ⚠️ Не используется

НЕИСПОЛЬЗУЕМЫЕ
finmon_analytics.py             UNUSED      0       ❌ Пусто
runtime_migrator.py             ACTIVE      200     Миграции (используется)

МЕНЕДЖЕРЫ В КОРНЕ
v2ray_manager.py                ACTIVE      1739    Управление прокси
product_manager.py              ACTIVE      826     Управление товаром
issue_manager.py                ACTIVE      282     Отслеживание проблем
content_generator.py            ACTIVE      309     Генерация контента
video_generator.py              ACTIVE      213     Генерация видео

КОМАНДЫ В КОРНЕ
v2ray_commands.py               ACTIVE      653     Команды V2Ray
product_commands.py             ACTIVE      746     Команды товара
issue_commands.py               ACTIVE      609     Команды проблем
cash_commands.py                ACTIVE      532     Команды финансов
club_commands.py                ACTIVE      543     Команды клубов
content_commands.py             ACTIVE      314     Команды контента
```

## Статистика проекта

### Размер кода
- **Всего строк Python:** ~17,000
- **Основной модуль (bot.py):** 3,772 строк (22% от всего кода)
- **Модули:** ~13,000 строк (76%)
- **Менеджеры и команды:** ~8,000 строк в корне

### Размер данных
- **club_assistant.db:** 49 KB
- **knowledge.db:** 4.5 MB
- **vector_index.faiss:** 43 MB (ПРОБЛЕМА: разбухает)
- **vector_metadata.pkl:** 197 KB
- **.embedding_cache/:** 311 MB (ПРОБЛЕМА: неконтролируемый рост)

### Команды
- **Всего команд:** 120+
- **ConversationHandlers:** 8+ (cash, product, clubs, issues, v2ray, и т.д.)
- **CommandHandlers:** 120+ команд
- **CallbackQueryHandlers:** 50+ кнопок

## Ключевые таблицы БД

```
ТАБЛИЦА                     НАЗНАЧЕНИЕ
────────────────────────────────────────────────────
admins                      Админы с ролями и правами
admin_credentials           Учётные данные (БЕЗ ШИФРОВАНИЯ!)
knowledge                   База знаний Q&A
active_shifts               Открытые смены
shift_cash_withdrawals      Списания денег в смене
salary_payments             Расчёты зарплат
finmon_shifts               История смен
finmon_balances             Текущие балансы касс
products                    Каталог товаров
admin_products              Товар взятый админами
club_issues                 Проблемы клуба
v2ray_servers               V2Ray серверы
_migrations                 Отслеживание миграций
```

## Входные точки (Entry Points)

### Главная функция
```python
def main():
    config = load_config()
    init_database()
    bot = ClubAssistantBot(config)
    bot.register_handlers()
    app.run_polling()
```

### Основные обработчики
1. **handle_message()** - обработка всех текстовых сообщений
2. **cmd_*** - 120+ функций команд
3. **ConversationHandlers** - диалоги с состояниями

## Интеграции

### OpenAI API
- Embeddings (text-embedding-3-small, 1536D)
- Chat completions (gpt-4o-mini, gpt-4o)
- Для: база знаний, автообучение, RAG

### Google Sheets
- gspread library
- Синхронизация смен и балансов
- Опциональная интеграция (graceful degradation)

### SSH/Paramiko
- V2Ray управление серверами
- Установка Xray
- Генерация REALITY конфигов

### Telegram
- python-telegram-bot 20.7
- Polling для получения обновлений
- ConversationHandler для FSM диалогов

## Конфигурация

### .env переменные
```
TELEGRAM_BOT_TOKEN          - токен бота
OPENAI_API_KEY              - ключ OpenAI
OWNER_TG_IDS                - ID владельцев (через запятую)
DB_PATH                     - путь к БД (по умолчанию knowledge.db)
BACKUP_DIR                  - папка бэкапов
BACKUP_INTERVAL_DAYS        - интервал бэкапа
FINMON_DB_PATH              - БД финмон
GOOGLE_SA_JSON              - путь к Google Service Account JSON
FINMON_SHEET_NAME           - имя листа Google Sheets
```

### config.json параметры
```json
{
  "telegram_token": "...",
  "openai_api_key": "...",
  "admin_ids": [123, 456],
  "owner_id": 123,
  "gpt_model": "gpt-4o-mini",
  "embedding_model": "text-embedding-3-small",
  "vector_search": {
    "top_k": 5,
    "min_score": 0.5
  }
}
```

## Миграции БД

Расположение: `/migrations/`

```
admins_001_init.sql                    - Инициализация админов
finmon_001_init.sql                    - Инициализация финмон
admin_shift_management_001_init.sql    - Управление сменами
add_shift_management.sql               - Добавление управления сменами
add_salary_system.sql                  - Система зарплат
add_payroll_system.sql                 - Система выплат
```

Применение: `python modules/runtime_migrator.py`

## Критические проблемы

### 🔴 БЕЗОПАСНОСТЬ
- Пароли хранятся в открытом виде в БД
- Нет шифрования credentials

### 🟠 ПРОИЗВОДИТЕЛЬНОСТЬ
- .embedding_cache/ разбухла на 311 MB
- vector_index.faiss растёт на 43 MB
- Медленное удаление из FAISS (переиндексация)

### 🟡 ПОДДЕРЖИВАЕМОСТЬ
- bot.py слишком большой (3772 строк)
- Дублирование кода (cash vs finmon, club v1 vs v2)
- SmartAutoLearner вызывает GPT дважды

### 🔵 ТЕСТИРОВАНИЕ
- Нет unit тестов
- Нет integration тестов
- Невозможно рефакторить

## Рекомендуемый порядок изучения

1. **Начните отсюда:**
   - README.md - обзор проекта
   - bot.py (строки 1-100) - импорты и конфиг
   - bot.py (строки 664-700) - инициализация ClubAssistantBot

2. **Затем изучите модули:**
   - modules/admins/__init__.py - как регистрируются handlers
   - modules/finmon/__init__.py - как работает ConversationHandler
   - modules/shift_manager.py - логика управления сменами

3. **Глубокое изучение:**
   - bot.py (3200-3450) - регистрация всех handlers
   - modules/admins/db.py - система ролей и разрешений
   - modules/finmon/wizard.py - FSM для пошагового ввода

4. **Специализированные системы:**
   - v2ray_manager.py - управление прокси серверами
   - salary_calculator.py - расчет зарплат
   - schedule_parser.py - парсинг расписания

## Команды для разработки

```bash
# Запуск бота локально
python3 bot.py

# Применение миграций
python3 modules/runtime_migrator.py

# Проверка конфига
python3 -c "import json; json.load(open('config.json'))"

# Логирование (в production)
sudo journalctl -u club_assistant -f

# Перезапуск сервиса
sudo systemctl restart club_assistant
```

## Полезные файлы документации

- `FULL_PROJECT_ANALYSIS.md` - полный анализ (этот файл основан на нём)
- `README.md` - основная документация
- `ENHANCED_ADMIN_SHIFT_GUIDE.md` - система управления сменами
- `GOOGLE_SHEETS_SETUP.md` - настройка Google Sheets
- `SALARY_GUIDE.md` - система расчета зарплат
- `SCHEDULE_GUIDE.md` - система расписания
- `modules/admins/README.md` - документация админ-модуля

---

**Дата создания:** 29 октября 2025
**Версия проекта:** v4.15
**Статус:** Production (с проблемами в production-ready)

