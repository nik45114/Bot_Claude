#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Assistant - Улучшенная RAG-система с обучением на OpenAI
Поддержка индексации документов, истории сообщений, контекста о клубе
"""

import os
import sqlite3
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import openai

logger = logging.getLogger(__name__)


class SmartAssistant:
    """
    Умный ассистент с улучшенной RAG-системой
    - Индексирует .md файлы (инструкции, правила)
    - Использует историю сообщений
    - Контекст о клубе и процедурах
    - Разные промпты для разных типов вопросов
    """

    def __init__(self,
                 kb,  # KnowledgeBase instance
                 embedding_service,  # EmbeddingService instance
                 vector_store,  # VectorStore instance
                 db_path: str,
                 gpt_model: str = 'gpt-4o-mini'):
        """
        Args:
            kb: Экземпляр KnowledgeBase
            embedding_service: Сервис для создания embeddings
            vector_store: Векторное хранилище FAISS
            db_path: Путь к БД
            gpt_model: Модель GPT для ответов
        """
        self.kb = kb
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.db_path = db_path
        self.gpt_model = gpt_model

        # Кэш для документов
        self.documents_cache = {}
        self.documents_indexed = False

        logger.info(f"✅ SmartAssistant initialized with {gpt_model}")

    def index_markdown_files(self, docs_dir: str = '.') -> int:
        """
        Индексировать все .md файлы в векторную БД

        Args:
            docs_dir: Директория с документами

        Returns:
            Количество проиндексированных файлов
        """
        logger.info(f"📚 Indexing .md files from {docs_dir}...")

        indexed_count = 0

        for root, dirs, files in os.walk(docs_dir):
            # Пропускаем venv и скрытые директории
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'venv']

            for file in files:
                if not file.endswith('.md'):
                    continue

                file_path = os.path.join(root, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Пропускаем пустые файлы
                    if len(content.strip()) < 50:
                        continue

                    # Разбиваем большие файлы на чанки
                    chunks = self._split_into_chunks(content, max_length=1000)

                    for i, chunk in enumerate(chunks):
                        # Создаём вопрос-ответ для индексации
                        question = f"Информация из {file} (часть {i+1}/{len(chunks)})"
                        answer = chunk

                        # Добавляем в базу знаний
                        try:
                            self.kb.add(
                                question=question,
                                answer=answer,
                                category='documentation',
                                tags=f"md,doc,{file}",
                                source='auto_index',
                                added_by=0  # system
                            )
                            indexed_count += 1
                        except Exception as e:
                            logger.error(f"❌ Error indexing {file_path}: {e}")

                    logger.info(f"   ✅ Indexed {file} ({len(chunks)} chunks)")

                except Exception as e:
                    logger.error(f"❌ Error reading {file_path}: {e}")

        # Сохраняем векторное хранилище
        self.vector_store.save()
        self.documents_indexed = True

        logger.info(f"✅ Indexed {indexed_count} document chunks")
        return indexed_count

    def _split_into_chunks(self, text: str, max_length: int = 1000) -> List[str]:
        """Разбить текст на чанки для индексации"""
        chunks = []
        lines = text.split('\n')

        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line)

            if current_length + line_length > max_length and current_chunk:
                # Сохраняем текущий чанк
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_length = 0

            current_chunk.append(line)
            current_length += line_length + 1  # +1 для \n

        # Добавляем последний чанк
        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks if chunks else [text]

    def answer_with_context(self,
                          question: str,
                          user_id: Optional[int] = None,
                          chat_history: Optional[List[Dict]] = None,
                          mode: str = 'auto') -> Tuple[str, float, List[Dict], str]:
        """
        Ответить на вопрос с учётом контекста

        Args:
            question: Вопрос пользователя
            user_id: ID пользователя (для персонализации)
            chat_history: История чата (последние N сообщений)
            mode: Режим ответа ('auto', 'strict', 'creative', 'docs')

        Returns:
            (answer, confidence, search_results, source_type)
        """
        # Векторный поиск
        search_results = self.kb.vector_search(question, top_k=5, min_score=0.60)

        # Определяем тип вопроса
        question_type = self._classify_question(question)

        # Выбираем стратегию ответа
        if mode == 'auto':
            if search_results and search_results[0]['score'] >= 0.75:
                # Хорошее совпадение - строгий RAG
                return self._strict_rag_answer(question, search_results)
            elif question_type in ['greeting', 'smalltalk']:
                # Приветствие или светская беседа - GPT без RAG
                return self._casual_answer(question)
            elif question_type == 'procedural':
                # Процедурный вопрос - RAG + GPT
                return self._hybrid_answer(question, search_results, chat_history)
            else:
                # Общий вопрос
                return self._hybrid_answer(question, search_results, chat_history)

        elif mode == 'strict':
            # Только из базы знаний
            return self._strict_rag_answer(question, search_results)

        elif mode == 'creative':
            # GPT с минимальным контекстом
            return self._creative_answer(question, search_results)

        elif mode == 'docs':
            # Только из документации
            doc_results = [r for r in search_results if 'documentation' in r.get('category', '')]
            return self._strict_rag_answer(question, doc_results)

        # Fallback
        return self._hybrid_answer(question, search_results, chat_history)

    def _classify_question(self, question: str) -> str:
        """Классификация типа вопроса"""
        question_lower = question.lower().strip()

        # Приветствия
        greetings = ['привет', 'здравствуй', 'добрый день', 'добрый вечер', 'hi', 'hello']
        if any(g in question_lower for g in greetings):
            return 'greeting'

        # Светская беседа
        smalltalk = ['как дела', 'что делаешь', 'как настроение', 'что нового']
        if any(s in question_lower for s in smalltalk):
            return 'smalltalk'

        # Процедурные вопросы (как сделать)
        procedural = ['как', 'что делать', 'как сделать', 'как закрыть', 'как открыть', 'инструкция']
        if any(p in question_lower for p in procedural):
            return 'procedural'

        # Информационные вопросы
        informational = ['что такое', 'кто такой', 'где находится', 'когда']
        if any(i in question_lower for i in informational):
            return 'informational'

        return 'general'

    def _strict_rag_answer(self, question: str, results: List[Dict]) -> Tuple[str, float, List[Dict], str]:
        """Строгий RAG - только из базы знаний"""
        if not results:
            return "В базе знаний нет информации по этому вопросу.", 0.0, [], "none"

        top = results[0]

        # Если скор слишком низкий
        if top['score'] < 0.60:
            return "В базе знаний нет точной информации по этому вопросу.", top['score'], results, "none"

        # Формируем ответ из топ результатов
        answer_parts = []

        for i, result in enumerate(results[:3], 1):
            if result['score'] < 0.55:
                break

            answer = result['answer']
            if len(answer) > 600:
                answer = answer[:600] + "..."

            if i == 1:
                answer_parts.append(answer)
            else:
                answer_parts.append(f"\n\n📎 Также:\n{answer}")

        final_answer = "".join(answer_parts)

        # Добавляем источники
        sources = ', '.join([f"[{r['id']}]" for r in results[:3]])
        final_answer += f"\n\n📚 Источники: {sources}"

        return final_answer, top['score'], results, "knowledge_base"

    def _casual_answer(self, question: str) -> Tuple[str, float, List[Dict], str]:
        """Непринуждённый ответ (приветствие, светская беседа)"""
        try:
            response = openai.ChatCompletion.create(
                model=self.gpt_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты - дружелюбный помощник компьютерного клуба. "
                            "Отвечай кратко, позитивно и по-дружески. "
                            "Не используй эмодзи без необходимости."
                        )
                    },
                    {"role": "user", "content": question}
                ],
                temperature=0.8,
                max_tokens=150
            )
            answer = response['choices'][0]['message']['content'].strip()
            return answer, 0.5, [], "casual"
        except Exception as e:
            logger.error(f"❌ Casual answer error: {e}")
            return "Привет! Чем могу помочь?", 0.0, [], "fallback"

    def _hybrid_answer(self,
                      question: str,
                      results: List[Dict],
                      chat_history: Optional[List[Dict]] = None) -> Tuple[str, float, List[Dict], str]:
        """Гибридный ответ - RAG + GPT"""

        # Формируем контекст из результатов поиска
        context_parts = []

        if results:
            context_parts.append("Информация из базы знаний:")
            for i, result in enumerate(results[:3], 1):
                context_parts.append(f"\n{i}. {result['answer'][:400]}")

        context = "\n".join(context_parts) if context_parts else "Нет релевантной информации в базе."

        # Формируем историю
        history_text = ""
        if chat_history:
            history_text = "\n\nПоследние сообщения:\n"
            for msg in chat_history[-5:]:
                history_text += f"- {msg.get('from', 'User')}: {msg.get('text', '')[:100]}\n"

        # Системный промпт
        system_prompt = """Ты - умный помощник компьютерного клуба.

