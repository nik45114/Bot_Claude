# 🚀 Обновление до v4.11

## 📋 Что нового

### 🔐 V2Ray Manager
- Установка прокси одной командой
- Генерация VLESS ссылок
- Управление трафиком
- SSH менеджмент

### 🏢 Club Management System
- Автопарсинг отчётов смен
- Красивое форматирование
- Учёт финансов и оборудования
- Сводка по проблемам
- Статистика клубов

---

## ⚡ БЫСТРОЕ ОБНОВЛЕНИЕ

```bash
cd /opt/club_assistant

# Пул с GitHub
git pull origin main

# Обнови зависимости
pip3 install -r requirements.txt --break-system-packages

# Обнови конфиг
nano config.json
# Добавь: "owner_id": 123456789

# Перезапусти
systemctl restart club_assistant

# Проверь
systemctl status club_assistant
```

**Готово!** ✅

---

## 📦 Новые файлы v4.11

```
/opt/club_assistant/
├── v2ray_manager.py        # NEW - V2Ray управление
├── v2ray_commands.py       # NEW - V2Ray команды
├── club_manager.py         # NEW - Club управление
├── club_commands.py        # NEW - Club команды
├── bot.py                  # UPDATED - основной бот
└── config.json             # UPDATED - добавлен owner_id
```

---

## ⚙️ Обновление config.json

### Было:
```json
{
  "telegram_token": "...",
  "openai_api_key": "...",
  "admin_ids": [123456789]
}
```

### Стало:
```json
{
  "telegram_token": "...",
  "openai_api_key": "...",
  "admin_ids": [123456789],
  "owner_id": 123456789      ← ДОБАВЬ СВОЙ ID
}
```

**owner_id** - только этот пользователь может использовать V2Ray и Club Management!

---

## 📊 База данных

База автоматически обновится при запуске. Добавятся таблицы:

### V2Ray:
- `v2ray_servers` - серверы
- `v2ray_users` - пользователи

### Clubs:
- `clubs` - клубы
- `shifts` - смены
- `shift_finance` - финансы
- `shift_equipment` - оборудование
- `shift_supplies` - расходники
- `shift_issues` - проблемы

**Старые данные не затронуты!**

---

## 🎯 Проверка после обновления

### 1. Проверь бота
```bash
systemctl status club_assistant

# Должно быть:
● club_assistant.service - Club Assistant Bot
   Active: active (running)
```

### 2. Проверь команды в Telegram

```
/start

Должно быть:
👋 Привет!
Я ассистент клуба v4.11.
```

### 3. Проверь V2Ray (только owner)
```
/v2ray

Должно быть:
🔐 V2Ray Manager
Команды: ...
```

### 4. Проверь Clubs (только owner)
```
/clubs

Должно быть:
🏢 Управление клубами
Команды: ...
```

---

## 🔐 V2Ray - Быстрый старт

```bash
# 1. Добавь сервер
/v2add main 185.123.45.67 root MyPass123

# 2. Установи V2Ray
/v2setup main

# 3. Добавь пользователя
/v2user main @username Вася

# 4. Получи VLESS ссылку
→ vless://uuid@185.123.45.67:443...
```

Подробнее: [V2RAY_GUIDE.md](V2RAY_GUIDE.md)

---

## 🏢 Club Management - Быстрый старт

```bash
# 1. Добавь клубы
/clubadd Центральный Ленина 123
/clubadd Северный Пушкина 45

# 2. Админ сдаёт отчёт
/report Центральный

→ Бот: 📋 Отчёт смены - Центральный
       Отправь отчёт в любом формате.

→ Админ: [текст отчёта]

→ Бот: [красивый отчёт]

# 3. Смотришь статистику
/clubstats Центральный
/issues
```

Подробнее: [CLUB_MANAGEMENT_GUIDE.md](CLUB_MANAGEMENT_GUIDE.md)

---

## 🐛 Решение проблем

### Бот не запускается после обновления

```bash
# Проверь логи
sudo journalctl -u club_assistant -n 50

# Проверь зависимости
pip3 install paramiko==3.4.0 --break-system-packages

# Проверь конфиг
python3 -c "import json; json.load(open('/opt/club_assistant/config.json'))"
```

### ImportError: No module named 'club_manager'

```bash
cd /opt/club_assistant
git pull origin main

# Проверь что файлы скачались
ls -la club_manager.py club_commands.py v2ray_manager.py v2ray_commands.py
```

### V2Ray команды не работают

```bash
# Проверь owner_id в config.json
cat /opt/club_assistant/config.json | grep owner_id

# Должно быть:
"owner_id": 123456789,

# Проверь paramiko
pip3 show paramiko
```

### Clubs команды не работают

```bash
# Проверь что модули загружены
python3 -c "from club_manager import ClubManager; print('OK')"
python3 -c "from club_commands import ClubCommands; print('OK')"
```

---

## 📝 Миграция данных

### Если у тебя были свои таблицы для клубов

```sql
-- Экспорт старых данных
sqlite3 knowledge.db "SELECT * FROM old_clubs;" > old_clubs.csv

-- Импорт в новые таблицы через бота
-- (напиши если нужна помощь)
```

---

## 🎨 Кастомизация

### Изменить типы смен

В `club_manager.py`:
```python
shift_types = {
    'утро': 'morning',
    'день': 'day', 
    'вечер': 'evening',
    'ночь': 'night',
    'выходной': 'weekend'  # добавь свой
}
```

### Изменить поля отчёта

В `club_manager.py` метод `parse_report()` добавь свои регулярки.

---

## 🔄 Откат на v4.10

Если что-то пошло не так:

```bash
cd /opt/club_assistant

# Откат на предыдущую версию
git log --oneline
git checkout <commit_v4.10>

# Или
git checkout v4.10

# Перезапусти
systemctl restart club_assistant
```

---

## ✅ Чек-лист обновления

- [ ] Сделал бекап базы: `cp knowledge.db knowledge.db.backup`
- [ ] Сделал `git pull origin main`
- [ ] Обновил `requirements.txt`
- [ ] Добавил `owner_id` в config.json
- [ ] Перезапустил бота
- [ ] Проверил `/start`
- [ ] Проверил `/v2ray` (owner)
- [ ] Проверил `/clubs` (owner)
- [ ] Проверил логи: `journalctl -u club_assistant -f`

---

## 📞 Поддержка

Если проблемы:
1. Проверь логи: `journalctl -u club_assistant -n 100`
2. Проверь issues: https://github.com/nik45114/Bot_Claude/issues
3. Напиши мне: @nik45114

---

## 🎉 Готово!

**Теперь у тебя:**
- ✅ V2Ray Manager для прокси
- ✅ Club Management для отчётов
- ✅ Автопарсинг любых форматов
- ✅ Красивая статистика
- ✅ Контроль проблем

**Всё в одном боте!** 🚀
