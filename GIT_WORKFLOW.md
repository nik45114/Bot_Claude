# 🔄 Git Workflow - Инструкция по работе с GitHub

## Быстрый старт

### Автоматический push (рекомендуется)

```bash
# После любых изменений в проекте выполните:
./git_push.sh "Описание изменений"

# Примеры:
./git_push.sh "Fix: Исправлены кнопки управления правами администраторов"
./git_push.sh "Feature: Добавлена новая команда /stats"
./git_push.sh "Docs: Обновлена документация проекта"
```

### Ручной push (если нужен контроль)

```bash
# 1. Проверить изменения
git status

# 2. Добавить файлы
git add .

# 3. Создать коммит
git commit -m "Описание изменений

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# 4. Загрузить в GitHub
git push origin main
```

---

## Рекомендации по коммитам

### Формат сообщений

Используйте префиксы для типа изменений:

- **Fix:** - исправление багов
- **Feature:** - новая функциональность
- **Refactor:** - рефакторинг кода
- **Docs:** - изменения в документации
- **Style:** - форматирование кода
- **Test:** - добавление тестов
- **Chore:** - обновление зависимостей, конфигурации

### Примеры хороших коммитов

```bash
./git_push.sh "Fix: Убрана двойная обработка кнопок в ConversationHandler"
./git_push.sh "Feature: Добавлен модуль расчета зарплат"
./git_push.sh "Refactor: Разделен bot.py на модули"
./git_push.sh "Docs: Создан СПРАВОЧНИК_ПРОЕКТА.md"
./git_push.sh "Fix: Исправлена ошибка DB_PATH в admins модуле"
```

---

## Частые команды

### Проверка статуса

```bash
# Посмотреть измененные файлы
git status

# Посмотреть diff изменений
git diff

# Посмотреть историю коммитов
git log --oneline -10
```

### Работа с ветками

```bash
# Создать новую ветку
git checkout -b feature/new-feature

# Переключиться на ветку
git checkout main

# Список веток
git branch -a

# Удалить локальную ветку
git branch -d feature/old-feature
```

### Отмена изменений

```bash
# Отменить изменения в файле (до add)
git checkout -- filename.py

# Отменить git add (вернуть из staging)
git reset HEAD filename.py

# Отменить последний коммит (но оставить изменения)
git reset --soft HEAD~1

# Отменить последний коммит (удалить изменения) ⚠️
git reset --hard HEAD~1
```

### Синхронизация с удаленным репозиторием

```bash
# Загрузить изменения с GitHub
git pull origin main

# Посмотреть удаленные ветки
git remote -v

# Обновить список удаленных веток
git fetch origin
```

---

## Автоматизация

### Git hook для автоматического push после коммита (опционально)

Создайте файл `.git/hooks/post-commit`:

```bash
#!/bin/bash
# Автоматический push после каждого коммита

echo "🚀 Автоматический push в GitHub..."
git push origin main

if [ $? -eq 0 ]; then
    echo "✅ Push выполнен успешно!"
else
    echo "❌ Ошибка при push"
fi
```

Сделайте его исполняемым:
```bash
chmod +x .git/hooks/post-commit
```

**Внимание:** Это будет делать push после КАЖДОГО коммита автоматически!

---

## Интеграция с Claude Code

### После каждого изменения, сделанного Claude:

1. Claude вносит изменения в файлы
2. Вы проверяете изменения: `git status` и `git diff`
3. Если всё хорошо, запускаете: `./git_push.sh "Описание изменений"`
4. Изменения автоматически коммитятся и загружаются в GitHub

### Пример workflow:

```bash
# Claude исправил баг с кнопками
git status
# Видите: modified: modules/admins/wizard.py

git diff modules/admins/wizard.py
# Проверяете изменения

./git_push.sh "Fix: Исправлены кнопки управления правами администраторов"
# ✅ Изменения в GitHub!
```

---

## Полезные алиасы (опционально)

Добавьте в `~/.bashrc` или `~/.zshrc`:

```bash
# Git алиасы
alias gs='git status'
alias gd='git diff'
alias gl='git log --oneline -10'
alias gp='git push origin main'
alias gpl='git pull origin main'

# Быстрый push
alias gpush='./git_push.sh'
```

После добавления выполните: `source ~/.bashrc`

Теперь можно использовать:
```bash
gpush "Fix: Исправлен баг"
```

---

## Решение проблем

### "Updates were rejected because the remote contains work"

```bash
# Загрузить изменения с GitHub и объединить
git pull origin main --rebase

# Затем снова push
git push origin main
```

### "fatal: not a git repository"

```bash
# Инициализировать git репозиторий
cd /opt/club_assistant
git init
git remote add origin https://github.com/nik45114/Bot_Claude.git
```

### Забыли добавить файл в коммит

```bash
# Добавить файл
git add forgotten_file.py

# Изменить последний коммит
git commit --amend --no-edit

# Force push (только если коммит еще не в GitHub!)
git push origin main --force
```

### Конфликты при merge

```bash
# Посмотреть файлы с конфликтами
git status

# Открыть файл и исправить конфликты (между <<<< и >>>>)
nano conflicted_file.py

# После исправления
git add conflicted_file.py
git commit -m "Fix: Разрешены конфликты merge"
git push origin main
```

---

## Чеклист перед push

- [ ] Проверил изменения: `git diff`
- [ ] Проверил статус: `git status`
- [ ] Убедился, что нет секретов в коде (.env, пароли)
- [ ] Написал понятное сообщение коммита
- [ ] Запустил `./git_push.sh "Описание"`
- [ ] Проверил успешный push в GitHub

---

## Безопасность

### ⚠️ НИКОГДА не добавляйте в Git:

- `.env` - файл с секретами (уже в .gitignore)
- `google_credentials.json` - Google API ключи
- `config.json` - может содержать API keys
- `*.db` - базы данных с личными данными
- `__pycache__/` - кэш Python
- `venv/` - виртуальное окружение
- `.embedding_cache/` - кэш эмбеддингов
- Пароли, токены, API keys

### Проверка .gitignore

Убедитесь, что файл `.gitignore` содержит:

```
.env
*.db
google_credentials.json
config.json
__pycache__/
venv/
.embedding_cache/
*.pyc
*.log
vector_index.faiss
vector_metadata.pkl
```

---

## Мониторинг репозитория

### GitHub Actions (опционально)

Можно настроить автоматическое тестирование при каждом push:

Создайте файл `.github/workflows/test.yml`:

```yaml
name: Test Bot

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Check syntax
        run: |
          python -m py_compile bot.py
```

---

## Контакты

- **Репозиторий:** https://github.com/nik45114/Bot_Claude
- **Ветка по умолчанию:** main
- **Автор:** nik45114
- **Email:** nik45114@gmail.com

---

**Дата создания:** 29 октября 2025
**Версия:** 1.0
