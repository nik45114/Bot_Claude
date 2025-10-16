#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Commands - Команды управления клубами
Только для владельца
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_REPORT = 1


class ClubCommands:
    """Команды управления клубами"""
    
    def __init__(self, manager, owner_id: int):
        self.manager = manager
        self.owner_id = owner_id
        self.pending_reports = {}  # {user_id: club_id}
    
    def is_owner(self, user_id: int) -> bool:
        return user_id == self.owner_id
    
    async def cmd_clubs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню клубов"""
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        text = """🏢 Управление клубами

Команды:

📋 Клубы:
/clubadd <название> <адрес> - добавить клуб
/clublist - список клубов
/clubstats <название> [дней] - статистика

📊 Отчёты:
/report <клуб> - начать отчёт смены
/lastreport <клуб> - последний отчёт
/issues [клуб] - проблемы

Пример:
/clubadd Центральный Ленина 123
/report Центральный
→ Отправь текст отчёта"""
        
        await update.message.reply_text(text)
    
    async def cmd_clubadd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление клуба: /clubadd <название> <адрес>"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 1:
                await update.message.reply_text(
                    "Использование: /clubadd <название> [адрес]\n\n"
                    "Пример: /clubadd Центральный Ленина 123"
                )
                return
            
            name = context.args[0]
            address = ' '.join(context.args[1:]) if len(context.args) > 1 else ""
            
            if self.manager.add_club(name, address=address):
                await update.message.reply_text(
                    f"✅ Клуб '{name}' добавлен!\n\n"
                    f"📍 Адрес: {address or 'не указан'}\n\n"
                    f"Теперь админы могут сдавать отчёты:\n"
                    f"/report {name}"
                )
            else:
                await update.message.reply_text("❌ Ошибка добавления клуба")
        
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_clublist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список клубов"""
        if not self.is_owner(update.effective_user.id):
            return
        
        clubs = self.manager.list_clubs()
        
        if not clubs:
            await update.message.reply_text("📭 Нет клубов")
            return
        
        text = "🏢 Клубы:\n\n"
        
        for club in clubs:
            text += f"🔹 {club['name']}\n"
            if club['address']:
                text += f"   📍 {club['address']}\n"
            if club['phone']:
                text += f"   📞 {club['phone']}\n"
            text += "\n"
        
        await update.message.reply_text(text)
    
    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало отчёта: /report <клуб>"""
        try:
            if len(context.args) < 1:
                await update.message.reply_text(
                    "Использование: /report <клуб>\n\n"
                    "Пример: /report Центральный"
                )
                return
            
            club_name = context.args[0]
            clubs = self.manager.list_clubs()
            club = next((c for c in clubs if c['name'].lower() == club_name.lower()), None)
            
            if not club:
                await update.message.reply_text(
                    f"❌ Клуб '{club_name}' не найден\n\n"
                    f"Доступные клубы: /clublist"
                )
                return
            
            # Сохраняем клуб для этого пользователя
            self.pending_reports[update.effective_user.id] = club['id']
            
            text = f"""📋 Отчёт смены - {club['name']}

Отправь отчёт в любом формате.

Пример:
Вечер 15.10
Факт нал 3 940 / 20 703
Наличка в сейфе 927
Факт бн 16 327
QR 3 753
Джойстиков 15
3 в ремонте
Туалетка есть
Бумажные полотенца нет

