#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Message Summarizer - пересказ сообщений через AI
"""

import logging
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

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize summarizer

        Args:
            openai_api_key: OpenAI API key
        """
        self.api_key = openai_api_key
        self.enabled = OPENAI_AVAILABLE and bool(openai_api_key)

        if self.enabled:
            openai.api_key = self.api_key
            logger.info("✅ Message Summarizer initialized")
        else:
            logger.warning("⚠️ Message Summarizer disabled (no API key or OpenAI not installed)")

    async def summarize_messages(self, messages: List[dict], language: str = 'ru') -> Optional[str]:
        """
        Summarize list of messages using GPT

        Args:
            messages: List of message dicts with 'from', 'text', 'date' keys
            language: Language for summary (default: 'ru')

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

            # Create prompt
            if language == 'ru':
                system_prompt = (
                    "Ты - помощник, который делает краткий пересказ сообщений из чата. "
                    "Выдели основные темы, важные решения и ключевые моменты. "
                    "Пересказ должен быть структурированным и кратким."
                )
                user_prompt = f"Сделай краткий пересказ этих сообщений:\n\n{messages_text}"
            else:
                system_prompt = (
                    "You are an assistant that summarizes chat messages. "
                    "Highlight main topics, important decisions, and key points. "
                    "Summary should be structured and concise."
                )
                user_prompt = f"Summarize these messages:\n\n{messages_text}"

            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",  # Cheap and fast model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )

            summary = response.choices[0].message.content.strip()

            logger.info(f"✅ Summarized {len(messages)} messages")
            return summary

        except Exception as e:
            logger.error(f"❌ Failed to summarize messages: {e}")
            return f"❌ Ошибка при пересказе: {e}"

    def format_summary_response(self, summary: str, message_count: int) -> str:
        """
        Format summary response with header

        Args:
            summary: Summary text
            message_count: Number of messages summarized

        Returns:
            Formatted response
        """
        response = f"📝 Пересказ последних {message_count} сообщений:\n\n"
        response += summary
        response += f"\n\n💬 Обработано сообщений: {message_count}"

        return response
