#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Bot Claude - Полное автоматическое обновление до v4.13
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

BOT_DIR="/opt/club_assistant"
BACKUP_DIR="$BOT_DIR/backups/v4.13_$(date +%Y%m%d_%H%M%S)"

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
║              Автоматическое обновление до v4.13              ║
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
print_step "ШАГ 1/9: Остановка бота"

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
print_step "ШАГ 2/9: Создание резервной копии"

mkdir -p "$BACKUP_DIR"
print_info "Директория бэкапа: $BACKUP_DIR"

cp "$BOT_DIR/bot.py" "$BACKUP_DIR/bot.py.backup"
print_success "bot.py"

if [ -f "$BOT_DIR/club_manager.py" ]; then
    cp "$BOT_DIR/club_manager.py" "$BACKUP_DIR/club_manager.py.backup"
    print_success "club_manager.py"
fi

if [ -f "$BOT_DIR/knowledge.db" ]; then
    cp "$BOT_DIR/knowledge.db" "$BACKUP_DIR/knowledge.db.backup"
    print_success "knowledge.db"
fi

# ═══════════════════════════════════════════════════════════════
# Шаг 4: Скачивание обновлений с GitHub
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 3/9: Скачивание обновлений с GitHub"

cd "$BOT_DIR"
print_info "Выполняю git pull..."
git pull origin main
print_success "Обновления скачаны"

# ═══════════════════════════════════════════════════════════════
# Шаг 5: Замена club_manager.py
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 4/9: Обновление club_manager.py"

if [ -f "$BOT_DIR/club_manager_v2.py" ]; then
    cp "$BOT_DIR/club_manager_v2.py" "$BOT_DIR/club_manager.py"
    print_success "club_manager.py обновлён до v2"
else
    print_warning "club_manager_v2.py не найден"
fi

# ═══════════════════════════════════════════════════════════════
# Шаг 6: Проверка v2ray_manager.py
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 5/9: Проверка v2ray_manager.py"

if [ -f "$BOT_DIR/v2ray_manager.py" ]; then
    print_success "v2ray_manager.py найден"
else
    print_error "v2ray_manager.py отсутствует!"
fi

# ═══════════════════════════════════════════════════════════════
# Шаг 7: Применение патча к bot.py с помощью Python
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 6/9: Применение патча к bot.py"

# Создаём временный Python скрипт для обновления
cat > /tmp/update_bot_py.py << 'PYTHON_SCRIPT'
import re
import sys
from pathlib import Path

BOT_FILE = "/opt/club_assistant/bot.py"

NEW_CMD_HELP = '''    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Помощь по командам"""
        user_id = update.effective_user.id
        
        if self.is_owner(user_id):
            text = """📚 Команды владельца (v4.13):

🏢 КЛУБЫ:
/clubs - список клубов
/addclub <название> - добавить клуб
/stats [клуб] [дней] - статистика клуба

📊 ОТЧЁТЫ:
/report <клуб> - создать отчёт смены
/shift <shift_id> - просмотр отчёта

💸 РАСХОДЫ (v4.13):
/expenses [клуб] [дней] - статистика расходов
/expenses_history [клуб] [дней] - история расходов
/add_expense <shift_id> <сумма> <описание> - добавить расход

🔐 V2RAY (v4.13):
/v2ray - главное меню V2Ray
/v2add <имя> <host> <user> <pass> [sni] - добавить сервер
/v2setup <имя> - установить Xray (2-3 мин)
/v2user <сервер> <user_id> [email] - добавить пользователя
/v2sni <сервер> <сайт> - изменить маскировку
/v2stats <имя> - статистика сервера
/v2list - список серверов
/v2remove <сервер> <uuid> - удалить пользователя

👥 АДМИНИСТРАТОРЫ:
/addadmin <user_id> <club_id> - добавить админа
/removeadmin <user_id> - удалить админа
/listadmins - список админов

📚 БАЗА ЗНАНИЙ:
/knowledge - меню базы знаний
/search <запрос> - поиск в базе
/add_document - добавить документ
/stats_kb - статистика базы

ℹ️ СИСТЕМА:
/help - эта справка
/version - версия бота"""
            
        elif self.is_admin(user_id):
            text = """📚 Команды администратора (v4.13):

📊 ОТЧЁТЫ:
/report <клуб> - создать отчёт смены

📝 Форматы расходов в отчёте:
- "- 4500 вика зп"
- "зп вика 4500"
- "закупка 1500 monster"
- "инкассация 10000"

📚 БАЗА ЗНАНИЙ:
/knowledge - меню базы знаний
/search <запрос> - поиск

ℹ️ ПОМОЩЬ:
/help - эта справка"""
            
        else:
            text = """📚 Команды пользователя (v4.13):

📚 БАЗА ЗНАНИЙ:
/knowledge - меню базы знаний
/search <запрос> - поиск информации

ℹ️ Для доступа к функциям управления обратитесь к администратору.
/help - эта справка"""
        
        await update.message.reply_text(text)
'''

