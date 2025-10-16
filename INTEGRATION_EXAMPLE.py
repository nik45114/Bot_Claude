"""
Пример интеграции v4.13 в bot.py
Добавь эти изменения в свой bot.py
"""

# ═══════════════════════════════════════════════════════════════
# ИМПОРТЫ
# ═══════════════════════════════════════════════════════════════

from club_manager import ClubManager  # Обновленная версия v4.13
from v2ray_manager import V2RayManager  # НОВЫЙ МОДУЛЬ!
from v2ray_commands import V2RayCommands  # Требует v2ray_manager

# ═══════════════════════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ (в main())
# ═══════════════════════════════════════════════════════════════

def main():
    # Существующие менеджеры
    club_manager = ClubManager(db_path='knowledge.db')
    admin_manager = AdminManager(db_path='knowledge.db')
    
    # НОВЫЙ: V2Ray Manager
    v2ray_manager = V2RayManager(db_path='knowledge.db')
    
    # Команды V2Ray
    v2ray_commands = V2RayCommands(
        manager=v2ray_manager,
        admin_manager=admin_manager,
        owner_id=OWNER_ID
    )
    
    # ... остальной код

# ═══════════════════════════════════════════════════════════════
# РЕГИСТРАЦИЯ КОМАНД V2RAY
# ═══════════════════════════════════════════════════════════════

    # В секции регистрации команд добавь:
    app.add_handler(CommandHandler("v2ray", v2ray_commands.cmd_v2ray))
    app.add_handler(CommandHandler("v2add", v2ray_commands.cmd_v2add))
    app.add_handler(CommandHandler("v2list", v2ray_commands.cmd_v2list))
    app.add_handler(CommandHandler("v2setup", v2ray_commands.cmd_v2setup))
    app.add_handler(CommandHandler("v2user", v2ray_commands.cmd_v2user))
    app.add_handler(CommandHandler("v2stats", v2ray_commands.cmd_v2stats))
    app.add_handler(CommandHandler("v2sni", v2ray_commands.cmd_v2sni))
    app.add_handler(CommandHandler("v2remove", v2ray_commands.cmd_v2remove))

# ═══════════════════════════════════════════════════════════════
# НОВЫЕ КОМАНДЫ ДЛЯ АНАЛИТИКИ РАСХОДОВ (опционально)
# ═══════════════════════════════════════════════════════════════

async def cmd_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика расходов: /expenses [club_id] [days]"""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещён")
        return
    
    try:
        club_id = int(context.args[0]) if len(context.args) > 0 else None
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        stats = club_manager.get_expenses_stats(club_id, days)
        
        if not stats or stats['count'] == 0:
            await update.message.reply_text(f"📭 Нет расходов за последние {days} дней")
            return
        
        text = f"📊 Статистика расходов за {days} дней:\n\n"
        
        # Эмодзи для категорий
        category_emoji = {
            'salary': '👤',
            'purchase': '🛒',
            'collection': '🏦',
            'repair': '🔧',
            'utility': '🔌',
            'other': '💰'
        }
        
        category_names = {
            'salary': 'Зарплата',
            'purchase': 'Закупки',
            'collection': 'Инкассация',
            'repair': 'Ремонт',
            'utility': 'Коммунальные',
            'other': 'Прочее'
        }
        
        for category, data in stats['by_category'].items():
            emoji = category_emoji.get(category, '💰')
            name = category_names.get(category, category.title())
            
            text += f"{emoji} {name}:\n"
            text += f"   Сумма: {data['total']:,} ₽\n"
            text += f"   Операций: {data['count']}\n"
            text += f"   Средняя: {data['average']:,.0f} ₽\n\n"
        
        text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💰 Всего: {stats['total']:,} ₽\n"
        text += f"📝 Операций: {stats['count']}"
        
        await update.message.reply_text(text)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_expenses_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История расходов: /expenses_history [club_id] [days] [category]"""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещён")
        return
    
    try:
        club_id = int(context.args[0]) if len(context.args) > 0 else None
        days = int(context.args[1]) if len(context.args) > 1 else 30
        category = context.args[2] if len(context.args) > 2 else None
        
        history = club_manager.get_expenses_history(club_id, days, category)
        
        if not history:
            await update.message.reply_text(f"📭 Нет расходов за последние {days} дней")
            return
        
        text = f"📋 История расходов (последние {len(history)}):\n\n"
        
        category_emoji = {
            'salary': '👤',
            'purchase': '🛒',
            'collection': '🏦',
            'repair': '🔧',
            'utility': '🔌',
            'other': '💰'
        }
        
        for item in history[:20]:  # Показываем первые 20
            emoji = category_emoji.get(item['category'], '💰')
            recipient_text = f" ({item['recipient']})" if item.get('recipient') else ""
            
            text += f"{emoji} {item['description']}{recipient_text}: {item['amount']:,} ₽\n"
            text += f"   📅 {item['shift_date']} | 🏢 {item['club_name']} | 👤 {item['admin_name']}\n\n"
        
        if len(history) > 20:
            text += f"... и ещё {len(history) - 20} расходов"
        
        await update.message.reply_text(text)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить расход: /add_expense <shift_id> <amount> <description>"""
    if not is_owner(update.effective_user.id) and not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещён")
        return
    
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "Использование: /add_expense <shift_id> <amount> <description>\n\n"
                "Пример: /add_expense 42 4500 зп вика"
            )
            return
        
        shift_id = int(context.args[0])
        amount = int(context.args[1])
        description = ' '.join(context.args[2:])
        
        if club_manager.add_expense(shift_id, description, amount):
            await update.message.reply_text(
                f"✅ Расход добавлен к смене #{shift_id}\n\n"
                f"💰 Сумма: {amount:,} ₽\n"
                f"📝 Описание: {description}"
            )
        else:
            await update.message.reply_text("❌ Ошибка добавления расхода")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


# Регистрация новых команд
app.add_handler(CommandHandler("expenses", cmd_expenses))
app.add_handler(CommandHandler("expenses_history", cmd_expenses_history))
app.add_handler(CommandHandler("add_expense", cmd_add_expense))

# ═══════════════════════════════════════════════════════════════
# ОБНОВЛЕНИЕ КОМАНДЫ /help (опционально)
# ═══════════════════════════════════════════════════════════════

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    user_id = update.effective_user.id
    
    if is_owner(user_id):
        text = """📚 Команды владельца:

