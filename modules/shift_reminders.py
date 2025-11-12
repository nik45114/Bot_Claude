"""
Модуль системы напоминаний для чек-листов смены
Использует JobQueue для периодических проверок
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))

# Reminder types
REMINDER_INVENTORY = 'inventory'
REMINDER_CLEANING_RATING = 'cleaning_rating'
REMINDER_SHIFT_NOT_OPENED = 'shift_not_opened'


class ShiftReminderManager:
    """Менеджер напоминаний о чек-листах"""

    def __init__(self, db_path: str = 'club_assistant.db'):
        self.db_path = db_path

    def create_reminder(self, shift_id: int, reminder_type: str, next_reminder_at: Optional[datetime] = None) -> bool:
        """Создать напоминание"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO shift_reminders (shift_id, reminder_type, next_reminder_at)
                VALUES (?, ?, ?)
            """, (shift_id, reminder_type, next_reminder_at))

            conn.commit()
            conn.close()
            logger.info(f"Created reminder {reminder_type} for shift {shift_id}")
            return True

        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            return False

    def resolve_reminder(self, shift_id: int, reminder_type: str) -> bool:
        """Пометить напоминание как выполненное"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE shift_reminders
                SET is_resolved = 1
                WHERE shift_id = ? AND reminder_type = ? AND is_resolved = 0
            """, (shift_id, reminder_type))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Error resolving reminder: {e}")
            return False

    def get_active_reminders(self, reminder_type: Optional[str] = None) -> List[Dict]:
        """Получить активные напоминания"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if reminder_type:
                cursor.execute("""
                    SELECT * FROM shift_reminders
                    WHERE reminder_type = ? AND is_resolved = 0
                    ORDER BY next_reminder_at ASC
                """, (reminder_type,))
            else:
                cursor.execute("""
                    SELECT * FROM shift_reminders
                    WHERE is_resolved = 0
                    ORDER BY next_reminder_at ASC
                """)

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting active reminders: {e}")
            return []

    def update_next_reminder(self, reminder_id: int, next_reminder_at: datetime) -> bool:
        """Обновить время следующего напоминания"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE shift_reminders
                SET next_reminder_at = ?
                WHERE id = ?
            """, (next_reminder_at, reminder_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Error updating reminder: {e}")
            return False


# ===== JOB QUEUE FUNCTIONS =====

async def check_unopened_shifts(context: ContextTypes.DEFAULT_TYPE):
    """
    Проверка смен, которые не открыты через 30 минут после закрытия предыдущей
    Запускается каждые 5 минут
    """
    try:
        db_path = context.bot_data.get('db_path', 'club_assistant.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Находим смены, которые закрыты более 30 минут назад
        cutoff_time = datetime.now(MSK) - timedelta(minutes=30)

        cursor.execute("""
            SELECT s.*, a.full_name as admin_name
            FROM active_shifts s
            LEFT JOIN admins a ON s.admin_id = a.user_id
            WHERE s.status = 'closed'
            AND s.closed_at <= ?
            AND s.club IN ('rio', 'sever')
        """, (cutoff_time,))

        closed_shifts = cursor.fetchall()

        for shift in closed_shifts:
            club = shift['club']
            shift_id = shift['id']
            end_time = datetime.fromisoformat(shift['closed_at'])

            # Проверяем, есть ли новая открытая смена после этой
            cursor.execute("""
                SELECT id FROM active_shifts
                WHERE club = ? AND opened_at > ? AND status = 'open'
            """, (club, end_time))

            new_shift = cursor.fetchone()

            if not new_shift:
                # Проверяем, не отправляли ли уже это напоминание
                cursor.execute("""
                    SELECT id FROM shift_reminders
                    WHERE shift_id = ? AND reminder_type = ? AND is_resolved = 0
                """, (shift_id, REMINDER_SHIFT_NOT_OPENED))

                existing_reminder = cursor.fetchone()

                if not existing_reminder:
                    # Отправляем напоминание в чат клуба
                    club_accounts = context.bot_data.get('club_accounts', {})
                    club_chat_id = club_accounts.get(club)

                    if club_chat_id:
                        text = f"⚠️ *Внимание!*\n\n"
                        text += f"Прошло более 30 минут после закрытия смены.\n"
                        text += f"Пожалуйста, откройте новую смену через /start"

                        await context.bot.send_message(
                            chat_id=club_chat_id,
                            text=text,
                            parse_mode='Markdown'
                        )

                    # Отправляем уведомление владельцу и Глазу
                    owner_id = context.bot_data.get('owner_id')
                    controller_id = context.bot_data.get('controller_id')

                    alert_text = f"⚠️ *Смена не открыта - {club.upper()}*\n\n"
                    alert_text += f"Закрыта: {end_time.strftime('%H:%M')}\n"
                    alert_text += f"Прошло: более 30 минут\n"
                    alert_text += f"Последний админ: {shift['admin_name'] if shift['admin_name'] else 'Неизвестно'}"

                    if owner_id:
                        await context.bot.send_message(owner_id, alert_text, parse_mode='Markdown')

                    if controller_id:
                        await context.bot.send_message(controller_id, alert_text, parse_mode='Markdown')

                    # Создаем запись о напоминании
                    reminder_manager = ShiftReminderManager(db_path)
                    reminder_manager.create_reminder(shift_id, REMINDER_SHIFT_NOT_OPENED)

                    logger.info(f"Sent unopened shift reminder for {club}")

        conn.close()

    except Exception as e:
        logger.error(f"Error checking unopened shifts: {e}")
        import traceback
        traceback.print_exc()


async def check_inventory_deadlines(context: ContextTypes.DEFAULT_TYPE):
    """
    Проверка дедлайнов инвентаря (4 часа после открытия смены)
    Напоминания: через 3 часа (за 1ч до дедлайна), через 2 часа (на рабочий аккаунт), после 4 часов (владельцу)
    Запускается каждые 5 минут
    """
    try:
        db_path = context.bot_data.get('db_path', 'club_assistant.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        now = datetime.now(MSK)

        # Находим активные смены без заполненного инвентаря
        cursor.execute("""
            SELECT s.*, a.full_name as admin_name, a.user_id as admin_user_id
            FROM active_shifts s
            LEFT JOIN admins a ON s.admin_id = a.user_id
            LEFT JOIN shift_inventory_checklist ic ON s.id = ic.shift_id
            WHERE s.status = 'open'
            AND ic.id IS NULL
        """)

        active_shifts = cursor.fetchall()

        for shift in active_shifts:
            shift_id = shift['id']
            club = shift['club']
            admin_id = shift['admin_user_id']
            start_time = datetime.fromisoformat(shift['opened_at']).replace(tzinfo=MSK)

            time_elapsed = (now - start_time).total_seconds() / 3600  # в часах

            # Напоминание через 3 часа (за 1 час до дедлайна) - второе напоминание
            if 3.0 <= time_elapsed < 3.1:
                # Проверяем, сколько раз уже отправляли напоминания
                cursor.execute("""
                    SELECT COUNT(*) FROM shift_reminders
                    WHERE shift_id = ? AND reminder_type = ?
                """, (shift_id, REMINDER_INVENTORY))

                reminder_count = cursor.fetchone()[0]

                if reminder_count == 1:
                    text = f"⏰ *Напоминание об инвентаре*\n\n"
                    text += f"Осталось 1 час до дедлайна заполнения чек-листа инвентаря.\n"
                    text += f"Пожалуйста, заполните его в ближайшее время."

                    if admin_id:
                        await context.bot.send_message(admin_id, text, parse_mode='Markdown')

                    reminder_manager = ShiftReminderManager(db_path)
                    reminder_manager.create_reminder(shift_id, REMINDER_INVENTORY)
                    logger.info(f"Sent 3-hour inventory reminder for shift {shift_id}")

            # Напоминание через 2 часа (на рабочий аккаунт клуба) - первое напоминание
            elif 2.0 <= time_elapsed < 2.1:
                # Проверяем, сколько раз уже отправляли напоминания
                cursor.execute("""
                    SELECT COUNT(*) FROM shift_reminders
                    WHERE shift_id = ? AND reminder_type = ?
                """, (shift_id, REMINDER_INVENTORY))

                reminder_count = cursor.fetchone()[0]

                if reminder_count == 0:
                    club_accounts = context.bot_data.get('club_accounts', {})
                    club_chat_id = club_accounts.get(club)

                    text = f"⏰ *Напоминание об инвентаре*\n\n"
                    text += f"Осталось 2 часа до дедлайна.\n"
                    text += f"Админ: {shift['admin_name'] if shift['admin_name'] else 'Неизвестно'}"

                    if club_chat_id:
                        await context.bot.send_message(club_chat_id, text, parse_mode='Markdown')

                    reminder_manager = ShiftReminderManager(db_path)
                    reminder_manager.create_reminder(shift_id, REMINDER_INVENTORY)
                    logger.info(f"Sent 2-hour inventory reminder for shift {shift_id}")

            # Уведомление владельцу после 4 часов (просрочено) - третье напоминание
            elif time_elapsed >= 4.0:
                # Проверяем, сколько раз уже отправляли напоминания
                cursor.execute("""
                    SELECT COUNT(*) FROM shift_reminders
                    WHERE shift_id = ? AND reminder_type = ?
                """, (shift_id, REMINDER_INVENTORY))

                reminder_count = cursor.fetchone()[0]

                if reminder_count == 2:
                    owner_id = context.bot_data.get('owner_id')
                    controller_id = context.bot_data.get('controller_id')

                    alert_text = f"❌ *Просрочен чек-лист инвентаря*\n\n"
                    alert_text += f"🏢 Клуб: {club.upper()}\n"
                    alert_text += f"👤 Админ: {shift['admin_name'] if shift['admin_name'] else 'Неизвестно'}\n"
                    alert_text += f"⏰ Прошло: {int(time_elapsed)} часов\n"
                    alert_text += f"📅 Начало смены: {start_time.strftime('%H:%M')}"

                    if owner_id:
                        await context.bot.send_message(owner_id, alert_text, parse_mode='Markdown')

                    if controller_id:
                        await context.bot.send_message(controller_id, alert_text, parse_mode='Markdown')

                    reminder_manager = ShiftReminderManager(db_path)
                    reminder_manager.create_reminder(shift_id, REMINDER_INVENTORY)
                    logger.info(f"Sent overdue inventory alert for shift {shift_id}")

        conn.close()

    except Exception as e:
        logger.error(f"Error checking inventory deadlines: {e}")


async def check_cleaning_rating_deadline(context: ContextTypes.DEFAULT_TYPE):
    """
    Проверка дедлайна рейтинга уборки (30 минут после открытия смены)
    Запускается каждые 5 минут
    """
    try:
        db_path = context.bot_data.get('db_path', 'club_assistant.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        now = datetime.now(MSK)
        cutoff_time = now - timedelta(minutes=30)

        # Находим смены, открытые более 30 минут назад без заполненного рейтинга уборки
        cursor.execute("""
            SELECT s.*, a.full_name as admin_name, a.user_id as admin_user_id
            FROM active_shifts s
            LEFT JOIN admins a ON s.admin_id = a.user_id
            LEFT JOIN shift_cleaning_rating scr ON s.id = scr.shift_id
            WHERE s.opened_at <= ? AND s.status = 'open'
            AND (scr.id IS NULL OR scr.rated_at IS NULL)
        """, (cutoff_time,))

        overdue_shifts = cursor.fetchall()

        for shift in overdue_shifts:
            shift_id = shift['id']
            club = shift['club']
            admin_id = shift['admin_user_id']

            # Проверяем, не отправляли ли уже напоминание для этой смены
            cursor.execute("""
                SELECT id FROM shift_reminders
                WHERE shift_id = ? AND reminder_type = ?
            """, (shift_id, REMINDER_CLEANING_RATING))

            if not cursor.fetchone():
                # Отправляем напоминание админу
                text = f"⚠️ *Напоминание о рейтинге уборки*\n\n"
                text += f"Прошло более 30 минут с начала смены.\n"
                text += f"Пожалуйста, оцените качество уборки предыдущего админа."

                if admin_id:
                    await context.bot.send_message(admin_id, text, parse_mode='Markdown')

                # Уведомляем владельца и Глаза
                owner_id = context.bot_data.get('owner_id')
                controller_id = context.bot_data.get('controller_id')

                alert_text = f"⚠️ *Не заполнен рейтинг уборки*\n\n"
                alert_text += f"🏢 Клуб: {club.upper()}\n"
                alert_text += f"👤 Админ: {shift['admin_name'] if shift['admin_name'] else 'Неизвестно'}\n"
                alert_text += f"⏰ Прошло: более 30 минут"

                if owner_id:
                    await context.bot.send_message(owner_id, alert_text, parse_mode='Markdown')

                if controller_id:
                    await context.bot.send_message(controller_id, alert_text, parse_mode='Markdown')

                # Создаем запись о напоминании
                reminder_manager = ShiftReminderManager(db_path)
                reminder_manager.create_reminder(shift_id, REMINDER_CLEANING_RATING)

                logger.info(f"Sent cleaning rating reminder for shift {shift_id}")

        conn.close()

    except Exception as e:
        logger.error(f"Error checking cleaning rating deadline: {e}")


async def check_system_health(context: ContextTypes.DEFAULT_TYPE):
    """
    Проверка здоровья системы (CPU, RAM, Disk)
    Запускается каждые 5 минут
    """
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        alerts = []

        if cpu_percent > 80:
            alerts.append(f"🔴 CPU: {cpu_percent}% (критично)")

        if memory.percent > 85:
            alerts.append(f"🔴 RAM: {memory.percent}% (критично)")

        if disk.percent > 90:
            alerts.append(f"🔴 Диск: {disk.percent}% (критично)")

        if alerts:
            owner_id = context.bot_data.get('owner_id')

            text = "⚠️ *Критические показатели системы*\n\n"
            text += "\n".join(alerts)
            text += f"\n\n📊 Детали:\n"
            text += f"• CPU: {cpu_percent}%\n"
            text += f"• RAM: {memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)\n"
            text += f"• Диск: {disk.percent}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)"

            if owner_id:
                await context.bot.send_message(owner_id, text, parse_mode='Markdown')
                logger.warning(f"System health alert sent: CPU={cpu_percent}%, RAM={memory.percent}%, Disk={disk.percent}%")

    except Exception as e:
        logger.error(f"Error checking system health: {e}")


def setup_reminder_jobs(application):
    """
    Настроить все периодические задачи JobQueue
    Вызывается при запуске бота
    """
    job_queue = application.job_queue

    # Проверка нераскрытых смен - каждые 5 минут
    job_queue.run_repeating(
        check_unopened_shifts,
        interval=timedelta(minutes=5),
        first=timedelta(seconds=10),
        name='check_unopened_shifts'
    )

    # Проверка дедлайнов инвентаря - каждые 5 минут
    job_queue.run_repeating(
        check_inventory_deadlines,
        interval=timedelta(minutes=5),
        first=timedelta(seconds=20),
        name='check_inventory_deadlines'
    )

    # Проверка дедлайна рейтинга уборки - каждые 5 минут
    job_queue.run_repeating(
        check_cleaning_rating_deadline,
        interval=timedelta(minutes=5),
        first=timedelta(seconds=30),
        name='check_cleaning_rating_deadline'
    )

    # Проверка здоровья системы - каждые 5 минут
    job_queue.run_repeating(
        check_system_health,
        interval=timedelta(minutes=5),
        first=timedelta(seconds=40),
        name='check_system_health'
    )

    logger.info("All reminder jobs scheduled successfully")
