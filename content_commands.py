#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Content Generation Commands
Handlers for content generation features
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class ContentCommands:
    """Handles content generation commands"""
    
    def __init__(self, content_generator, admin_manager):
        self.content_generator = content_generator
        self.admin_manager = admin_manager
    
    async def cmd_generate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate command"""
        user_id = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text(
                "🎨 Генерация контента\n\n"
                "Использование:\n"
                "/generate <ваш запрос>\n\n"
                "Примеры:\n"
                "• /generate напиши статью про Python\n"
                "• /generate создай изображение космического корабля\n"
                "• /generate создай видео с анимацией логотипа\n\n"
                "💡 Бот автоматически определит тип контента!"
            )
            return
        
        prompt = ' '.join(context.args)
        
        # Show typing indicator
        await update.message.reply_chat_action('typing')
        
        # Detect content type and show appropriate message
        content_type, _ = self.content_generator.detect_content_type(prompt)
        
        if content_type == 'image':
            await update.message.reply_text("🎨 Генерирую изображение... Это может занять ~30 секунд.")
        elif content_type == 'video':
            await update.message.reply_text("🎬 Обрабатываю запрос на видео...")
        else:
            await update.message.reply_text("✍️ Генерирую текст...")
        
        # Generate content
        result = self.content_generator.generate_content(prompt, user_id)
        
        if result['success']:
            if result['type'] == 'image':
                await update.message.reply_photo(
                    photo=result['url'],
                    caption=f"🎨 Изображение создано!\nМодель: {result['model']}"
                )
            elif result['type'] == 'video':
                await update.message.reply_text(result['content'])
            else:
                await update.message.reply_text(
                    f"✅ Контент создан!\nМодель: {result['model']}\n\n{result['content']}"
                )
        else:
            await update.message.reply_text(
                f"❌ Ошибка генерации: {result.get('error', 'Неизвестная ошибка')}"
            )
    
    async def show_content_menu(self, query):
        """Show content generation menu"""
        keyboard = [
            [InlineKeyboardButton("✍️ Генерация текста", callback_data="content_text")],
            [InlineKeyboardButton("🎨 Генерация изображений", callback_data="content_image")],
            [InlineKeyboardButton("🎬 Генерация видео", callback_data="content_video")],
            [InlineKeyboardButton("📜 История генераций", callback_data="content_history")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
        
        text = """🎨 Генерация контента

Выберите тип контента для генерации:

✍️ Текст - статьи, посты, описания
🎨 Изображения - картинки по описанию
🎬 Видео - анимация и видеоролики (скоро)

Или используйте команду:
/generate <описание>"""
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_model_settings(self, query):
        """Show GPT model settings for admins"""
        user_id = query.from_user.id
        
        if not self.admin_manager.is_admin(user_id):
            await query.answer("❌ Только для админов", show_alert=True)
            return
        
        current_model = self.content_generator.get_active_model()
        
        keyboard = [
            [InlineKeyboardButton(
                f"{'✅ ' if current_model == 'gpt-4o-mini' else ''}GPT-4o Mini (быстрая)", 
                callback_data="model_gpt-4o-mini"
            )],
            [InlineKeyboardButton(
                f"{'✅ ' if current_model == 'gpt-4o' else ''}GPT-4o (оптимальная)", 
                callback_data="model_gpt-4o"
            )],
            [InlineKeyboardButton(
                f"{'✅ ' if current_model == 'gpt-4-turbo' else ''}GPT-4 Turbo", 
                callback_data="model_gpt-4-turbo"
            )],
            [InlineKeyboardButton(
                f"{'✅ ' if current_model == 'gpt-4' else ''}GPT-4 (лучшее качество)", 
                callback_data="model_gpt-4"
            )],
            [InlineKeyboardButton(
                f"{'✅ ' if current_model == 'gpt-3.5-turbo' else ''}GPT-3.5 Turbo (бюджетная)", 
                callback_data="model_gpt-3.5-turbo"
            )],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin")]
        ]
        
        text = f"""⚙️ Настройки GPT модели

Текущая модель: {current_model}

📊 Сравнение моделей:

GPT-4o Mini ⚡
• Самая быстрая
• Дешевая
• Хорошо для простых задач

GPT-4o 🎯
• Оптимальная
• Баланс скорости и качества
• Рекомендуется для большинства

GPT-4 Turbo ⚡
• Быстрее GPT-4
• Хорошее качество

GPT-4 🌟
• Лучшее качество
• Медленнее
• Дороже

GPT-3.5 Turbo 💰
• Самая дешевая
• Базовое качество
• Быстрая"""
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_model_change(self, query, model: str):
        """Handle model change request"""
        user_id = query.from_user.id
        
        if not self.admin_manager.is_admin(user_id):
            await query.answer("❌ Только для админов", show_alert=True)
            return
        
        success = self.content_generator.set_active_model(model, user_id)
        
        if success:
            await query.answer(f"✅ Модель изменена на {model}", show_alert=True)
            # Refresh the settings menu
            await self.show_model_settings(query)
        else:
            await query.answer("❌ Ошибка при смене модели", show_alert=True)
    
    async def show_generation_history(self, query):
        """Show content generation history"""
        user_id = query.from_user.id
        
        history = self.content_generator.get_generation_history(user_id, limit=10)
        
        if not history:
            text = "📜 История генераций пуста"
        else:
            text = "📜 История генераций (последние 10):\n\n"
            
            for i, row in enumerate(history, 1):
                gen_id, request, content_type, status, model, created = row
                
                status_emoji = {
                    'completed': '✅',
                    'processing': '⏳',
                    'failed': '❌',
                    'pending': '⏸'
                }.get(status, '❓')
                
                type_emoji = {
                    'text': '✍️',
                    'image': '🎨',
                    'video': '🎬'
                }.get(content_type, '📄')
                
                request_short = request[:30] + '...' if len(request) > 30 else request
                text += f"{i}. {type_emoji} {status_emoji} {request_short}\n"
                text += f"   ID: {gen_id} | {created[:16]}\n\n"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="content_menu")]]
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_content_type_info(self, query, content_type: str):
        """Show information about specific content type"""
        if content_type == 'text':
            text = """✍️ Генерация текста

Примеры запросов:
• Напиши статью про искусственный интеллект
• Создай описание товара для интернет-магазина
• Сочини короткую историю про космос
• Напиши пост для соцсетей про кафе

Просто отправь свой запрос с /generate или напиши мне напрямую, и я автоматически определю, что нужно создать текст!"""
        
        elif content_type == 'image':
            text = """🎨 Генерация изображений

Модель: DALL-E 3
Размер: 1024x1024px

Примеры запросов:
• Создай изображение футуристического города
• Нарисуй логотип для кофейни
• Сгенерируй картинку космического корабля
• Изобрази закат на океане в стиле импрессионизма

💡 Совет: Чем детальнее описание, тем лучше результат!

⏱ Генерация занимает ~30 секунд"""
        
        elif content_type == 'video':
            text = """🎬 Генерация видео

🚧 В разработке

Планируемые возможности:
• Создание коротких анимаций
• Генерация видео из текста
• Анимация изображений
• Создание презентационных роликов

Интеграция с:
• RunwayML Gen-2
• Pika Labs
• Stable Video Diffusion

📅 Ожидается в следующих версиях!"""
        
        else:
            text = "❓ Неизвестный тип контента"
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="content_menu")]]
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
