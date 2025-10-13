#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Assistant Bot v4.2 - RAG Edition
Telegram бот с векторным поиском, RAG и контролируемым обучением
"""

import os
import sys
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import openai

# Импорты v4.0 модулей
try:
    from embeddings import EmbeddingService
    from vector_store import VectorStore
    from draft_queue import DraftQueue
except ImportError:
    print("❌ Не найдены модули v4.0!")
    print("Установите: embeddings.py, vector_store.py, draft_queue.py")
    sys.exit(1)

# Настройки
CONFIG_PATH = 'config.json'
DB_PATH = 'knowledge.db'

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Версия
VERSION = "4.2"


class AdminManager:
    """Управление администраторами"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def add_admin(self, user_id: int, username: str, full_name: str, added_by: int, 
                  can_teach: bool = True, can_import: bool = False, can_manage_admins: bool = False) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO admins 
                (user_id, username, full_name, added_by, can_teach, can_import, can_manage_admins, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ''', (user_id, username, full_name, added_by, can_teach, can_import, can_manage_admins))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка add_admin: {e}")
            return False
    
    def get_admin(self, user_id: int) -> Optional[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM admins WHERE user_id = ? AND is_active = 1', (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'added_by': row[3],
                    'can_teach': bool(row[4]),
                    'can_import': bool(row[5]),
                    'can_manage_admins': bool(row[6]),
                    'is_active': bool(row[7])
                }
            return None
        except:
            return None
    
    def is_admin(self, user_id: int) -> bool:
        return self.get_admin(user_id) is not None


class KnowledgeBase:
    """База знаний с векторным поиском"""
    
    def __init__(self, db_path: str, embedding_service: EmbeddingService, vector_store: VectorStore):
        self.db_path = db_path
        self.embedding_service = embedding_service
        self.vector_store = vector_store
    
    def add(self, question: str, answer: str, category: str = 'general',
            tags: str = '', source: str = 'manual', added_by: int = 0) -> int:
        """Добавление знания с векторизацией"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO knowledge 
                (question, answer, category, tags, source, added_by, is_current, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ''', (question, answer, category, tags, source, added_by))
            
            kb_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Создаём эмбеддинг и добавляем в векторный индекс
            combined = self.embedding_service.combine_qa(question, answer)
            vector = self.embedding_service.embed(combined)
            
            self.vector_store.upsert(kb_id, vector, {
                'category': category,
                'tags': tags,
                'question': question[:100]
            })
            
            self.vector_store.save()
            
            logger.info(f"Знание добавлено: kb_id={kb_id}")
            return kb_id
            
        except Exception as e:
            logger.error(f"Ошибка add: {e}")
            return 0
    
    def get_by_id(self, kb_id: int) -> Optional[Dict]:
        """Получить знание по ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, question, answer, category, tags, source
                FROM knowledge
                WHERE id = ? AND is_current = 1
            ''', (kb_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'question': row[1],
                    'answer': row[2],
                    'category': row[3],
                    'tags': row[4],
                    'source': row[5]
                }
            return None
        except:
            return None
    
    def vector_search(self, query: str, top_k: int = 5, min_score: float = 0.5) -> List[Dict]:
        """Векторный поиск с получением полных записей"""
        try:
            # Создаём эмбеддинг запроса
            query_vector = self.embedding_service.embed(query)
            
            # Поиск в векторном индексе
            results = self.vector_store.search(query_vector, top_k=top_k, min_score=min_score)
            
            if not results:
                return []
            
            # Получаем полные записи из БД
            kb_ids = [r['kb_id'] for r in results]
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            placeholders = ','.join(['?'] * len(kb_ids))
            cursor.execute(f'''
                SELECT id, question, answer, category, tags
                FROM knowledge
                WHERE id IN ({placeholders}) AND is_current = 1
            ''', kb_ids)
            
            rows = cursor.fetchall()
            conn.close()
            
            # Создаём словарь id -> запись
            kb_dict = {row[0]: {
                'id': row[0],
                'question': row[1],
                'answer': row[2],
                'category': row[3],
                'tags': row[4]
            } for row in rows}
            
            # Объединяем с score из векторного поиска
            enriched_results = []
            for r in results:
                kb_id = r['kb_id']
                if kb_id in kb_dict:
                    kb_record = kb_dict[kb_id]
                    kb_record['score'] = r['score']
                    enriched_results.append(kb_record)
            
            # Сортируем по score
            enriched_results.sort(key=lambda x: x['score'], reverse=True)
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Ошибка vector_search: {e}")
            return []
    
    def count(self) -> int:
        """Количество записей"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 1')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except:
            return 0