NEW_CMD_VERSION = '''
    async def cmd_version(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать версию бота"""
        text = f"""🤖 Club Assistant Bot
        
📦 Версия: v{VERSION}
📅 Дата: 2025-10-16

✨ Что нового в v4.13:
• Улучшенный парсинг расходов (5+ форматов)
• Автоопределение получателя и категории
• 6 категорий расходов с группировкой
• Полный V2Ray Manager с REALITY
• SSH управление серверами
• Генерация ключей и VLESS ссылок

📊 Статистика:
• База знаний: {len(self.vector_store.vectors)} векторов
• Записей: {len(self.knowledge_base.entries)} шт

🔗 GitHub: https://github.com/nik45114/Bot_Claude"""
        
        await update.message.reply_text(text)
'''

# Читаем файл
with open(BOT_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Обновление VERSION
content = re.sub(r'VERSION = "[^"]*"', 'VERSION = "4.13"', content)

# 2. Закомментировать v2traffic
content = re.sub(
    r'^(\s*)(app\.add_handler\(CommandHandler\("v2traffic")',
    r'\1# \2  # TODO: v4.14',
    content,
    flags=re.MULTILINE
)

# 3. Обновление сообщений
content = re.sub(r'Club Assistant Bot v[\d.]+', 'Club Assistant Bot v4.13', content)
content = re.sub(r'Database Fix Edition', 'Enhanced Reports + V2Ray REALITY Edition', content)
content = re.sub(r'Инициализация v[\d.]+', 'Инициализация v4.13', content)
content = re.sub(r'Бот v[\d.]+ готов', 'Бот v4.13 готов', content)

# 4. Замена cmd_help
pattern = r'(    async def cmd_help\(self.*?\n)(.*?)(\n    async def |\n    def |\nclass )'
match = re.search(pattern, content, re.DOTALL)
if match:
    content = content[:match.start()] + NEW_CMD_HELP + '\n' + content[match.start(3):]

# 5. Добавление cmd_version
if 'async def cmd_version' not in content:
    pattern = r'(    async def cmd_help\(.*?\n        await update\.message\.reply_text\(text\)\n)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        content = content[:match.end()] + NEW_CMD_VERSION + content[match.end():]

# 6. Регистрация /version
if 'CommandHandler("version"' not in content:
    pattern = r'(app\.add_handler\(CommandHandler\("help", self\.cmd_help\)\))'
    match = re.search(pattern, content)
    if match:
        line_start = content.rfind('\n', 0, match.start()) + 1
        indent = ' ' * (match.start() - line_start)
        new_line = f'\n{indent}app.add_handler(CommandHandler("version", self.cmd_version))'
        content = content[:match.end()] + new_line + content[match.end():]

# Сохраняем
with open(BOT_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK")
PYTHON_SCRIPT

print_info "Применяю патч с помощью Python..."
source "$BOT_DIR/venv/bin/activate"
python3 /tmp/update_bot_py.py
deactivate

if [ $? -eq 0 ]; then
    print_success "Патч применён успешно"
else
    print_error "Ошибка применения патча"
    print_warning "Восстанавливаю из бэкапа..."
    cp "$BACKUP_DIR/bot.py.backup" "$BOT_DIR/bot.py"
    exit 1
fi

rm -f /tmp/update_bot_py.py

# ═══════════════════════════════════════════════════════════════
# Шаг 8: Проверка зависимостей
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 7/9: Проверка зависимостей"

cd "$BOT_DIR"
source venv/bin/activate

if python -c "import paramiko" 2>/dev/null; then
    print_success "paramiko установлен"
else
    print_info "Установка paramiko..."
    pip install paramiko > /dev/null 2>&1
    print_success "paramiko установлен"
fi

deactivate

# ═══════════════════════════════════════════════════════════════
# Шаг 9: Запуск бота
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 8/9: Запуск бота"

systemctl start club_assistant
sleep 3

# ═══════════════════════════════════════════════════════════════
# Шаг 10: Проверка статуса
# ═══════════════════════════════════════════════════════════════
print_step "ШАГ 9/9: Проверка статуса"

if systemctl is-active --quiet club_assistant; then
    echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║             ✓✓✓ Обновление завершено успешно! ✓✓✓           ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${CYAN}📊 Последние 15 строк лога:${NC}"
    echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}"
    journalctl -u club_assistant -n 15 --no-pager
    echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}"
    
    echo -e "\n${BLUE}📦 Информация:${NC}"
    echo -e "  Версия: ${GREEN}v4.13${NC}"
    echo -e "  Бэкап:  ${CYAN}$BACKUP_DIR${NC}"
    
    echo -e "\n${BLUE}✅ Проверь в Telegram:${NC}"
    echo -e "  ${GREEN}/version${NC}  → должна показать v4.13"
    echo -e "  ${GREEN}/help${NC}     → должна показать новые команды"
    echo -e "  ${GREEN}/v2ray${NC}    → меню V2Ray"
    
    echo -e "\n${BLUE}📝 Просмотр логов:${NC}"
    echo -e "  ${CYAN}journalctl -u club_assistant -f${NC}"
    
    echo -e "\n${BLUE}🔄 Откат (если нужно):${NC}"
    echo -e "  ${CYAN}cp $BACKUP_DIR/bot.py.backup $BOT_DIR/bot.py${NC}"
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
    echo -e "  ${CYAN}cp $BACKUP_DIR/club_manager.py.backup $BOT_DIR/club_manager.py${NC}"
    echo -e "  ${CYAN}systemctl start club_assistant${NC}"
    echo ""
    exit 1
fi
