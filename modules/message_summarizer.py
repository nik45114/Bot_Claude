#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Message Summarizer - пересказ сообщений через AI
"""

import logging
import sqlite3
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI not available, summarizer will not work")


class MessageSummarizer:
    """Summarize chat messages using AI"""

    MAX_MESSAGES = 1000  # Maximum messages to store per chat

    def __init__(self, openai_api_key: Optional[str] = None, db_path: str = 'knowledge.db'):
        """
        Initialize summarizer

        Args:
            openai_api_key: OpenAI API key
            db_path: Path to SQLite database
        """
        self.api_key = openai_api_key
        self.db_path = db_path
        self.enabled = OPENAI_AVAILABLE and bool(openai_api_key)

        if self.enabled:
            openai.api_key = self.api_key
            logger.info("✅ Message Summarizer initialized")
        else:
            logger.warning("⚠️ Message Summarizer disabled (no API key or OpenAI not installed)")

    async def summarize_messages(self, messages: List[dict], language: str = 'ru', mode: Optional[str] = None) -> Optional[str]:
        """
        Summarize list of messages using GPT

        Args:
            messages: List of message dicts with 'from', 'text', 'date' keys
            language: Language for summary (default: 'ru')
            mode: Summary mode - None (normal), 'q' (quick/brief), 'a' (amusing/humorous), 's' (standup)

        Returns:
            Summary text or None if failed
        """
        if not self.enabled:
            return "❌ Пересказ недоступен: OpenAI не настроен"

        if not messages:
            return "❌ Нет сообщений для пересказа"

        try:
            # Format messages for AI
            formatted_messages = []
            for msg in messages:
                from_user = msg.get('from', 'Unknown')
                text = msg.get('text', '')
                date_str = msg.get('date', '')

                if text:
                    formatted_messages.append(f"[{date_str}] {from_user}: {text}")

            if not formatted_messages:
                return "❌ Все сообщения пустые"

            messages_text = "\n".join(formatted_messages)

            # Create prompt based on mode
            if language == 'ru':
                if mode == 'q':
                    # Quick mode - like "Previously on..." in TV series
                    system_prompt = (
                        "Ты - помощник, который делает ОЧЕНЬ КРАТКИЙ пересказ сообщений из чата, "
                        "как в заставке сериала 'В предыдущей серии...'. "
                        "Максимум 3-5 предложений. Только самое важное и интересное. "
                        "Начни с фразы '📺 В предыдущих сообщениях:'"
                    )
                    user_prompt = f"Сделай краткий пересказ:\n\n{messages_text}"
                    max_tokens = 300
                    temperature = 0.4
                elif mode == 'a':
                    # Amusing mode - with humor
                    system_prompt = (
                        "Ты - веселый помощник, который пересказывает сообщения из чата С ЮМОРОМ. "
                        "Добавляй шутки, смешные комментарии и эмодзи. "
                        "Сохраняй все важные факты, но подавай их весело и интересно. "
                        "Пиши как стендап-комик, который комментирует чужую переписку. "
                        "Начни с фразы '🎭 Что тут у нас было:'"
                    )
                    user_prompt = f"Перескажи эти сообщения с юмором:\n\n{messages_text}"
                    max_tokens = 600
                    temperature = 0.7
                elif mode == 's':
                    # Standup mode - as a standup performance
                    system_prompt = (
                        "Ты - профессиональный стендап-комик на сцене. "
                        "Перескажи эти сообщения КАК СВОЁ ВЫСТУПЛЕНИЕ на стендапе. "
                        "Обращайся к зрителям, делай паузы, используй типичные приёмы стендапа: "
                        "наблюдения, преувеличения, неожиданные повороты, callbacks. "
                        "Используй эмодзи для передачи эмоций и пауз. "
                        "Начни как на реальном выступлении: '🎤 Доброго времени суток! Вот представьте себе...'"
                    )
                    user_prompt = f"Сделай стендап-выступление про эти сообщения:\n\n{messages_text}"
                    max_tokens = 700
                    temperature = 0.8
                else:
                    # Normal mode
                    system_prompt = (
                        "Ты - помощник, который делает краткий пересказ сообщений из чата. "
                        "Выдели основные темы, важные решения и ключевые моменты. "
                        "Пересказ должен быть структурированным и кратким."
                    )
                    user_prompt = f"Сделай краткий пересказ этих сообщений:\n\n{messages_text}"
                    max_tokens = 500
                    temperature = 0.3
            else:
                # English mode (basic support)
                if mode == 'q':
                    system_prompt = (
                        "You are an assistant that creates VERY BRIEF summaries of chat messages, "
                        "like 'Previously on...' in TV series. Maximum 3-5 sentences. "
                        "Only the most important and interesting points."
                    )
                    max_tokens = 300
                    temperature = 0.4
                elif mode == 'a':
                    system_prompt = (
                        "You are a funny assistant that summarizes chat messages WITH HUMOR. "
                        "Add jokes, funny comments and emojis. Keep all important facts but present them in an entertaining way."
                    )
                    max_tokens = 600
                    temperature = 0.7
                elif mode == 's':
                    system_prompt = (
                        "You are a professional standup comedian on stage. "
                        "Retell these messages AS YOUR STANDUP PERFORMANCE. "
                        "Address the audience, use typical standup techniques: observations, exaggerations, unexpected turns, callbacks. "
                        "Use emojis for emotions and pauses. Start like a real performance."
                    )
                    max_tokens = 700
                    temperature = 0.8
                else:
                    system_prompt = (
                        "You are an assistant that summarizes chat messages. "
                        "Highlight main topics, important decisions, and key points. "
                        "Summary should be structured and concise."
                    )
                    max_tokens = 500
                    temperature = 0.3
                user_prompt = f"Summarize these messages:\n\n{messages_text}"

            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",  # Cheap and fast model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

            summary = response.choices[0].message.content.strip()

            logger.info(f"✅ Summarized {len(messages)} messages (mode: {mode or 'normal'})")
            return summary

        except Exception as e:
            logger.error(f"❌ Failed to summarize messages: {e}")
            return f"❌ Ошибка при пересказе: {e}"

    def save_message(self, chat_id: int, user_id: int, username: str, full_name: str, message_text: str) -> bool:
        """
        Save message to history and cleanup old messages

        Args:
            chat_id: Chat ID
            user_id: User ID
            username: Username
            full_name: Full name
            message_text: Message text

        Returns:
            True if saved successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Insert new message
            cursor.execute('''
                INSERT INTO message_history (chat_id, user_id, username, full_name, message_text)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, user_id, username, full_name, message_text))

            # Count messages for this chat
            cursor.execute('SELECT COUNT(*) FROM message_history WHERE chat_id = ?', (chat_id,))
            count = cursor.fetchone()[0]

            # If exceeded limit, delete oldest messages
            if count > self.MAX_MESSAGES:
                delete_count = count - self.MAX_MESSAGES
                cursor.execute('''
                    DELETE FROM message_history
                    WHERE id IN (
                        SELECT id FROM message_history
                        WHERE chat_id = ?
                        ORDER BY id ASC
                        LIMIT ?
                    )
                ''', (chat_id, delete_count))
                logger.info(f"🗑️ Deleted {delete_count} old messages from chat {chat_id}")

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save message: {e}")
            return False

    def get_recent_messages(self, chat_id: int, limit: int = 100) -> List[dict]:
        """
        Get recent messages from history

        Args:
            chat_id: Chat ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of message dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT user_id, username, full_name, message_text, message_date
                FROM message_history
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
            ''', (chat_id, limit))

            rows = cursor.fetchall()
            conn.close()

            # Reverse to get chronological order
            messages = []
            for row in reversed(rows):
                messages.append({
                    'from': row['full_name'] or row['username'] or f"User {row['user_id']}",
                    'text': row['message_text'],
                    'date': row['message_date'][:16] if row['message_date'] else ''
                })

            return messages

        except Exception as e:
            logger.error(f"❌ Failed to get messages: {e}")
            return []

    def get_message_count(self, chat_id: int) -> int:
        """
        Get count of stored messages for chat

        Args:
            chat_id: Chat ID

        Returns:
            Number of messages
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM message_history WHERE chat_id = ?', (chat_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"❌ Failed to get message count: {e}")
            return 0

    def format_summary_response(self, summary: str, message_count: int, mode: Optional[str] = None) -> str:
        """
        Format summary response with header

        Args:
            summary: Summary text
            message_count: Number of messages summarized
            mode: Summary mode - None (normal), 'q' (quick), 'a' (amusing), 's' (standup)

        Returns:
            Formatted response
        """
        # Skip header if summary already has special prefix (q, a, or s mode)
        if mode in ['q', 'a', 's'] and (summary.startswith('📺') or summary.startswith('🎭') or summary.startswith('🎤')):
            response = summary
            response += f"\n\n💬 Обработано сообщений: {message_count}"
        else:
            response = f"📝 Пересказ последних {message_count} сообщений:\n\n"
            response += summary
            response += f"\n\n💬 Обработано сообщений: {message_count}"

        return response
