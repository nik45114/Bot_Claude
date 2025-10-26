# 🤖 Club Assistant Bot v4.11

## 🎯 Что нового в v4.11

### 🔐 V2Ray Manager
Управление прокси-серверами через бота:
- Установка V2Ray одной командой
- Автогенерация VLESS ссылок
- Маскировка трафика (TCP/WS/gRPC/TLS)
- Управление пользователями

### 🏢 Club Management System
Контроль за админами и клубами:
- Красивые отчёты смен с автопарсингом
- Учёт финансов (наличка, безнал, QR)
- Контроль оборудования
- Отслеживание расходников
- Сводка по проблемам
- Статистика по клубам

---

## 📋 Основные возможности

### 💬 Умный бот
- RAG (Retrieval-Augmented Generation)
- Векторный поиск по базе знаний
- Автообучение в группах
- GPT-4 fallback

### 👥 Управление админами
- Добавление/удаление админов
- Права доступа
- Хранение учётных данных

### 📊 База знаний
- Автоматическая категоризация
- Дедупликация
- Версионирование
- Очистка и оптимизация

---

## 🚀 Установка

### Требования
- Ubuntu 20.04+
- Python 3.8+
- Systemd

### Быстрый старт

```bash
# 1. Клонируй репозиторий
cd /opt
git clone https://github.com/nik45114/Bot_Claude.git club_assistant
cd club_assistant

# 2. Установи зависимости
pip3 install -r requirements.txt --break-system-packages

# 3. Настрой конфиг
cp config.json.example config.json
nano config.json

# Добавь:
# - telegram_token
# - openai_api_key
# - admin_ids
# - owner_id (для V2Ray и Club Management)

# 4. Настрой переменные окружения
cp .env.example .env
nano .env

# Обязательные параметры:
# - TELEGRAM_BOT_TOKEN
# - OPENAI_API_KEY
# - OWNER_TG_IDS (через запятую для нескольких владельцев)
#
# Опциональные:
# - DB_PATH (по умолчанию: knowledge.db)
# - BACKUP_DIR (по умолчанию: ./backups)
# - BACKUP_INTERVAL_DAYS (по умолчанию: 14)
# - GOOGLE_SA_JSON (для синхронизации с Google Sheets)

# 5. Запусти миграции базы данных
python3 run_migrations.py

# 6. Запусти бота
python3 bot.py
```

### Автозапуск через systemd

```bash
# Создай сервис
sudo nano /etc/systemd/system/club_assistant.service
```

```ini
[Unit]
Description=Club Assistant Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/club_assistant
ExecStart=/usr/bin/python3 /opt/club_assistant/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Запусти
sudo systemctl daemon-reload
sudo systemctl enable club_assistant
sudo systemctl start club_assistant

# Проверь статус
sudo systemctl status club_assistant
```

---

## 📖 Команды

### 🤖 Основные
```
/start - Старт
/help - Справка
/stats - Статистика базы
```

### 📚 База знаний
```
/search <запрос> - Поиск
/teach <вопрос> | <ответ> - Добавить знание
/forget <id> - Удалить запись
/category <id> <категория> - Изменить категорию
```

### 👥 Админы
```
/addadmin <user_id> - Добавить админа
/admins - Список админов
/savecreds <сервис> <логин> <пароль> - Сохранить учётку
/getcreds - Получить учётки
```

### 🧹 Обслуживание
```
/cleanup - Очистка дубликатов
/fixdb - Исправление базы
/deletetrash - Удаление мусора
/fixjson - Исправление JSON в ответах
/import - Импорт данных
```

### 🔐 V2Ray (только owner)
```
/v2ray - Главное меню
/v2add <имя> <host> <user> <pass> - Добавить сервер
/v2setup <имя> - Установить V2Ray
/v2user <сервер> <user_id> [email] - Добавить пользователя
/v2list - Список серверов
/v2stats <имя> - Статистика
/v2traffic <сервер> <тип> - Изменить трафик
```

### 🏢 Клубы (только owner)
```
/clubs - Главное меню
/clubadd <название> <адрес> - Добавить клуб
/clublist - Список клубов
/report <клуб> - Отчёт смены
/lastreport <клуб> - Последний отчёт
/clubstats <клуб> [дней] - Статистика
/issues [клуб] - Проблемы
```

### 💰 FinMon - Финансовый мониторинг
```
/shift - Сдать смену (кнопочный визард)
/balances - Текущие балансы касс
/shifts - Последние смены
```

### 💾 Резервное копирование (только owner)
```
/migration - Отправить файлы миграций БД
/backup - Создать и отправить полный бэкап
```

---

## 🗃️ База данных и миграции

### Структура БД

Бот использует SQLite для хранения данных. Основные таблицы:
- `knowledge` - база знаний
- `admins` - список администраторов
- `finmon_clubs` - клубы для финансового мониторинга
- `finmon_balances` - текущие балансы касс
- `finmon_shifts` - история сдачи смен
- `finmon_movements` - история движений денег

### Миграции

Миграции находятся в папке `migrations/` и применяются автоматически при первом запуске бота.

