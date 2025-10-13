#!/bin/bash
# Установщик Club Assistant Bot v2.1
# ИСПРАВЛЕННАЯ ВЕРСИЯ - работает из директории с файлами

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}"
cat << 'EOF'
╔════════════════════════════════════╗
║   CLUB ASSISTANT BOT INSTALLER    ║
║         v2.1 Final Edition         ║
╚════════════════════════════════════╝
EOF
echo -e "${NC}"

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Запустите от root: sudo bash install.sh${NC}"
    exit 1
fi

# Определяем где мы находимся
CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo -e "${BLUE}📁 Текущая директория: $CURRENT_DIR${NC}"

# Проверяем что bot.py есть
if [ ! -f "$CURRENT_DIR/bot.py" ]; then
    echo -e "${RED}❌ Ошибка: bot.py не найден в текущей директории!${NC}"
    echo "Убедитесь что вы распаковали архив и находитесь в правильной папке."
    exit 1
fi

echo ""
echo -e "${BLUE}Выберите способ установки:${NC}"
echo "1) Обычная установка (systemd) - рекомендуется"
echo "2) Docker установка"
read -p "Выбор (1 или 2): " INSTALL_TYPE

# Обновление системы
echo ""
echo -e "${YELLOW}[1/5]${NC} Обновление системы..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq > /dev/null 2>&1

if [ "$INSTALL_TYPE" == "2" ]; then
    # Docker установка
    echo -e "${YELLOW}[2/5]${NC} Установка Docker..."
    
    if ! command -v docker &> /dev/null; then
        echo "  Устанавливаю Docker..."
        curl -fsSL https://get.docker.com | sh > /dev/null 2>&1
        systemctl enable docker > /dev/null 2>&1
        systemctl start docker
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo "  Устанавливаю Docker Compose..."
        apt-get install -y docker-compose > /dev/null 2>&1
    fi
    
    echo "✅ Docker установлен"
else
    # Обычная установка
    echo -e "${YELLOW}[2/5]${NC} Установка пакетов..."
    apt-get install -y python3 python3-pip python3-venv git > /dev/null 2>&1
    echo "✅ Пакеты установлены"
fi

# Проверка что все файлы на месте
echo -e "${YELLOW}[3/5]${NC} Проверка файлов..."

REQUIRED_FILES=("bot.py" "requirements.txt" ".gitignore")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$CURRENT_DIR/$file" ]; then
        echo -e "${RED}❌ Ошибка: файл $file не найден!${NC}"
        exit 1
    fi
done

if [ "$INSTALL_TYPE" == "2" ]; then
    if [ ! -f "$CURRENT_DIR/Dockerfile" ] || [ ! -f "$CURRENT_DIR/docker-compose.yml" ]; then
        echo -e "${RED}❌ Ошибка: Docker файлы не найдены!${NC}"
        exit 1
    fi
fi

echo "✅ Все файлы на месте"

# Конфигурация
echo ""
echo -e "${YELLOW}[4/5]${NC} Настройка конфигурации"
echo -e "${BLUE}════════════════════════════════════${NC}"
echo ""
echo "Получите токены здесь:"
echo "  🔹 Telegram Bot Token: https://t.me/botfather → /newbot"
echo "  🔹 OpenAI API Key: https://platform.openai.com/api-keys"
echo "  🔹 Ваш Telegram ID: https://t.me/userinfobot → /start"
echo ""

read -p "Telegram Bot Token: " TG_TOKEN
read -p "OpenAI API Key: " OPENAI_KEY
read -p "Ваш Telegram ID (только цифры): " ADMIN_ID

echo ""
read -p "GitHub репозиторий (Enter = пропустить): " GITHUB_REPO

# Создаём config.json
cat > "$CURRENT_DIR/config.json" << EOF
{
  "telegram_token": "$TG_TOKEN",
  "openai_api_key": "$OPENAI_KEY",
  "admin_ids": [$ADMIN_ID],
  "github_repo": "$GITHUB_REPO"
}
EOF

chmod 600 "$CURRENT_DIR/config.json"
echo "✅ Конфигурация сохранена"

# Установка и запуск
echo ""
echo -e "${YELLOW}[5/5]${NC} Установка и запуск..."

if [ "$INSTALL_TYPE" == "2" ]; then
    # Docker запуск
    cd "$CURRENT_DIR"
    echo "  Собираю Docker образ..."
    docker-compose up -d --build
    
    echo ""
    echo -e "${GREEN}✅ УСТАНОВКА ЗАВЕРШЕНА (Docker)${NC}"
    echo ""
    echo -e "${BLUE}📋 Команды управления:${NC}"
    echo "  Статус:     cd $CURRENT_DIR && docker-compose ps"
    echo "  Логи:       cd $CURRENT_DIR && docker-compose logs -f"
    echo "  Перезапуск: cd $CURRENT_DIR && docker-compose restart"
    echo "  Остановка:  cd $CURRENT_DIR && docker-compose down"
    
    echo ""
    echo "Показываю статус..."
    sleep 2
    docker-compose ps
    
else
    # Systemd установка
    cd "$CURRENT_DIR"
    
    echo "  Создаю виртуальное окружение..."
    python3 -m venv venv
    
    echo "  Устанавливаю зависимости..."
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    deactivate
    
    # Systemd service
    echo "  Создаю systemd service..."
    cat > /etc/systemd/system/club_assistant.service << EOF
[Unit]
Description=Club Assistant Bot v2.1
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=club_assistant

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable club_assistant > /dev/null 2>&1
    systemctl start club_assistant
    
    echo ""
    echo -e "${GREEN}✅ УСТАНОВКА ЗАВЕРШЕНА (Systemd)${NC}"
    echo ""
    echo -e "${BLUE}📋 Команды управления:${NC}"
    echo "  Статус:     systemctl status club_assistant"
    echo "  Логи:       journalctl -u club_assistant -f"
    echo "  Перезапуск: systemctl restart club_assistant"
    echo "  Остановка:  systemctl stop club_assistant"
    
    echo ""
    echo "Показываю статус..."
    sleep 2
    systemctl status club_assistant --no-pager -l
fi

echo ""
echo -e "${BLUE}📁 Файлы:${NC}"
echo "  Директория: $CURRENT_DIR"
echo "  Конфиг:     $CURRENT_DIR/config.json"
echo "  База:       $CURRENT_DIR/knowledge.db (создастся автоматически)"
echo ""

if [ -n "$GITHUB_REPO" ]; then
    echo -e "${BLUE}🔄 Настройка автообновлений:${NC}"
    echo ""
    echo "1. Инициализируйте Git:"
    echo "   cd $CURRENT_DIR"
    echo "   git init"
    echo "   git add bot.py requirements.txt .gitignore"
    echo "   git commit -m 'Initial commit'"
    echo ""
    echo "2. Подключите GitHub:"
    echo "   git remote add origin $GITHUB_REPO"
    echo "   git push -u origin main"
    echo ""
    echo "3. Используйте /update в Telegram для обновления бота"
    echo ""
fi

echo -e "${GREEN}🎉 Готово! Проверьте бота в Telegram!${NC}"
echo ""
echo -e "${YELLOW}Отправьте боту команду /start${NC}"
echo ""
