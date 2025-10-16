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

# 4. Запусти бота
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
