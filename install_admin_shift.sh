#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Admin & Shift Management System - Auto Installation Script
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

BOT_DIR="/opt/club_assistant"
BACKUP_DIR="$BOT_DIR/backups/admin_shift_$(date +%Y%m%d_%H%M%S)"

clear
echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     ██████╗  ██████╗ ████████╗     ██████╗██╗      █████╗    ║
║     ██╔══██╗██╔═══██╗╚══██╔══╝    ██╔════╝██║     ██╔══██╗   ║
║     ██████╔╝██║   ██║   ██║       ██║     ██║     ███████║   ║
║     ██╔══██╗██║   ██║   ██║       ██║     ██║     ██╔══██║   ║
║     ██████╔╝╚██████╔╝   ██║       ╚██████╗███████╗██║  ██║   ║
║     ╚═════╝  ╚═════╝    ╚═╝        ╚═════╝╚══════╝╚═╝  ╚═╝   ║
║                                                               ║
║              Admin & Shift Management v4.14                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

sleep 2

# ═══════════════════════════════════════════════════════════════
# Функции
# ═══════════════════════════════════════════════════════════════

print_step() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}   $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_info() {
    echo -e "${CYAN}→${NC} $1"
}

# ═══════════════════════════════════════════════════════════════
# Шаг 1: Проверка прав
# ═══════════════════════════════════════════════════════════════
if [ "$EUID" -ne 0 ]; then 
    print_error "Запусти скрипт с правами root (sudo)"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════
# Шаг 2: Остановка бота
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 1/8: Остановка бота"

if systemctl is-active --quiet club_assistant; then
    print_info "Останавливаю бота..."
    systemctl stop club_assistant
    sleep 2
    print_success "Бот остановлен"
else
    print_warning "Бот уже остановлен"
fi

# ═══════════════════════════════════════════════════════════════
# Шаг 3: Создание резервной копии
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 2/8: Создание резервной копии"

mkdir -p "$BACKUP_DIR"
print_info "Директория бэкапа: $BACKUP_DIR"

cp "$BOT_DIR/bot.py" "$BACKUP_DIR/bot.py.backup"
print_success "bot.py"

if [ -f "$BOT_DIR/knowledge.db" ]; then
    cp "$BOT_DIR/knowledge.db" "$BACKUP_DIR/knowledge.db.backup"
    print_success "knowledge.db"
fi

if [ -f "$BOT_DIR/config.json" ]; then
    cp "$BOT_DIR/config.json" "$BACKUP_DIR/config.json.backup"
    print_success "config.json"
fi

# ═══════════════════════════════════════════════════════════════
# Шаг 4: Скачивание обновлений с GitHub
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 3/8: Скачивание обновлений с GitHub"

cd "$BOT_DIR"
print_info "Выполняю git pull..."
git pull origin main
print_success "Обновления скачаны"

# ═══════════════════════════════════════════════════════════════
# Шаг 5: Установка системных зависимостей
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 4/8: Установка системных зависимостей"

print_info "Обновляю пакеты..."
apt update -qq

print_info "Устанавливаю Tesseract OCR..."
apt install -y tesseract-ocr tesseract-ocr-rus libtesseract-dev

print_success "Системные зависимости установлены"

# ═══════════════════════════════════════════════════════════════
# Шаг 6: Установка Python зависимостей
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 5/8: Установка Python зависимостей"

cd "$BOT_DIR"
source venv/bin/activate

print_info "Устанавливаю OpenCV..."
pip install opencv-python>=4.8.0 > /dev/null 2>&1

print_info "Устанавливаю Tesseract Python wrapper..."
pip install pytesseract>=0.3.10 > /dev/null 2>&1

print_info "Устанавливаю Pillow..."
pip install Pillow>=10.0.0 > /dev/null 2>&1

deactivate
print_success "Python зависимости установлены"

# ═══════════════════════════════════════════════════════════════
# Шаг 7: Создание директорий и настройка прав
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 6/8: Создание директорий и настройка прав"

print_info "Создаю директории..."
mkdir -p "$BOT_DIR/photos"
mkdir -p "$BOT_DIR/backups"

print_info "Настраиваю права доступа..."
chown -R club_assistant:club_assistant "$BOT_DIR/photos"
chown -R club_assistant:club_assistant "$BOT_DIR/backups"
chmod 755 "$BOT_DIR/photos"
chmod 755 "$BOT_DIR/backups"

print_success "Директории созданы и права настроены"

