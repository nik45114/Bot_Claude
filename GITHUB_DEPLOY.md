# 🚀 Деплой на GitHub - v4.11

## 📦 Файлы для загрузки

### Основные файлы бота:
```
bot.py                      # Главный бот (bot_v4.10.py → bot.py)
embeddings.py               # Эмбеддинги
vector_store.py             # Векторное хранилище
draft_queue.py              # Черновики
```

### V2Ray модули:
```
v2ray_manager.py            # V2Ray управление
v2ray_commands.py           # V2Ray команды
```

### Club модули:
```
club_manager.py             # Club управление
club_commands.py            # Club команды
```

### Конфигурация:
```
config.json.example         # Пример конфига
requirements.txt            # Зависимости
update.sh                   # Скрипт обновления
```

### Документация:
```
README.md                   # Главный README (README_V4.11.md → README.md)
UPDATE_TO_V4.11.md          # Инструкция по обновлению
V2RAY_GUIDE.md              # Руководство по V2Ray
CLUB_MANAGEMENT_GUIDE.md    # Руководство по Club Management
```

---

## 🔄 Процесс деплоя

### 1. Подготовка репозитория

```bash
cd /path/to/Bot_Claude

# Проверь статус
git status

# Посмотри что изменилось
git diff
```

### 2. Добавление файлов

```bash
# Основные файлы
git add bot.py
git add embeddings.py
git add vector_store.py
git add draft_queue.py

# V2Ray
git add v2ray_manager.py
git add v2ray_commands.py

# Clubs
git add club_manager.py
git add club_commands.py

# Конфиг
git add config.json.example
git add requirements.txt
git add update.sh

# Документация
git add README.md
git add UPDATE_TO_V4.11.md
git add V2RAY_GUIDE.md
git add CLUB_MANAGEMENT_GUIDE.md
```

### 3. Коммит

```bash
git commit -m "v4.11: Added V2Ray Manager + Club Management System

Features:
- V2Ray proxy management via bot
- Club reports with auto-parsing
- Finance & equipment tracking
- Issues monitoring
- Beautiful formatted reports

New modules:
- v2ray_manager.py
- v2ray_commands.py
- club_manager.py
- club_commands.py

Updated:
- bot.py (integrated new modules)
- README.md (v4.11 docs)
- requirements.txt (added paramiko)
"
```

### 4. Пуш на GitHub

```bash
# Проверь ремоут
git remote -v

# Должно быть:
# origin  https://github.com/nik45114/Bot_Claude.git (fetch)
# origin  https://github.com/nik45114/Bot_Claude.git (push)

# Пуш
git push origin main

# Или если первый раз:
git push -u origin main
```

### 5. Создание Release (опционально)

На GitHub:
1. Зайди в Releases
2. "Draft a new release"
3. Tag: `v4.11`
4. Title: `v4.11 - V2Ray + Club Management`
5. Description:
```markdown
## 🎉 v4.11 - Major Update

### 🔐 V2Ray Manager
- Install V2Ray with one command
- Auto-generate VLESS links
- Traffic masking (TCP/WS/gRPC/TLS)
- User management

### 🏢 Club Management System
- Auto-parsed shift reports
- Finance tracking (cash/card/QR)
- Equipment monitoring
- Supplies tracking
- Issues summary
- Club statistics

### 📦 Installation
```bash
cd /opt
git clone https://github.com/nik45114/Bot_Claude.git club_assistant
cd club_assistant
pip3 install -r requirements.txt --break-system-packages
cp config.json.example config.json
nano config.json  # Add your tokens
python3 bot.py
```

### 📚 Documentation
- [V2RAY_GUIDE.md](V2RAY_GUIDE.md)
- [CLUB_MANAGEMENT_GUIDE.md](CLUB_MANAGEMENT_GUIDE.md)
- [UPDATE_TO_V4.11.md](UPDATE_TO_V4.11.md)
```

6. Publish release

---