Твоя задача:
1. Отвечай на основе предоставленной информации из базы знаний
2. Если в базе нет точного ответа, используй свои знания, но честно укажи это
3. Будь кратким и конкретным
4. Если не знаешь - так и скажи

Правила:
- Не придумывай факты о клубе, которых нет в контексте
- Для процедурных вопросов давай пошаговые инструкции
- Используй профессиональный, но дружелюбный тон"""

        user_prompt = f"""Вопрос: {question}

{context}
{history_text}

Ответь на вопрос, используя предоставленную информацию."""

        try:
            response = openai.ChatCompletion.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            answer = response['choices'][0]['message']['content'].strip()

            # Определяем confidence на основе наличия результатов
            confidence = results[0]['score'] if results else 0.4

            return answer, confidence, results, "hybrid"

        except Exception as e:
            logger.error(f"❌ Hybrid answer error: {e}")

            # Fallback на строгий RAG
            if results:
                return self._strict_rag_answer(question, results)

            return "Не могу ответить на этот вопрос.", 0.0, [], "error"

    def _creative_answer(self, question: str, results: List[Dict]) -> Tuple[str, float, List[Dict], str]:
        """Креативный ответ с минимальным контекстом"""

        # Минимальный контекст
        context = ""
        if results:
            context = f"Контекст: {results[0]['answer'][:200]}"

        system_prompt = """Ты - креативный помощник компьютерного клуба.
Отвечай интересно, с примерами, объясняй понятно.
Можешь использовать аналогии и метафоры."""

        try:
            response = openai.ChatCompletion.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{context}\n\nВопрос: {question}"}
                ],
                temperature=0.7,
                max_tokens=600
            )

            answer = response['choices'][0]['message']['content'].strip()
            return answer, 0.6, results, "creative"

        except Exception as e:
            logger.error(f"❌ Creative answer error: {e}")
            return "Не могу ответить на этот вопрос.", 0.0, [], "error"

    def get_stats(self) -> Dict:
        """Статистика ассистента"""
        return {
            'documents_indexed': self.documents_indexed,
            'vector_store_size': self.vector_store.stats()['total_vectors'],
            'kb_size': self._get_kb_size(),
            'model': self.gpt_model
        }

    def _get_kb_size(self) -> int:
        """Размер базы знаний"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM knowledge')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except:
            return 0


# Пример использования
if __name__ == '__main__':
    print("SmartAssistant module - use via bot.py")
