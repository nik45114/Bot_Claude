"""
Модуль инвентаря при приеме смены (Чек-лист #3)
Проверка количества оборудования на столах и в запасе
Срок заполнения: 4 часа после открытия смены
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))

# States для ConversationHandler
(INV_MICE_TABLES, INV_MICE_STOCK, INV_MICE_DONGLES,
 INV_KB_TABLES, INV_KB_STOCK,
 INV_HS_TABLES, INV_HS_STOCK, INV_HS_MICS, INV_HS_CABLES,
 INV_CHARGERS) = range(10)


class InventoryChecklistManager:
    """Менеджер инвентаря при приеме смены"""

    def __init__(self, db_path: str = 'club_assistant.db'):
        self.db_path = db_path

    def save_inventory(self, shift_id: int, club: str, admin_id: int,
                      mice_tables: int, mice_stock: int, mice_dongles: int,
                      kb_tables: int, kb_stock: int,
                      hs_tables: int, hs_stock: int, hs_mics: int, hs_cables: int,
                      chargers: int = 0) -> bool:
        """Сохранить данные инвентаря"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO shift_inventory_checklist
                (shift_id, club, admin_id, mice_on_tables, mice_in_stock, mice_dongles_in_stock,
                 keyboards_on_tables, keyboards_in_stock,
                 headsets_on_tables, headsets_in_stock, headset_mics_in_stock, headset_cables_in_stock,
                 chargers_in_stock)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (shift_id, club, admin_id, mice_tables, mice_stock, mice_dongles,
                  kb_tables, kb_stock, hs_tables, hs_stock, hs_mics, hs_cables, chargers))

            conn.commit()
            conn.close()
            logger.info(f"Saved inventory for shift {shift_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving inventory: {e}")
            return False

    def get_inventory(self, shift_id: int) -> Optional[Dict]:
        """Получить данные инвентаря для смены"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM shift_inventory_checklist WHERE shift_id = ?", (shift_id,))
            row = cursor.fetchone()
            conn.close()

            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting inventory: {e}")
            return None

    def get_previous_day_inventory(self, club: str) -> Optional[Dict]:
        """Получить инвентарь предыдущего дня для сравнения"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            yesterday = (datetime.now(MSK) - timedelta(days=1)).date()

            cursor.execute("""
                SELECT sic.* FROM shift_inventory_checklist sic
                JOIN active_shifts ash ON sic.shift_id = ash.id
                WHERE sic.club = ?
                AND DATE(ash.opened_at) = ?
                ORDER BY sic.completed_at DESC
                LIMIT 1
            """, (club, yesterday))

            row = cursor.fetchone()
            conn.close()

            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting previous inventory: {e}")
            return None

    def compare_with_previous(self, current: Dict, previous: Dict) -> List[str]:
        """Сравнить текущий инвентарь с предыдущим, вернуть список изменений"""
        changes = []

        fields = [
            ('mice_on_tables', 'Мыши на столах'),
            ('mice_in_stock', 'Мыши в запасе'),
            ('mice_dongles_in_stock', 'Донглы в запасе'),
            ('keyboards_on_tables', 'Клавиатуры на столах'),
            ('keyboards_in_stock', 'Клавиатуры в запасе'),
            ('headsets_on_tables', 'Наушники на столах'),
            ('headsets_in_stock', 'Наушники в запасе'),
            ('headset_mics_in_stock', 'Микрофоны в запасе'),
            ('headset_cables_in_stock', 'Провода наушников в запасе'),
            ('chargers_in_stock', 'Зарядки в запасе')
        ]

        for field, name in fields:
            curr_val = current.get(field, 0)
            prev_val = previous.get(field, 0)

            if curr_val != prev_val:
                changes.append(f"{name}: было {prev_val}, стало {curr_val}")

        return changes


# ===== TELEGRAM HANDLERS =====

