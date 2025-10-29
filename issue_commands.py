#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Issue Commands - Команды управления проблемами клуба
Для владельца и админов
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# Состояния conversation handler
ISSUE_SELECT_CLUB, ISSUE_ENTER_DESCRIPTION, ISSUE_EDIT_DESCRIPTION = range(3)


class IssueCommands:
    """Обработчик команд управления проблемами"""
    
    def __init__(self, issue_manager, knowledge_base, admin_manager, owner_id: int, bot_app):
        self.issue_manager = issue_manager
        self.kb = knowledge_base
        self.admin_manager = admin_manager
        self.owner_id = owner_id
        self.bot_app = bot_app
    
    def is_owner(self, user_id: int) -> bool:
        """Проверка что пользователь - владелец"""
        return user_id == self.owner_id
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка что пользователь - админ"""
        return self.admin_manager.is_admin(user_id)
    
    async def show_issue_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню проблем"""
        query = update.callback_query
        
        if query:
            user_id = query.from_user.id
            await query.answer()
        else:
            user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            text = "❌ Доступно только админам"
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        keyboard = []
        
        # Кнопки для всех админов
        keyboard.append([InlineKeyboardButton("🔴 Сообщить о проблеме", callback_data="issue_report")])
        keyboard.append([InlineKeyboardButton("📋 Проблемы клуба", callback_data="issue_list")])
        
        # Кнопки для владельца
        if self.is_owner(user_id):
            active_count = self.issue_manager.get_active_count()
            keyboard.append([InlineKeyboardButton(
                f"⚠️ Текущие проблемы ({active_count})", 
                callback_data="issue_current"
            )])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "⚠️ ПРОБЛЕМЫ КЛУБА\n\n"
        text += "Система отслеживания и решения проблем"
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def start_report_issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать сообщение о проблеме"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(query.from_user.id):
            await query.edit_message_text("❌ Доступно только админам")
            return ConversationHandler.END
        
        keyboard = [
            [InlineKeyboardButton("🏢 Рио", callback_data="issue_club_rio")],
            [InlineKeyboardButton("🏢 Мичуринская/Север", callback_data="issue_club_mich")],
            [InlineKeyboardButton("❌ Отмена", callback_data="issue_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔴 СООБЩИТЬ О ПРОБЛЕМЕ\n\nВыберите клуб:",
            reply_markup=reply_markup
        )
        
        return ISSUE_SELECT_CLUB
    
    async def select_club_for_issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор клуба для проблемы"""
        query = update.callback_query
        await query.answer()
        
        club = 'rio' if 'rio' in query.data else 'michurinskaya'
        context.user_data['issue_club'] = club
        
        club_name = "Рио" if club == 'rio' else "Мичуринская/Север"
        
        await query.edit_message_text(
            f"Клуб: {club_name}\n\n"
            "Опишите проблему подробно:"
        )
        
        return ISSUE_ENTER_DESCRIPTION
    
    async def enter_issue_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ввод описания проблемы"""
        description = update.message.text
        club = context.user_data['issue_club']
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name or update.effective_user.username or str(user_id)
        
        # 1. Записываем в БД проблем
        issue_id = self.issue_manager.create_issue(
            club=club,
            description=description,
            created_by=user_id,
            created_by_name=user_name
        )
        
        if not issue_id:
            await update.message.reply_text("❌ Ошибка создания проблемы")
            context.user_data.clear()
            return ConversationHandler.END
        
        # 2. Уведомляем владельца
        notification_text = self.issue_manager.format_notification(issue_id)
        
        try:
            # Отправляем уведомление владельцу
            await self.bot_app.bot.send_message(
                chat_id=self.owner_id,
                text=notification_text
            )
            logger.info(f"✅ Owner notified about issue #{issue_id}")
        except Exception as e:
            logger.error(f"❌ Failed to notify owner: {e}")
        
        # 3. Добавляем в базу знаний
        try:
            club_names = {'rio': 'Рио', 'michurinskaya': 'Мичуринская/Север'}
            question = f"Проблема в клубе {club_names[club]}"
            answer = f"Проблема #{issue_id}: {description}\nСтатус: активная\nСообщил: {user_name}"
            
            self.kb.add(
                question=question,
                answer=answer,
                category='club_issue',
                tags=f'issue,{club}',
                source='issue_tracker',
                added_by=user_id
            )
            logger.info(f"✅ Issue #{issue_id} added to knowledge base")
        except Exception as e:
            logger.error(f"❌ Failed to add issue to KB: {e}")
        
        # Подтверждение админу
        text = f"✅ Проблема #{issue_id} зарегистрирована\n\n"
        text += "• Записана в базу данных\n"
        text += "• Владелец уведомлён\n"
        text += "• Добавлена в базу знаний бота"
        
        keyboard = [[InlineKeyboardButton("◀️ В меню проблем", callback_data="issue_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def show_issues_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список проблем"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(query.from_user.id):
            await query.edit_message_text("❌ Доступно только админам")
            return
        
        keyboard = [
            [InlineKeyboardButton("🏢 Рио", callback_data="issue_filter_rio"),
             InlineKeyboardButton("🏢 Мичуринская", callback_data="issue_filter_mich")],
            [InlineKeyboardButton("🔴 Активные", callback_data="issue_filter_active"),
             InlineKeyboardButton("✅ Решённые", callback_data="issue_filter_resolved")],
            [InlineKeyboardButton("📋 Все", callback_data="issue_filter_all")],
            [InlineKeyboardButton("◀️ Назад", callback_data="issue_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите фильтр для просмотра проблем:",
            reply_markup=reply_markup
        )
    
    async def show_filtered_issues(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать отфильтрованные проблемы"""
        query = update.callback_query
        await query.answer()
        
        # Извлекаем фильтр из callback_data
        data = query.data
        
        club = None
        status = None
        title = "ВСЕ ПРОБЛЕМЫ"
        
        if 'rio' in data:
            club = 'rio'
            title = "ПРОБЛЕМЫ - РИО"
        elif 'mich' in data:
            club = 'michurinskaya'
            title = "ПРОБЛЕМЫ - МИЧУРИНСКАЯ"
        
        if 'active' in data:
            status = 'active'
            title += " (АКТИВНЫЕ)"
        elif 'resolved' in data:
            status = 'resolved'
            title += " (РЕШЁННЫЕ)"
        elif 'all' in data:
            status = None
        
        issues = self.issue_manager.list_issues(club=club, status=status)
        text = self.issue_manager.format_issues_list(issues, title)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="issue_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_current_issues(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать текущие проблемы (только владелец)"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        issues = self.issue_manager.list_issues(status='active')
        
        if not issues:
            text = "✅ Нет активных проблем"
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="issue_menu")]]
        else:
            text = "⚠️ ТЕКУЩИЕ ПРОБЛЕМЫ\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            keyboard = []
            
            for issue in issues[:10]:  # Показываем максимум 10
                club_emoji = "🏢"
                desc_short = issue['description'][:30] + "..." if len(issue['description']) > 30 else issue['description']
                
                keyboard.append([InlineKeyboardButton(
                    f"#{issue['id']} | {desc_short}",
                    callback_data=f"issue_manage_{issue['id']}"
                )])
            
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="issue_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def manage_issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Управление конкретной проблемой"""
        query = update.callback_query
        await query.answer()

        # Проверка прав: владелец ИЛИ право issues_edit
        user_id = query.from_user.id
        if not (self.is_owner(user_id) or self.admin_manager.has_permission(user_id, 'issues_edit')):
            await query.edit_message_text("❌ У вас нет прав на управление проблемами")
            return
        
        # Извлекаем ID проблемы из callback_data
        issue_id = int(query.data.split('_')[-1])
        
        issue = self.issue_manager.get_issue(issue_id)
        
        if not issue:
            await query.edit_message_text("❌ Проблема не найдена")
            return
        
        text = self.issue_manager.format_issue(issue)
        
        keyboard = [
            [InlineKeyboardButton("✅ Решена", callback_data=f"issue_resolve_{issue_id}")],
            [InlineKeyboardButton("✏️ Редактировать", callback_data=f"issue_edit_{issue_id}")],
            [InlineKeyboardButton("🗑️ Удалить", callback_data=f"issue_delete_{issue_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="issue_current")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def resolve_issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Пометить проблему как решённую"""
        query = update.callback_query
        await query.answer()

        # Проверка прав: владелец ИЛИ право issues_edit
        user_id = query.from_user.id
        if not (self.is_owner(user_id) or self.admin_manager.has_permission(user_id, 'issues_edit')):
            await query.edit_message_text("❌ У вас нет прав на управление проблемами")
            return
        
        issue_id = int(query.data.split('_')[-1])
        
        # Получаем проблему перед решением
        issue = self.issue_manager.get_issue(issue_id)
        
        success = self.issue_manager.resolve_issue(issue_id)
        
        if success:
            # Обновляем в базе знаний
            try:
                club_names = {'rio': 'Рио', 'michurinskaya': 'Мичуринская/Север'}
                question = f"Проблема в клубе {club_names[issue['club']]}"
                answer = f"Проблема #{issue_id}: {issue['description']}\nСтатус: РЕШЕНА\nСообщил: {issue['created_by_name']}"
                
                self.kb.add(
                    question=question,
                    answer=answer,
                    category='club_issue',
                    tags=f'issue,{issue["club"]},resolved',
                    source='issue_tracker',
                    added_by=self.owner_id
                )
            except Exception as e:
                logger.error(f"❌ Failed to update KB: {e}")
            
            text = f"✅ Проблема #{issue_id} помечена как решённая"
        else:
            text = "❌ Ошибка"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="issue_current")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def start_edit_issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать редактирование проблемы"""
        query = update.callback_query
        await query.answer()

        # Проверка прав: владелец ИЛИ право issues_edit
        user_id = query.from_user.id
        if not (self.is_owner(user_id) or self.admin_manager.has_permission(user_id, 'issues_edit')):
            await query.edit_message_text("❌ У вас нет прав на управление проблемами")
            return ConversationHandler.END
        
        issue_id = int(query.data.split('_')[-1])
        context.user_data['edit_issue_id'] = issue_id
        
        issue = self.issue_manager.get_issue(issue_id)
        
        await query.edit_message_text(
            f"Текущее описание:\n{issue['description']}\n\n"
            "Введите новое описание:"
        )
        
        return ISSUE_EDIT_DESCRIPTION
    
    async def edit_issue_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранить новое описание проблемы"""
        new_description = update.message.text
        issue_id = context.user_data['edit_issue_id']
        
        issue = self.issue_manager.get_issue(issue_id)
        
        success = self.issue_manager.update_issue(issue_id, new_description)
        
        if success:
            # Обновляем в базе знаний
            try:
                club_names = {'rio': 'Рио', 'michurinskaya': 'Мичуринская/Север'}
                question = f"Проблема в клубе {club_names[issue['club']]}"
                answer = f"Проблема #{issue_id}: {new_description}\nСтатус: {issue['status']}\nСообщил: {issue['created_by_name']}"
                
                self.kb.add(
                    question=question,
                    answer=answer,
                    category='club_issue',
                    tags=f'issue,{issue["club"]}',
                    source='issue_tracker',
                    added_by=self.owner_id
                )
            except Exception as e:
                logger.error(f"❌ Failed to update KB: {e}")
            
            text = f"✅ Проблема #{issue_id} обновлена"
        else:
            text = "❌ Ошибка"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="issue_current")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def delete_issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удалить проблему"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Доступно только владельцу")
            return
        
        issue_id = int(query.data.split('_')[-1])
        
        success = self.issue_manager.delete_issue(issue_id)
        
        if success:
            text = f"✅ Проблема #{issue_id} удалена"
        else:
            text = "❌ Ошибка"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="issue_current")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена операции"""
        context.user_data.clear()
        await self.show_issue_menu(update, context)
        return ConversationHandler.END
