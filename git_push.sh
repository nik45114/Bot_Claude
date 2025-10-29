#!/bin/bash

# Скрипт для автоматического коммита и push изменений в GitHub
# Использование: ./git_push.sh "Описание изменений"

# Проверка аргументов
if [ -z "$1" ]; then
    echo "❌ Ошибка: укажите описание изменений"
    echo "Использование: ./git_push.sh \"Описание изменений\""
    exit 1
fi

COMMIT_MESSAGE="$1"

echo "🔍 Проверка изменений..."
git status

echo ""
echo "➕ Добавление файлов..."
git add .

echo ""
echo "📝 Создание коммита..."
git commit -m "$COMMIT_MESSAGE

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при создании коммита"
    exit 1
fi

echo ""
echo "🚀 Push в GitHub..."
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Изменения успешно загружены в GitHub!"
    echo "📊 Статус:"
    git log -1 --oneline
else
    echo "❌ Ошибка при push в GitHub"
    exit 1
fi
