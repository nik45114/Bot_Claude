#!/bin/bash
# Скрипт автообновления Club Assistant Bot

echo "🔄 Обновление бота из GitHub..."

cd /opt/club_assistant

# Останавливаем бота
echo "⏸ Останавливаю бота..."
systemctl stop club_assistant

# Бэкап
echo "💾 Создаю бэкап..."
tar -czf "backup_$(date +%Y%m%d_%H%M%S).tar.gz" knowledge.db bot.py config.json 2>/dev/null

# Скачиваем с GitHub
echo "📥 Скачиваю обновления..."
git pull origin main

# Проверяем что скачалось
if [ ! -f "bot_v4.4.py" ]; then
    echo "❌ bot_v4.4.py не найден!"
    systemctl start club_assistant
    exit 1
fi

# Заменяем
echo "🔄 Заменяю bot.py..."
cp bot_v4.4.py bot.py

# Делаем исполняемым
chmod +x bot.py

# Проверяем модули
echo "🔍 Проверяю модули..."
python3 -c "from embeddings import EmbeddingService" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Модули v4.0 не найдены!"
    systemctl start club_assistant
    exit 1
fi

# Запускаем
echo "▶️ Запускаю бота..."
systemctl start club_assistant

# Проверяем статус
sleep 2
if systemctl is-active --quiet club_assistant; then
    echo "✅ Бот успешно обновлён и запущен!"
else
    echo "❌ Ошибка запуска! Смотри: journalctl -u club_assistant -n 20"
fi