Я распарсю и сохраню красиво!"""
            
            await update.message.reply_text(text)
            return WAITING_REPORT
        
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            return ConversationHandler.END
    
    async def handle_report_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текста отчёта"""
        user_id = update.effective_user.id
        
        if user_id not in self.pending_reports:
            await update.message.reply_text(
                "❌ Сначала начни отчёт: /report <клуб>"
            )
            return ConversationHandler.END
        
        try:
            club_id = self.pending_reports[user_id]
            text = update.message.text
            
            await update.message.reply_text("⏳ Обрабатываю отчёт...")
            
            # Парсим отчёт
            report = self.manager.parse_report(text)
            
            # Сохраняем
            admin_name = update.effective_user.full_name or update.effective_user.username
            shift_id = self.manager.save_shift_report(
                club_id, 
                user_id, 
                admin_name, 
                report
            )
            
            if shift_id == 0:
                await update.message.reply_text("❌ Ошибка сохранения отчёта")
                return ConversationHandler.END
            
            # Форматируем и отправляем
            formatted = self.manager.format_report(shift_id)
            await update.message.reply_text(formatted)
            
            # Очищаем
            del self.pending_reports[user_id]
            
            return ConversationHandler.END
        
        except Exception as e:
            logger.error(f"Report error: {e}")
            await update.message.reply_text(f"❌ Ошибка обработки: {e}")
            return ConversationHandler.END
    
    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена отчёта"""
        user_id = update.effective_user.id
        if user_id in self.pending_reports:
            del self.pending_reports[user_id]
        await update.message.reply_text("❌ Отменено")
        return ConversationHandler.END
    
    async def cmd_lastreport(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Последний отчёт клуба: /lastreport <клуб>"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 1:
                await update.message.reply_text("Использование: /lastreport <клуб>")
                return
            
            club_name = context.args[0]
            clubs = self.manager.list_clubs()
            club = next((c for c in clubs if c['name'].lower() == club_name.lower()), None)
            
            if not club:
                await update.message.reply_text(f"❌ Клуб '{club_name}' не найден")
                return
            
            # Получаем последнюю смену
            import sqlite3
            conn = sqlite3.connect(self.manager.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM shifts 
                WHERE club_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (club['id'],))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                await update.message.reply_text("📭 Нет отчётов")
                return
            
            shift_id = row[0]
            formatted = self.manager.format_report(shift_id)
            await update.message.reply_text(formatted)
        
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_clubstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика клуба: /clubstats <клуб> [дней]"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            if len(context.args) < 1:
                await update.message.reply_text(
                    "Использование: /clubstats <клуб> [дней]\n\n"
                    "Пример: /clubstats Центральный 7"
                )
                return
            
            club_name = context.args[0]
            days = int(context.args[1]) if len(context.args) > 1 else 7
            
            clubs = self.manager.list_clubs()
            club = next((c for c in clubs if c['name'].lower() == club_name.lower()), None)
            
            if not club:
                await update.message.reply_text(f"❌ Клуб '{club_name}' не найден")
                return
            
            await update.message.reply_text("⏳ Собираю статистику...")
            
            stats = self.manager.get_club_stats(club['id'], days)
            
            if not stats:
                await update.message.reply_text("❌ Нет данных")
                return
            
            avg_per_shift = stats['total_revenue'] / stats['shifts_count'] if stats['shifts_count'] > 0 else 0
            
            text = f"""📊 Статистика - {club['name']}
За последние {days} дней

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 ВЫРУЧКА
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 Наличные:  {stats['total_cash']:>10,} ₽
💳 Безнал:    {stats['total_cashless']:>10,} ₽
📱 QR:        {stats['total_qr']:>10,} ₽
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 ИТОГО:     {stats['total_revenue']:>10,} ₽

📈 Смен: {stats['shifts_count']}
📊 Средний чек: {avg_per_shift:>10,.0f} ₽

⚠️ Открытых проблем: {stats['open_issues']}"""
            
            await update.message.reply_text(text)
        
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_issues(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сводка по проблемам: /issues [клуб]"""
        if not self.is_owner(update.effective_user.id):
            return
        
        try:
            club_id = None
            
            if len(context.args) > 0:
                club_name = context.args[0]
                clubs = self.manager.list_clubs()
                club = next((c for c in clubs if c['name'].lower() == club_name.lower()), None)
                if club:
                    club_id = club['id']
            
            issues = self.manager.get_issues_summary(club_id)
            
            if not issues:
                await update.message.reply_text("✅ Нет открытых проблем!")
                return
            
            text = "⚠️ ОТКРЫТЫЕ ПРОБЛЕМЫ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, issue in enumerate(issues, 1):
                text += f"{i}. 🏢 {issue['club']}\n"
                text += f"   {issue['issue']}\n"
                text += f"   👤 {issue['admin']} • 📅 {issue['created_at'][:10]}\n\n"
            
            await update.message.reply_text(text)
        
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