class RAGAnswerer:
    """RAG (Retrieval-Augmented Generation) ответчик"""
    
    def __init__(self, knowledge_base: KnowledgeBase, gpt_model: str = 'gpt-4o-mini'):
        self.kb = knowledge_base
        self.gpt_model = gpt_model
    
    def build_context(self, search_results: List[Dict], max_results: int = 3) -> str:
        """Построение контекста из результатов поиска"""
        if not search_results:
            return ""
        
        context_parts = []
        
        for i, result in enumerate(search_results[:max_results], 1):
            kb_id = result['id']
            question = result['question']
            answer = result['answer']
            score = result.get('score', 0)
            
            # Ограничиваем длину ответа для контекста
            if len(answer) > 500:
                answer = answer[:500] + "..."
            
            context_parts.append(f"[{kb_id}] (релевантность: {score:.2f})\nВопрос: {question}\nОтвет: {answer}")
        
        return "\n\n".join(context_parts)
    
    def calculate_confidence(self, search_results: List[Dict]) -> float:
        """Расчёт уверенности ответа"""
        if not search_results:
            return 0.0
        
        # Уверенность на основе топового score
        top_score = search_results[0].get('score', 0)
        
        # Бонус если несколько результатов похожи
        if len(search_results) >= 2:
            second_score = search_results[1].get('score', 0)
            if second_score > 0.7:
                top_score = min(top_score + 0.1, 1.0)
        
        return top_score
    
    def generate_answer(self, question: str, context: str, confidence: float) -> str:
        """Генерация ответа с помощью GPT + контекст"""
        try:
            # Промпт для RAG
            system_prompt = """Ты - ассистент компьютерного клуба.

ВАЖНО:
1. Отвечай ТОЛЬКО на основе предоставленного контекста
2. Если в контексте нет ответа - скажи "Не нашёл информации"
3. Всегда указывай источники в формате [ID]
4. Будь кратким (2-4 предложения)
5. Если нужна инструкция - давай пошаговую

Формат ответа:
[Твой ответ]

Источники: [ID1], [ID2]"""

            user_prompt = f"""Вопрос: {question}

Контекст из базы знаний:
{context}

Ответь на вопрос используя контекст."""

            response = openai.ChatCompletion.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Низкая креативность для точности
                max_tokens=500
            )
            
            answer = response['choices'][0]['message']['content'].strip()
            
            # Добавляем предупреждение если низкая уверенность
            if confidence < 0.7:
                answer += "\n\n⚠️ Ответ требует проверки (низкая уверенность)"
            
            return answer
            
        except Exception as e:
            logger.error(f"Ошибка generate_answer: {e}")
            return f"Ошибка генерации ответа: {str(e)}"
    
    def answer_question(self, question: str, min_confidence: float = 0.5) -> Tuple[str, float, List[Dict]]:
        """Полный цикл RAG: поиск + генерация + оценка"""
        # 1. Векторный поиск
        search_results = self.kb.vector_search(question, top_k=5, min_score=min_confidence)
        
        # 2. Если ничего не нашли
        if not search_results:
            return "Не нашёл информации по этому вопросу. Попробуй переформулировать или уточнить.", 0.0, []
        
        # 3. Строим контекст
        context = self.build_context(search_results, max_results=3)
        
        # 4. Оцениваем уверенность
        confidence = self.calculate_confidence(search_results)
        
        # 5. Генерируем ответ
        answer = self.generate_answer(question, context, confidence)
        
        return answer, confidence, search_results