# ═══════════════════════════════════════════════════════════════
# Шаг 8: Применение патча к bot.py
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 7/8: Применение патча к bot.py"

if [ -f "$BOT_DIR/integration_patch.py" ]; then
    print_info "Применяю патч интеграции..."
    cd "$BOT_DIR"
    source venv/bin/activate
    python3 integration_patch.py bot.py
    deactivate
    
    if [ $? -eq 0 ]; then
        print_success "Патч применён успешно"
    else
        print_error "Ошибка применения патча"
        print_warning "Восстанавливаю из бэкапа..."
        cp "$BACKUP_DIR/bot.py.backup" "$BOT_DIR/bot.py"
        exit 1
    fi
else
    print_error "Файл integration_patch.py не найден!"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════
# Шаг 9: Миграция базы данных
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 8/8: Миграция базы данных"

if [ -f "$BOT_DIR/migrate_admin_shift.py" ]; then
    print_info "Выполняю миграцию базы данных..."
    cd "$BOT_DIR"
    source venv/bin/activate
    python3 migrate_admin_shift.py knowledge.db
    deactivate
    
    if [ $? -eq 0 ]; then
        print_success "Миграция выполнена успешно"
    else
        print_error "Ошибка миграции базы данных"
        exit 1
    fi
else
    print_error "Файл migrate_admin_shift.py не найден!"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════
# Шаг 10: Запуск бота
# ═══════════════════════════════════════════════════════════════
print_step "ФИНАЛЬНЫЙ ШАГ: Запуск бота"

systemctl start club_assistant
sleep 3

# ═══════════════════════════════════════════════════════════════
# Проверка статуса
# ═══════════════════════════════════════════════════════════════
if systemctl is-active --quiet club_assistant; then
    echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║             ✓✓✓ Установка завершена успешно! ✓✓✓           ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${CYAN}📊 Последние 15 строк лога:${NC}"
    echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}"
    journalctl -u club_assistant -n 15 --no-pager
    echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}"
    
    echo -e "\n${BLUE}📦 Информация:${NC}"
    echo -e "  Версия: ${GREEN}v4.14${NC}"
    echo -e "  Бэкап:  ${CYAN}$BACKUP_DIR${NC}"
    
    echo -e "\n${BLUE}✅ Проверь в Telegram:${NC}"
    echo -e "  ${GREEN}/systemstatus${NC}  → статус всех систем"
    echo -e "  ${GREEN}/adminmgmt${NC}     → управление админами"
    echo -e "  ${GREEN}/shiftmgmt${NC}     → контроль смен"
    echo -e "  ${GREEN}/manualupdate${NC}  → ручное обновление"
    
    echo -e "\n${BLUE}📝 Новые возможности:${NC}"
    echo -e "  • Полная видимость всех админов"
    echo -e "  • Прикрепление фото к сменам"
    echo -e "  • OCR для извлечения чисел"
    echo -e "  • Ручное обновление через бота"
    echo -e "  • Расширенная статистика"
    
    echo -e "\n${BLUE}📝 Просмотр логов:${NC}"
    echo -e "  ${CYAN}journalctl -u club_assistant -f${NC}"
    
    echo -e "\n${BLUE}🔄 Откат (если нужно):${NC}"
    echo -e "  ${CYAN}cp $BACKUP_DIR/bot.py.backup $BOT_DIR/bot.py${NC}"
    echo -e "  ${CYAN}cp $BACKUP_DIR/knowledge.db.backup $BOT_DIR/knowledge.db${NC}"
    echo -e "  ${CYAN}systemctl restart club_assistant${NC}"
    
    echo ""
    
else
    echo -e "\n${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                                                               ║${NC}"
    echo -e "${RED}║                  ✗✗✗ Ошибка запуска! ✗✗✗                    ║${NC}"
    echo -e "${RED}║                                                               ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${RED}📋 Логи ошибок:${NC}"
    journalctl -u club_assistant -n 30 --no-pager
    
    echo -e "\n${YELLOW}🔄 Восстановление из бэкапа:${NC}"
    echo -e "  ${CYAN}systemctl stop club_assistant${NC}"
    echo -e "  ${CYAN}cp $BACKUP_DIR/bot.py.backup $BOT_DIR/bot.py${NC}"
    echo -e "  ${CYAN}cp $BACKUP_DIR/knowledge.db.backup $BOT_DIR/knowledge.db${NC}"
    echo -e "  ${CYAN}systemctl start club_assistant${NC}"
    echo ""
    exit 1
fi