async def start_inventory_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать проверку инвентаря"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    shift_manager = context.bot_data.get('shift_manager')
    if not shift_manager:
        await query.edit_message_text("❌ Модуль смен недоступен")
        return ConversationHandler.END

    active_shift = shift_manager.get_active_shift(user_id)
    if not active_shift:
        await query.edit_message_text("❌ У вас нет активной смены")
        return ConversationHandler.END

    context.user_data['inv_shift_id'] = active_shift['id']
    context.user_data['inv_club'] = active_shift['club']
    context.user_data['inv_admin_id'] = user_id

    text = "📦 *Чек-лист приема смены*\n\n"
    text += f"🏢 Клуб: {active_shift['club'].upper()}\n\n"
    text += "🖱 *Мыши*\n"
    text += "Сколько мышей на столах?\n\n"
    text += "Введите число или /cancel для отмены"

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="inventory_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return INV_MICE_TABLES


async def inv_mice_tables(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество мышей на столах"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['mice_tables'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        text = "🖱 *Мыши*\n\n"
        text += "Сколько мышей в запасе?\n\n"
        text += "Введите число:"

        await update.message.reply_text(text, parse_mode='Markdown')
        return INV_MICE_STOCK

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_MICE_TABLES


async def inv_mice_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество мышей в запасе"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['mice_stock'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        text = "🖱 *Донглы для беспроводных мышей*\n\n"
        text += "Сколько донглов в запасе?\n\n"
        text += "Введите число:"

        await update.message.reply_text(text, parse_mode='Markdown')
        return INV_MICE_DONGLES

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_MICE_STOCK


async def inv_mice_dongles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество донглов"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['mice_dongles'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        text = "⌨️ *Клавиатуры*\n\n"
        text += "Сколько клавиатур на столах?\n\n"
        text += "Введите число:"

        await update.message.reply_text(text, parse_mode='Markdown')
        return INV_KB_TABLES

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_MICE_DONGLES


async def inv_kb_tables(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество клавиатур на столах"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['kb_tables'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        text = "⌨️ *Клавиатуры*\n\n"
        text += "Сколько клавиатур в запасе?\n\n"
        text += "Введите число:"

        await update.message.reply_text(text, parse_mode='Markdown')
        return INV_KB_STOCK

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_KB_TABLES


async def inv_kb_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество клавиатур в запасе"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['kb_stock'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        text = "🎧 *Наушники*\n\n"
        text += "Сколько наушников на столах?\n\n"
        text += "Введите число:"

        await update.message.reply_text(text, parse_mode='Markdown')
        return INV_HS_TABLES

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_KB_STOCK


async def inv_hs_tables(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество наушников на столах"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['hs_tables'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        text = "🎧 *Наушники*\n\n"
        text += "Сколько наушников в запасе?\n\n"
        text += "Введите число:"

        await update.message.reply_text(text, parse_mode='Markdown')
        return INV_HS_STOCK

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_HS_TABLES


async def inv_hs_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество наушников в запасе"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['hs_stock'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        text = "🎧 *Микрофоны для наушников*\n\n"
        text += "Сколько микрофонов в запасе?\n\n"
        text += "Введите число:"

        await update.message.reply_text(text, parse_mode='Markdown')
        return INV_HS_MICS

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_HS_STOCK


async def inv_hs_mics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество микрофонов"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['hs_mics'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        text = "🎧 *Провода для наушников*\n\n"
        text += "Сколько проводов в запасе?\n\n"
        text += "Введите число:"

        await update.message.reply_text(text, parse_mode='Markdown')
        return INV_HS_CABLES

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_HS_MICS


async def inv_hs_cables(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество проводов"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['hs_cables'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        # Если клуб Рио - спрашиваем про зарядки
        club = context.user_data.get('inv_club', '')
        if club == 'rio':
            text = "🔌 *Зарядки для клиентов*\n\n"
            text += "Сколько зарядок в запасе?\n\n"
            text += "Введите число:"

            await update.message.reply_text(text, parse_mode='Markdown')
            return INV_CHARGERS
        else:
            # Для Севера пропускаем зарядки
            context.user_data['chargers'] = 0
            return await save_inventory(update, context)

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_HS_CABLES


async def inv_chargers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить количество зарядок (только Рио)"""
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
        context.user_data['chargers'] = count

        # Удаляем сообщение админа
        try:
            await update.message.delete()
        except:
            pass

        return await save_inventory(update, context)

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return INV_CHARGERS


async def save_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранить инвентарь и проверить изменения"""
    shift_id = context.user_data['inv_shift_id']
    club = context.user_data['inv_club']
    admin_id = context.user_data['inv_admin_id']

    db_path = context.bot_data.get('db_path', 'club_assistant.db')
    manager = InventoryChecklistManager(db_path)

    # Сохраняем
    success = manager.save_inventory(
        shift_id=shift_id,
        club=club,
        admin_id=admin_id,
        mice_tables=context.user_data.get('mice_tables', 0),
        mice_stock=context.user_data.get('mice_stock', 0),
        mice_dongles=context.user_data.get('mice_dongles', 0),
        kb_tables=context.user_data.get('kb_tables', 0),
        kb_stock=context.user_data.get('kb_stock', 0),
        hs_tables=context.user_data.get('hs_tables', 0),
        hs_stock=context.user_data.get('hs_stock', 0),
        hs_mics=context.user_data.get('hs_mics', 0),
        hs_cables=context.user_data.get('hs_cables', 0),
        chargers=context.user_data.get('chargers', 0)
    )

    if not success:
        await update.message.reply_text("❌ Ошибка сохранения")
        context.user_data.clear()
        return ConversationHandler.END

    # Получаем текущие данные
    current = manager.get_inventory(shift_id)
    previous = manager.get_previous_day_inventory(club)

    text = "✅ *Инвентарь сохранен!*\n\n"

    # Сравниваем с предыдущим днем
    if previous:
        changes = manager.compare_with_previous(current, previous)
        if changes:
            text += "⚠️ *Обнаружены изменения:*\n\n"
            for change in changes:
                text += f"• {change}\n"

            # Отправляем алерт владельцу и Глазу
            owner_id = context.bot_data.get('owner_id')
            if owner_id:
                alert_text = f"⚠️ *Изменение инвентаря в {club.upper()}*\n\n"
                alert_text += "\n".join(f"• {c}" for c in changes)
                try:
                    await context.bot.send_message(owner_id, alert_text, parse_mode='Markdown')
                except:
                    pass
        else:
            text += "✅ Инвентарь совпадает с предыдущим днем"
    else:
        text += "ℹ️ Нет данных за предыдущий день для сравнения"

    await update.message.reply_text(text, parse_mode='Markdown')

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить заполнение инвентаря"""
    context.user_data.clear()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Заполнение чек-листа инвентаря отменено")
    else:
        await update.message.reply_text("❌ Заполнение отменено")

    return ConversationHandler.END


def create_inventory_handlers():
    """Создать обработчики для инвентаря"""
    from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_inventory_check, pattern="^inventory_start$")
        ],
        states={
            INV_MICE_TABLES: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_mice_tables)],
            INV_MICE_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_mice_stock)],
            INV_MICE_DONGLES: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_mice_dongles)],
            INV_KB_TABLES: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_kb_tables)],
            INV_KB_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_kb_stock)],
            INV_HS_TABLES: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_hs_tables)],
            INV_HS_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_hs_stock)],
            INV_HS_MICS: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_hs_mics)],
            INV_HS_CABLES: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_hs_cables)],
            INV_CHARGERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_chargers)]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_inventory),
            CallbackQueryHandler(cancel_inventory, pattern="^inventory_cancel$")
        ],
        per_message=False,
        per_chat=True,
        per_user=True
    )

    return [conv_handler]