class ClubAssistantBot:
    """Главный класс бота v4.2"""
    
    def __init__(self, config: dict):
        self.config = config
        
        # Инициализация v4.0 компонентов
        logger.info("🚀 Инициализация v4.0 компонентов...")
        
        self.embedding_service = EmbeddingService(config['openai_api_key'])
        self.vector_store = VectorStore()
        self.vector_store.load()
        
        self.admin_manager = AdminManager(DB_PATH)
        self.kb = KnowledgeBase(DB_PATH, self.embedding_service, self.vector_store)
        self.draft_queue = DraftQueue(DB_PATH)
        self.rag = RAGAnswerer(self.kb, config.get('gpt_model', 'gpt-4o-mini'))
        
        # API ключ
        openai.api_key = config['openai_api_key']
        
        # Конфиг RAG
        self.confidence_threshold = config.get('draft_queue', {}).get('confidence_threshold', 0.7)
        self.auto_approve_threshold = config.get('draft_queue', {}).get('auto_approve_threshold', 0.9)
        
        logger.info(f"✅ Бот v{VERSION} инициализирован")
        logger.info(f"   Векторов в индексе: {self.vector_store.stats()['total_vectors']}")
        logger.info(f"   Записей в KB: {self.kb.count()}")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        is_admin = self.admin_manager.is_admin(user.id)
        
        welcome = f"""👋 Привет, {user.first_name}!

Я ассистент клуба v{VERSION} с RAG-архитектурой.

💬 Просто задай вопрос - я найду ответ в базе знаний и приведу источники.

Команды:
/help - помощь
/stats - статистика"""

        if is_admin:
            welcome += "\n\n🔧 Админ-команды:\n/review - очередь на ревью\n/vectorstats - статистика индекса"
        
        await update.message.reply_text(welcome)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        user_id = update.effective_user.id
        is_admin = self.admin_manager.is_admin(user_id)
        
        help_text = f"""📖 Помощь - Club Assistant v{VERSION}

🤖 Как работает:
Я использую RAG (Retrieval-Augmented Generation):
1. Векторный поиск по базе знаний
2. Формирую контекст из релевантных записей
3. GPT генерирует ответ с указанием источников [ID]

💬 Просто спрашивай:
• Как обновить биос?
• Где находится клуб?
• Что такое CLS?

📊 Команды:
/start - приветствие
/stats - статистика базы
/help - эта справка"""

        if is_admin:
            help_text += """

🔧 Админ-команды:
/review - просмотр черновиков на одобрение
/vectorstats - статистика векторного индекса
/learn <вопрос> | <ответ> - добавить знание
/reindex - переиндексация (если нужно)"""

        await update.message.reply_text(help_text)
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика"""
        kb_count = self.kb.count()
        vector_stats = self.vector_store.stats()
        draft_stats = self.draft_queue.stats()
        
        stats_text = f"""📊 Статистика v{VERSION}

📚 База знаний:
• Записей: {kb_count}
• Векторов: {vector_stats['total_vectors']}

📝 Черновики:
• Ожидают: {draft_stats.get('pending', 0)}
• Одобрено: {draft_stats.get('approved', 0)}
• Отклонено: {draft_stats.get('rejected', 0)}"""

        if draft_stats.get('pending', 0) > 0:
            avg_conf = draft_stats.get('avg_confidence', 0)
            stats_text += f"\n• Средняя уверенность: {avg_conf:.2f}"
        
        await update.message.reply_text(stats_text)
    
    async def cmd_vectorstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика векторного индекса (админ)"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        stats = self.vector_store.stats()
        
        stats_text = f"""🔍 Векторный индекс

Размерность: {stats['dimension']}D
Всего векторов: {stats['total_vectors']}
Метаданных: {stats['metadata_count']}

База знаний: {self.kb.count()} записей"""

        await update.message.reply_text(stats_text)
    
    async def cmd_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Просмотр черновиков (админ)"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        # Получаем черновики
        drafts = self.draft_queue.get_pending(limit=1)
        
        if not drafts:
            await update.message.reply_text("✅ Нет черновиков на ревью!")
            return
        
        draft = drafts[0]
        
        # Формируем сообщение
        review_text = f"""📝 Черновик #{draft['id']}
Уверенность: {draft['confidence']:.2f}

❓ Вопрос:
{draft['question']}

💬 Ответ:
{draft['answer'][:500]}{"..." if len(draft['answer']) > 500 else ""}