Для ручного применения миграций:

```bash
python3 run_migrations.py
```

Миграции отслеживаются в таблице `_migrations` и применяются только один раз.

### Автоматическая отправка миграций

Бот автоматически отправляет файлы миграций владельцу каждые N дней (настраивается в `.env`).

Параметры в `.env`:
```bash
BACKUP_INTERVAL_DAYS=14  # Интервал отправки (дней)
OWNER_TG_IDS=123456789   # ID владельца
```

### Резервное копирование

Владелец может в любой момент запросить:
- `/migration` - получить архив с SQL-файлами миграций
- `/backup` - получить полный бэкап (SQLite DB + JSON/CSV файлы)

Автоматическое резервное копирование настраивается через переменную `BACKUP_INTERVAL_DAYS`.

---

## 🔧 Обновление

### Автоматическое (рекомендуется)

```bash
# В боте:
/update

# Или вручную:
cd /opt/club_assistant
bash update.sh
```

### update.sh
```bash
#!/bin/bash
cd /opt/club_assistant
git pull origin main
pip3 install -r requirements.txt --break-system-packages
systemctl restart club_assistant
```

---

## 📊 Архитектура v4.11

```
club_assistant/
├── bot.py                  # Главный файл бота
├── embeddings.py           # Сервис эмбеддингов (OpenAI)
├── vector_store.py         # Векторное хранилище
├── draft_queue.py          # Очередь черновиков
├── v2ray_manager.py        # V2Ray управление
├── v2ray_commands.py       # V2Ray команды
├── club_manager.py         # Club управление
├── club_commands.py        # Club команды
├── knowledge.db            # SQLite база
├── vectors.npy             # Векторы для поиска
├── config.json             # Конфигурация
└── requirements.txt        # Зависимости
```

---

## ⚙️ Конфигурация

### config.json
```json
{
  "telegram_token": "YOUR_BOT_TOKEN",
  "openai_api_key": "YOUR_OPENAI_KEY",
  "admin_ids": [123456789],
  "owner_id": 123456789,
  "gpt_model": "gpt-4o-mini",
  "embedding_model": "text-embedding-3-small",
  "vector_search": {
    "top_k": 5,
    "min_score": 0.5
  }
}
```

### Параметры:
- **telegram_token** - токен бота от @BotFather
- **openai_api_key** - ключ OpenAI API
- **admin_ids** - список ID админов
- **owner_id** - ID владельца (для V2Ray и Clubs)
- **gpt_model** - модель GPT (gpt-4o-mini / gpt-4o)
- **embedding_model** - модель эмбеддингов

---

## 🎯 Примеры использования

### База знаний
```
Админ: /teach Что делать если ПК не включается? | Проверь кабель питания, попробуй другую розетку, проверь кнопку включения

Пользователь: ПК не включается
Бот: Проверь кабель питания, попробуй другую розетку, проверь кнопку включения
```

### V2Ray
```
Owner: /v2add main 185.123.45.67 root MyPass123
       /v2setup main
       /v2user main @username Вася

Бот: ✅ Пользователь добавлен!
     🔗 VLESS ссылка:
     vless://uuid@185.123.45.67:443?type=tcp#username
```

### Отчёты клубов
```
Админ: /report Центральный

Бот: 📋 Отчёт смены - Центральный
     Отправь отчёт в любом формате.

Админ: [отправляет текст отчёта]

Бот: [красивый отчёт с финансами, оборудованием, расходниками]
```

---

## 🔒 Безопасность

- **owner_id** - только владелец имеет доступ к V2Ray и Club Management
- **admin_ids** - админы могут управлять базой знаний
- Учётные данные хранятся зашифрованными
- SSH данные для V2Ray шифруются
- История всех изменений в базе

---

## 📚 Документация

- [V2RAY_GUIDE.md](V2RAY_GUIDE.md) - Руководство по V2Ray
- [CLUB_MANAGEMENT_GUIDE.md](CLUB_MANAGEMENT_GUIDE.md) - Руководство по Club Management
- [UPDATE_TO_V4.11.md](UPDATE_TO_V4.11.md) - Инструкция по обновлению

---

## 🐛 Траблшутинг

### Бот не запускается
```bash
# Проверь логи
sudo journalctl -u club_assistant -f

# Проверь конфиг
python3 -c "import json; json.load(open('config.json'))"

# Проверь зависимости
pip3 install -r requirements.txt --break-system-packages
```

### Ошибки в базе
```bash
# В боте:
/fixdb       # Исправление базы
/cleanup     # Очистка дубликатов
/deletetrash # Удаление мусора
```

### V2Ray не подключается
```bash
# Проверь SSH доступ
ssh root@185.123.45.67

# Проверь порт
ufw allow 443
```

### Отчёты не парсятся
```bash
# Проверь формат
Минимум:
- Тип смены (Утро/День/Вечер/Ночь)
- Дата (15.10)
- Хотя бы одна цифра (финансы)
```

---

## 💡 Полезные советы

### Производительность
- Используй `gpt-4o-mini` для экономии
- Векторный поиск быстрее GPT
- Очищай базу регулярно: `/cleanup`