🏢 Клубы:
/clubs - список клубов
/addclub - добавить клуб

📊 Отчёты:
/report <клуб> - создать отчёт
/stats [клуб] [дни] - статистика

💸 Расходы (НОВОЕ!):
/expenses [клуб] [дни] - статистика расходов
/expenses_history [клуб] [дни] [категория] - история
/add_expense <смена> <сумма> <описание> - добавить расход

🔐 V2Ray (НОВОЕ!):
/v2ray - главное меню V2Ray
/v2add <имя> <host> <user> <pass> [sni] - добавить сервер
/v2setup <имя> - установить Xray
/v2user <сервер> <user_id> [email] - добавить пользователя
/v2sni <сервер> <сайт> - изменить SNI
/v2stats <имя> - статистика сервера
/v2list - список серверов
/v2remove <сервер> <uuid> - удалить пользователя

👥 Администраторы:
/addadmin - добавить админа
/listadmins - список админов

📚 База знаний:
/knowledge - меню базы знаний
/search <запрос> - поиск
"""
    elif is_admin(user_id):
        text = """📚 Команды администратора:

📊 Отчёты:
/report <клуб> - создать отчёт смены

📚 База знаний:
/knowledge - меню базы знаний
/search <запрос> - поиск
"""
    else:
        text = """📚 Команды пользователя:

📚 База знаний:
/knowledge - меню базы знаний
/search <запрос> - поиск

ℹ️ Для доступа к другим функциям обратитесь к администратору.
"""
    
    await update.message.reply_text(text)

# ═══════════════════════════════════════════════════════════════
# ПРИМЕЧАНИЯ
# ═══════════════════════════════════════════════════════════════

"""
ВАЖНО:
1. Замени club_manager.py на club_manager_v2.py
2. Добавь v2ray_manager.py в директорию бота
3. Установи paramiko: pip install paramiko
4. База данных обновится автоматически при первом запуске

РАСХОДЫ В ОТЧЁТАХ:
Теперь админы могут писать расходы в любом формате:
- "- 4500 вика зп"
- "зп вика 4500"
- "закупка 1500 monster"
- "инкассация 10000"

Все расходы автоматически парсятся и группируются по категориям.

V2RAY КОМАНДЫ:
Для работы команд V2Ray нужен SSH доступ к серверу.
Убедись, что:
- Можешь подключиться по SSH (ssh root@IP)
- Порт 443 свободен на сервере
- У тебя есть root права

ТЕСТИРОВАНИЕ:
1. Создай тестовый отчёт с расходами
2. Проверь /expenses и /expenses_history
3. Попробуй добавить V2Ray сервер
4. Установи Xray командой /v2setup
5. Добавь тестового пользователя
"""
