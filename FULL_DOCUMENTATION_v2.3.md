# Club Assistant Bot v2.3 - Полнофункциональная версия

## Что нового в v2.3

### 1. Версионирование знаний
✅ Старые ответы не удаляются, а уходят в legacy
✅ Можно посмотреть историю изменений любого вопроса
✅ Команда `/history вопрос` показывает все версии

### 2. Система администраторов
✅ Многоуровневые права доступа
✅ Роли: обучение, импорт, управление
✅ Добавление/удаление админов через бота
✅ Отслеживание кто обучил бота

### 3. Личные данные
✅ Каждый админ может сохранять свои логины/пароли
✅ Команды `/savecreds` и `/getcreds`
✅ Безопасное хранение в БД (сообщения удаляются)

### 4. Health Check
✅ Команда `/health` - полная диагностика
✅ Проверка БД, OpenAI API, GitHub, памяти, uptime

### 5. Улучшенное обновление
✅ `/update` теперь обновляет ВСЁ из репозитория
✅ Автоматический перезапуск после обновления
✅ Показывает что изменилось

---

## Структура базы данных

### Таблица `knowledge`
```sql
- id
- question
- answer  
- category
- tags
- source
- added_by (user_id кто добавил)
- version (номер версии)
- is_current (1 = актуальная, 0 = legacy)
- created_at
- updated_at
```

### Таблица `admins`
```sql
- user_id (PRIMARY KEY)
- username
- full_name
- added_by
- can_teach (может обучать)
- can_import (может импортировать)
- can_manage_admins (может управлять админами)
- is_active
- created_at
```

### Таблица `admin_credentials`
```sql
- id
- user_id
- service (название сервиса)
- login
- password
- notes
- created_at
- updated_at
```

### Таблица `health_checks`
```sql
- id
- check_type
- status
- details
- checked_at
```

---

## Команды бота

### Для всех пользователей
- **Любой вопрос** - получить ответ
- `/start` - справка
- `/stats` - статистика

### Для администраторов

#### Обучение (право: can_teach)
- `/learn текст` - умное обучение
- `/history вопрос` - история изменений

#### Импорт (право: can_import)
- `/import` - импорт из CSV/JSONL
- Отправка файла - автоимпорт

#### Личные данные (все админы)
- `/savecreds сервис логин пароль [заметки]`
- `/getcreds [сервис]`

#### Системные (все админы)
- `/health` - проверка здоровья
- `/forget слово` - удалить записи
- `/update` - обновить с GitHub

#### Управление админами (только главный админ)
- `/addadmin @username Имя_Фамилия [права]`
- `/listadmins` - список админов
- `/rmadmin user_id` - удалить админа

---

## Примеры использования

### 1. Версионирование

**Сценарий:** Пароль от BIOS изменился

```
Админ1: /learn Пароль от BIOS: admin123
Бот: Запомнил!

[Через месяц пароль меняют]

Админ2: /learn Пароль от BIOS: newpass456
Бот: Запомнил!

Пользователь: пароль от биос?
Бот: newpass456

Админ: /history Пароль от BIOS?
Бот: История: 'Пароль от BIOS?'

     v2 (актуальный)
     Ответ: newpass456
     Создан: 2025-02-15
     Автор: 987654321

     v1 (legacy)
     Ответ: admin123
     Создан: 2025-01-15
     Автор: 123456789
```

### 2. Добавление администратора

```
ГлавныйАдмин: /addadmin @ivan Иван_Петров teach,import
Бот: Добавить администратора?

     Username: @ivan
     Имя: Иван Петров
     Права:
       • Обучение: да
       • Импорт: да
       • Управление: нет

     Для подтверждения пусть @ivan напишет боту:
     /confirmadmin

[Иван пишет боту]
Иван: /confirmadmin
Бот: Вы добавлены как администратор!

     Ваши права:
     • Обучение бота (/learn)
     • Просмотр статистики (/stats)
```

### 3. Сохранение личных данных

```
Админ: /savecreds auth_panel admin pass123 Доступ к админке
Бот: Данные для 'auth_panel' сохранены
[Сообщение удаляется автоматически]

[Позже]
Админ: /getcreds auth_panel
Бот: Ваши сохранённые данные:

     Сервис: auth_panel
     Логин: admin
     Пароль: pass123
     Заметки: Доступ к админке
     Создано: 2025-02-15 14:30
```

### 4. Health Check

```
Админ: /health
Бот: Проверка здоровья бота:

     ✅ База данных: OK
        156 записей

     ✅ OpenAI API: OK
        Доступен

     ✅ GitHub: OK
        https://github.com/user/repo.git

     ✅ Память: OK
        87.3 MB

     ✅ Uptime: OK
        48.2 часов
```

### 5. Обновление с GitHub

```
Админ: /update
Бот: Обновляю с GitHub...

Бот: Обновление загружено!

     Изменения:
     Updating abc123..def456
     Fast-forward
      bot.py | 45 ++++++++++++++++++++++++++++++
      1 file changed, 45 insertions(+)

     Перезапускаю бота...

[Бот перезапускается автоматически]
```

---

## Права доступа

### Роли администраторов