### Обучение
- Добавляй только важное
- Используй категории
- Дедуплицируй: `/cleanup`

### Отчёты
- Админы сдают отчёты после каждой смены
- Бот парсит любой формат
- Проблемы автоматически попадают в `/issues`

---

## 💰 FinMon Module - Финансовый мониторинг

### 📋 Описание
Модуль для удобной "Сдачи смены" админами компьютерных клубов с автоматической синхронизацией в Google Sheets.

### 🎯 Функционал

**Команды:**
- `/shift` - Сдать смену (пошаговый wizard с кнопками)
- `/balances` - Показать текущие остатки по кассам
- `/shifts` - Показать последние 10 смен (владельцу - все)

**Процесс сдачи смены:**
1. Выбор клуба (Рио офиц/коробка, Мичуринская офиц/коробка)
2. Выбор времени смены (утро/вечер)
3. Пошаговый ввод данных:
   - Выручка: fact_cash, fact_card, qr, card2
   - Кассы: safe_cash_end, box_cash_end, goods_cash
   - Расходы: compensations, salary_payouts, other_expenses
   - Инвентарь: joysticks_total, joysticks_in_repair, joysticks_need_repair, games_count
   - Хозяйство: toilet_paper, paper_towels
   - Примечания: notes
4. Показ сводки для подтверждения
5. Сохранение в SQLite + Google Sheets

### 📁 Структура модуля

```
modules/finmon/
├── __init__.py           # Регистрация модуля
├── db.py                 # Работа с SQLite
├── models.py             # Pydantic модели
├── wizard.py             # Conversation handler для ввода данных
└── sheets.py             # Интеграция с Google Sheets

migrations/
└── finmon_001_init.sql   # SQL миграция таблиц
```

### ⚙️ Настройка

**Переменные окружения (.env):**
```env
# FinMon Configuration
FINMON_DB_PATH=knowledge.db
FINMON_SHEET_NAME=ClubFinance
GOOGLE_SA_JSON=/opt/club_assistant/service-account.json
OWNER_TG_IDS=123456789,987654321
```

**Google Sheets Setup:**
1. Создать service account в Google Cloud Console
2. Скачать JSON ключ в `/opt/club_assistant/service-account.json`
3. Дать доступ к Google Sheets email из JSON

### 🎨 Пример сводки смены

```
[Рио офиц] Утро 20.10
━━━━━━━━━━━━━━━━━━━━
Факт нал: 2 640 ₽ | Сейф: 927 ₽
Факт безнал: 5 547 ₽ | QR: 1 680 ₽ | Новая касса: 0 ₽
Товарка (нал): 1 000 ₽ | Коробка (нал): 5 124 ₽
Комп/зп/прочие: -650 / 3 000 / 0 ₽

Геймпады: 153 (ремонт: 3, требуется: 3)
Игр: 31

Туалетка: есть | Полотенца: нет

Примечание: Все ОК
```

### 📊 Google Sheets структура

**Лист "Shifts":**
- Дата, Время, Клуб, Админ
- Факт нал, Факт безнал, QR, Новая касса
- Сейф, Коробка, Товарка
- Комп, ЗП, Прочие
- Геймпады, Ремонт, Требуется, Игр
- Туалетка, Полотенца, Примечание

**Лист "Balances":**
- Клуб, Тип кассы, Баланс, Обновлено

### 💡 Особенности

- **Wizard на python-telegram-bot FSM** - пошаговый ввод с валидацией
- **Inline кнопки** - для выбора клуба и подтверждения
- **Красивое форматирование** - сводка с эмодзи и выравниванием
- **Безопасность** - только владельцы видят все смены
- **Google Sheets sync** - автоматическая синхронизация данных (опционально)
- **Валидация** - Pydantic модели для проверки данных

---

## 📈 Roadmap

### v4.12 (планируется)
- [ ] Web-интерфейс для управления
- [ ] Telegram Web App для отчётов
- [ ] Экспорт отчётов в Excel
- [ ] Уведомления о проблемах
- [ ] Интеграция с CRM

### v5.0 (будущее)
- [ ] Мультиклубовость
- [ ] Роли и права
- [ ] API для интеграций
- [ ] Dashboard с аналитикой

---

## 📞 Поддержка

- GitHub Issues: https://github.com/nik45114/Bot_Claude/issues
- Telegram: @nik45114

---

## 📄 Лицензия

MIT License

---

## ✨ Версии

### v4.11 (текущая)
- ✅ V2Ray Manager
- ✅ Club Management System
- ✅ Автопарсинг отчётов
- ✅ ConversationHandler для отчётов

### v4.10
- ✅ Исправление автообучения
- ✅ Улучшенные фильтры

### v4.0-4.9
- ✅ RAG архитектура
- ✅ Векторный поиск
- ✅ Автообучение
- ✅ Draft queue

### v3.0
- ✅ Базовая база знаний
- ✅ GPT интеграция

---

**🚀 Club Assistant Bot v4.11 - Всё в одном боте!**