📂 Категория: {draft['category']}
🏷 Теги: {draft['tags']}
📌 Источник: {draft['source']}"""

        # Кнопки
        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{draft['id']}"),
                InlineKeyboardButton("✏️ Править", callback_data=f"edit_{draft['id']}")
            ],
            [
                InlineKeyboardButton("🗑 Удалить", callback_data=f"reject_{draft['id']}"),
                InlineKeyboardButton("⏭ Пропустить", callback_data="review_next")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(review_text, reply_markup=reply_markup)
    
    async def handle_review_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопок ревью"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        if not self.admin_manager.is_admin(user_id):
            await query.edit_message_text("❌ Только для админов")
            return
        
        data = query.data
        
        if data.startswith("approve_"):
            draft_id = int(data.split("_")[1])
            
            # Получаем черновик
            draft = self.draft_queue.get_draft(draft_id)
            if not draft:
                await query.edit_message_text("❌ Черновик не найден")
                return
            
            # Добавляем в базу
            kb_id = self.kb.add(
                question=draft['question'],
                answer=draft['answer'],
                category=draft['category'],
                tags=draft['tags'],
                source='approved_draft',
                added_by=user_id
            )
            
            # Одобряем черновик
            self.draft_queue.approve(draft_id, user_id)
            
            await query.edit_message_text(f"✅ Одобрено! Добавлено в базу [ID: {kb_id}]")
        
        elif data.startswith("reject_"):
            draft_id = int(data.split("_")[1])
            self.draft_queue.reject(draft_id, user_id)
            await query.edit_message_text("🗑 Отклонено")
        
        elif data == "review_next":
            # Показываем следующий
            await query.edit_message_text("⏭ Пропущено")
            # Эмулируем /review
            drafts = self.draft_queue.get_pending(limit=1)
            if drafts:
                # Отправляем новое сообщение (не можем edit с кнопками)
                pass
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка вопросов пользователя"""
        user = update.effective_user
        question = update.message.text.strip()
        
        if not question or len(question) < 3:
            await update.message.reply_text("Задай вопрос подлиннее 🙂")
            return
        
        # Показываем typing...
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        logger.info(f"Вопрос от {user.username}: {question}")
        
        # RAG ответ
        answer, confidence, search_results = self.rag.answer_question(question, min_confidence=0.5)
        
        logger.info(f"Confidence: {confidence:.2f}, Results: {len(search_results)}")
        
        # Если низкая уверенность - добавляем в drafts
        if 0 < confidence < self.confidence_threshold and search_results:
            # Создаём черновик для будущего улучшения
            self.draft_queue.add_draft(
                question=question,
                answer=answer,
                confidence=confidence,
                source='low_confidence_query',
                added_by=user.id
            )
            logger.info(f"Добавлен в drafts (conf={confidence:.2f})")
        
        # Отправляем ответ
        await update.message.reply_text(answer)
    
    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ручное добавление знания (админ)"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        # Парсим /learn вопрос | ответ
        text = update.message.text
        if '|' not in text:
            await update.message.reply_text("Формат: /learn вопрос | ответ")
            return
        
        parts = text.split('|', 1)
        question = parts[0].replace('/learn', '').strip()
        answer = parts[1].strip()
        
        if not question or not answer:
            await update.message.reply_text("❌ Вопрос и ответ не могут быть пустыми")
            return
        
        # Добавляем в базу
        kb_id = self.kb.add(
            question=question,
            answer=answer,
            source='manual',
            added_by=update.effective_user.id
        )
        
        await update.message.reply_text(f"✅ Добавлено в базу [ID: {kb_id}]")
    
    def run(self):
        """Запуск бота"""
        application = Application.builder().token(self.config['telegram_token']).build()
        
        # Команды
        application.add_handler(CommandHandler("start", self.cmd_start))
        application.add_handler(CommandHandler("help", self.cmd_help))
        application.add_handler(CommandHandler("stats", self.cmd_stats))
        application.add_handler(CommandHandler("vectorstats", self.cmd_vectorstats))
        application.add_handler(CommandHandler("review", self.cmd_review))
        application.add_handler(CommandHandler("learn", self.cmd_learn))
        
        # Callback для кнопок
        application.add_handler(CallbackQueryHandler(self.handle_review_callback))
        
        # Сообщения
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Запуск
        logger.info(f"🤖 Бот v{VERSION} запущен!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def load_config():
    """Загрузка конфигурации"""
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Не найден {CONFIG_PATH}")
        sys.exit(1)
    
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица admins
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            added_by INTEGER,
            can_teach BOOLEAN DEFAULT 1,
            can_import BOOLEAN DEFAULT 0,
            can_manage_admins BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица knowledge
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            tags TEXT DEFAULT '',
            source TEXT DEFAULT '',
            added_by INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            is_current BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица knowledge_drafts (v4.0)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            tags TEXT DEFAULT '',
            source TEXT DEFAULT '',
            confidence REAL DEFAULT 0.5,
            added_by INTEGER,
            reviewed_by INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP
        )
    ''')
    
    # Индексы
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_current ON knowledge(is_current)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_draft_status ON knowledge_drafts(status)')
    
    conn.commit()
    conn.close()


def main():
    """Главная функция"""
    print("=" * 60)
    print(f"   Club Assistant Bot v{VERSION}")
    print("   RAG Edition with Vector Search")
    print("=" * 60)
    print()
    
    # Инициализация БД
    logger.info("Инициализация базы данных...")
    init_database()
    
    # Загрузка конфига
    logger.info("Загрузка конфигурации...")
    config = load_config()
    
    # Проверка модулей v4.0
    try:
        from embeddings import EmbeddingService
        from vector_store import VectorStore
        from draft_queue import DraftQueue
        logger.info("✅ Модули v4.0 найдены")
    except ImportError:
        logger.error("❌ Модули v4.0 не найдены!")
        logger.error("Установите: embeddings.py, vector_store.py, draft_queue.py")
        sys.exit(1)
    
    # Запуск бота
    bot = ClubAssistantBot(config)
    bot.run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n👋 Бот остановлен")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