#### 1. Главный администратор (из config.json)
- Все права
- Может управлять другими админами
- Может назначать любые права

#### 2. Администратор с правом "teach"
- Может обучать бота (`/learn`)
- Может смотреть историю (`/history`)
- Может сохранять свои данные (`/savecreds`)
- НЕ может импортировать
- НЕ может управлять админами

#### 3. Администратор с правом "import"
- Все права "teach"
- Может импортировать данные (`/import`)
- НЕ может управлять админами

#### 4. Администратор с правом "manage"
- Все права "import"
- Может добавлять/удалять админов
- Полные права (как главный админ)

---

## Установка и обновление

### Первая установка

```bash
cd /opt/club_assistant

# 1. Замените bot.py новой версией v2.3
# 2. Обновите requirements.txt

# 3. Установите новые зависимости
source venv/bin/activate
pip install -r requirements.txt

# 4. Перезапустите
systemctl restart club_assistant

# 5. Проверьте
systemctl status club_assistant
```

### Обновление через GitHub

```bash
# Залейте v2.3 на GitHub
cd /opt/club_assistant
git add bot.py requirements.txt
git commit -m "v2.3: версионирование, админы, личные данные, health check"
git push origin main

# В Telegram боту
/update

# Бот перезапустится автоматически
```

---

## Миграция базы данных

Если у вас уже есть БД без новых полей:

```bash
cd /opt/club_assistant

# Сделайте бэкап
cp knowledge.db knowledge.db.backup

# Запустите бота - он автоматически обновит структуру
systemctl restart club_assistant
```

Или вручную:

```sql
-- Добавляем новые поля в knowledge
ALTER TABLE knowledge ADD COLUMN tags TEXT DEFAULT '';
ALTER TABLE knowledge ADD COLUMN source TEXT DEFAULT '';
ALTER TABLE knowledge ADD COLUMN added_by INTEGER;
ALTER TABLE knowledge ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE knowledge ADD COLUMN is_current BOOLEAN DEFAULT 1;

-- Создаём индекс
CREATE INDEX IF NOT EXISTS idx_current ON knowledge(is_current);

-- Создаём таблицу админов
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    added_by INTEGER,
    can_teach BOOLEAN DEFAULT 1,
    can_import BOOLEAN DEFAULT 0,
    can_manage_admins BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создаём таблицу credentials
CREATE TABLE IF NOT EXISTS admin_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    service TEXT NOT NULL,
    login TEXT,
    password TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES admins(user_id)
);

-- Создаём таблицу health_checks
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_type TEXT,
    status TEXT,
    details TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Безопасность

### Личные данные админов

⚠️ **ВАЖНО:** Пароли хранятся в открытом виде в БД!

**Рекомендации:**
1. Используйте отдельные пароли (не основные)
2. Регулярно меняйте пароли
3. Ограничьте доступ к серверу
4. Делайте бэкапы БД в безопасное место

**TODO (будущие версии):**
- Шифрование паролей в БД
- 2FA для доступа к боту
- Audit log всех действий

### Права доступа

- Только главный админ может управлять другими админами
- Сообщения с паролями автоматически удаляются
- Каждое действие логируется с user_id

---

## Устранение проблем

### Бот не запускается после обновления

```bash
# Проверьте логи
journalctl -u club_assistant -n 100

# Частые причины:
# 1. Не установлен psutil
pip install psutil

# 2. Ошибка миграции БД
cp knowledge.db.backup knowledge.db
systemctl restart club_assistant
```

### "Нет прав для обучения"

```bash
# Проверьте что вы в списке админов
sqlite3 /opt/club_assistant/knowledge.db
SELECT * FROM admins;

# Если нет - добавьте через главного админа
# Или вручную через SQL
```

### /health показывает ошибки

- **База данных FAIL** - проверьте permissions на knowledge.db
- **OpenAI API FAIL** - проверьте ключ в config.json
- **GitHub WARNING** - добавьте github_repo в config

---

## Changelog

### v2.3 (текущая)
- ✅ Версионирование знаний (legacy)
- ✅ Система администраторов с правами
- ✅ Личные данные админов
- ✅ Health check
- ✅ Улучшенное обновление (весь репозиторий)
- ✅ Отслеживание авторства

### v2.2
- ✅ Массовый импорт CSV/JSONL
- ✅ Убраны лишние смайлики
- ✅ Короткие ответы GPT

### v2.1
- ✅ Работа в группах (только на упоминания)
- ✅ Автообновление с GitHub

### v2.0
- ✅ Умное обучение через GPT
- ✅ База знаний SQLite

### v1.0
- ✅ Базовый функционал

---

## Roadmap (будущие версии)

### v2.4
- [ ] Шифрование паролей админов
- [ ] Расширенный audit log
- [ ] Экспорт знаний в CSV/JSONL
- [ ] Поиск по тегам

### v2.5
- [ ] Web-интерфейс для управления
- [ ] API для интеграций
- [ ] Аналитика использования
- [ ] Backup/restore через бота

---

## Поддержка

Если возникли вопросы или нашли баг - обновите код на GitHub и используйте `/update`!

**Готов к production использованию! 🚀**