## 📋 Проверка деплоя

### На GitHub:

1. Зайди: https://github.com/nik45114/Bot_Claude
2. Проверь что файлы загружены
3. Проверь что README обновился
4. Проверь commit message

### На сервере:

```bash
cd /opt/club_assistant

# Пул
git pull origin main

# Проверь файлы
ls -la | grep -E "(v2ray|club)"

# Должно быть:
# v2ray_manager.py
# v2ray_commands.py
# club_manager.py
# club_commands.py

# Проверь конфиг
cat config.json.example

# Должно быть owner_id

# Обнови
pip3 install -r requirements.txt --break-system-packages

# Перезапусти
systemctl restart club_assistant

# Проверь
systemctl status club_assistant
```

---

## 🎯 .gitignore

Убедись что эти файлы **НЕ** в git:

```gitignore
# Локальные файлы
config.json           # НЕ загружай! Только config.json.example
knowledge.db          # База данных
vectors.npy           # Векторы
*.pyc
__pycache__/
.DS_Store

# Логи
*.log
logs/

# Виртуальное окружение
venv/
env/
```

Проверка:
```bash
cat .gitignore

# Если нет .gitignore, создай:
cat > .gitignore << EOF
config.json
knowledge.db
vectors.npy
*.pyc
__pycache__/
.DS_Store
*.log
logs/
venv/
env/
EOF

git add .gitignore
git commit -m "Added .gitignore"
```

---

## 🔒 Безопасность

### ⚠️ НИКОГДА НЕ ЗАГРУЖАЙ:

- `config.json` - содержит токены!
- `knowledge.db` - может содержать приватные данные
- Любые файлы с паролями, токенами, SSH ключами

### ✅ Загружай только:

- `config.json.example` - без реальных токенов
- Код (.py файлы)
- Документацию (.md файлы)
- Конфигурационные примеры

---

## 📝 Коммиты - Best Practices

### Хорошие коммиты:
```bash
git commit -m "v4.11: Added V2Ray Manager + Club Management"
git commit -m "Fixed: Report parsing for negative numbers"
git commit -m "Updated: Documentation for v4.11"
```

### Плохие коммиты:
```bash
git commit -m "update"
git commit -m "fix"
git commit -m "changes"
```

### Структура коммита:
```
<type>: <subject>

<body>

<footer>
```

Примеры типов:
- `feat:` - новая функция
- `fix:` - исправление бага
- `docs:` - документация
- `refactor:` - рефакторинг кода
- `test:` - тесты

---

## 🔄 Workflow обновления

### Для пользователей (на сервере):

```bash
cd /opt/club_assistant

# 1. Пул
git pull origin main

# 2. Обнови зависимости
pip3 install -r requirements.txt --break-system-packages

# 3. Обнови конфиг (если нужно)
nano config.json

# 4. Перезапусти
systemctl restart club_assistant
```

### Через бота:
```
/update
```

update.sh должен быть:
```bash
#!/bin/bash
cd /opt/club_assistant
git pull origin main
pip3 install -r requirements.txt --break-system-packages
systemctl restart club_assistant
```

---

## 🎉 Финал

После деплоя на GitHub:

1. ✅ Код доступен: https://github.com/nik45114/Bot_Claude
2. ✅ Документация обновлена
3. ✅ Пользователи могут обновиться: `git pull`
4. ✅ Версия v4.11 опубликована

---

## 📞 Если проблемы

### GitHub не принимает пуш:
```bash
# Проверь авторизацию
git config --global user.name "Your Name"
git config --global user.email "your@email.com"

# Если нужен токен:
# Settings → Developer settings → Personal access tokens
# Создай токен с repo правами
# Используй токен вместо пароля при пуше
```

### Конфликты при пуше:
```bash
# Пул с ребейзом
git pull --rebase origin main

# Разреши конфликты
# Продолжи
git rebase --continue

# Пуш
git push origin main
```

---

**🚀 v4.11 готов к деплою!**
