#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Assistant Bot v4.6 - Final Production
Telegram бот с RAG, автообучением и векторным поиском
"""

import os
import sys
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import base64
import re

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
    sys.exit(1)

# Настройки
CONFIG_PATH = 'config.json'
DB_PATH = 'knowledge.db'

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

VERSION = "4.6"


class AdminManager:
    """Управление администраторами"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def add_admin(self, user_id: int, username: str = "", full_name: str = "", added_by: int = 0) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO admins 
                (user_id, username, full_name, added_by, can_teach, can_import, can_manage_admins, is_active)
                VALUES (?, ?, ?, ?, 1, 1, 1, 1)
            ''', (user_id, username, full_name, added_by))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка add_admin: {e}")
            return False
    
    def is_admin(self, user_id: int) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM admins WHERE user_id = ? AND is_active = 1', (user_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except:
            return False
    
    def list_admins(self) -> List[Tuple]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, username, full_name FROM admins WHERE is_active = 1')
            admins = cursor.fetchall()
            conn.close()
            return admins
        except:
            return []


class CredentialManager:
    """Управление учётками"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def save(self, user_id: int, service: str, login: str, password: str) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO admin_credentials
                (user_id, service, login, password)
                VALUES (?, ?, ?, ?)
            ''', (user_id, service, login, password))
            conn.commit()
            conn.close()
            return True
        except:
            return False
    
    def get(self, user_id: int, service: str = None) -> List[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if service:
                cursor.execute('SELECT service, login, password FROM admin_credentials WHERE user_id = ? AND service = ?', (user_id, service))
            else:
                cursor.execute('SELECT service, login, password FROM admin_credentials WHERE user_id = ?', (user_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [{'service': r[0], 'login': r[1], 'password': r[2]} for r in rows]
        except:
            return []


class KnowledgeBase:
    """База знаний с векторным поиском"""
    
    def __init__(self, db_path: str, embedding_service: EmbeddingService, vector_store: VectorStore):
        self.db_path = db_path
        self.embedding_service = embedding_service
        self.vector_store = vector_store
    
    def add(self, question: str, answer: str, category: str = 'general',
            tags: str = '', source: str = 'manual', added_by: int = 0) -> int:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO knowledge 
                (question, answer, category, tags, source, added_by, is_current)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (question, answer, category, tags, source, added_by))
            
            kb_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Векторизация
            combined = self.embedding_service.combine_qa(question, answer)
            vector = self.embedding_service.embed(combined)
            self.vector_store.upsert(kb_id, vector, {'category': category})
            self.vector_store.save()
            
            logger.info(f"Добавлено: kb_id={kb_id}")
            return kb_id
        except Exception as e:
            logger.error(f"Ошибка add: {e}")
            return 0
    
    def add_info_only(self, info: str, gpt_model: str = 'gpt-4o-mini', added_by: int = 0) -> int:
        """Добавление информации с автогенерацией вопроса"""
        try:
            prompt = f"""Из текста сформулируй короткий вопрос (3-10 слов):

{info}

Только вопрос, без лишнего."""

            response = openai.ChatCompletion.create(
                model=gpt_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=50
            )
            
            question = response['choices'][0]['message']['content'].strip()
            
            if not question or len(question) < 3:
                question = "Информация"
            
            kb_id = self.add(question, info, source='auto_learn', added_by=added_by)
            return kb_id
            
        except Exception as e:
            logger.error(f"Ошибка add_info_only: {e}")
            return self.add("Информация", info, source='auto_learn', added_by=added_by)
    
    def vector_search(self, query: str, top_k: int = 5, min_score: float = 0.5) -> List[Dict]:
        try:
            query_vector = self.embedding_service.embed(query)
            results = self.vector_store.search(query_vector, top_k=top_k, min_score=min_score)
            
            if not results:
                return []
            
            kb_ids = [r['kb_id'] for r in results]
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            placeholders = ','.join(['?'] * len(kb_ids))
            cursor.execute(f'SELECT id, question, answer FROM knowledge WHERE id IN ({placeholders}) AND is_current = 1', kb_ids)
            rows = cursor.fetchall()
            conn.close()
            
            kb_dict = {row[0]: {'id': row[0], 'question': row[1], 'answer': row[2]} for row in rows}
            
            enriched = []
            for r in results:
                if r['kb_id'] in kb_dict:
                    rec = kb_dict[r['kb_id']]
                    rec['score'] = r['score']
                    enriched.append(rec)
            
            enriched.sort(key=lambda x: x['score'], reverse=True)
            return enriched
        except Exception as e:
            logger.error(f"Ошибка vector_search: {e}")
            return []
    
    def count(self) -> int:
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
    """RAG ответчик"""
    
    def __init__(self, knowledge_base: KnowledgeBase, gpt_model: str = 'gpt-4o-mini'):
        self.kb = knowledge_base
        self.gpt_model = gpt_model
    
    def answer_question(self, question: str) -> Tuple[str, float, List[Dict], str]:
        """Ответ с RAG + fallback. Возвращает (answer, confidence, results, source_type)"""
        
        # Векторный поиск
        search_results = self.kb.vector_search(question, top_k=5, min_score=0.5)
        
        # Если нашли - используем RAG
        if search_results and search_results[0]['score'] >= 0.65:
            context = self._build_context(search_results[:3])
            confidence = search_results[0]['score']
            answer = self._generate_rag_answer(question, context, search_results)
            return answer, confidence, search_results, "knowledge_base"
        
        # Fallback на GPT
        try:
            response = openai.ChatCompletion.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": "Ты - помощник компьютерного клуба. Отвечай кратко."},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=300
            )
            answer = response['choices'][0]['message']['content'].strip()
            return answer, 0.3, [], "gpt"
        except Exception as e:
            logger.error(f"GPT error: {e}")
            return "Не могу ответить.", 0.0, [], "none"
    
    def _build_context(self, results: List[Dict]) -> str:
        parts = []
        for r in results:
            answer = r['answer'][:500] + ("..." if len(r['answer']) > 500 else "")
            parts.append(f"[{r['id']}] {r['question']}\n{answer}")
        return "\n\n".join(parts)
    
    def _generate_rag_answer(self, question: str, context: str, results: List[Dict]) -> str:
        try:
            prompt = f"""Ответь на вопрос используя контекст.

Вопрос: {question}

Контекст:
{context}

Ответь кратко. В конце укажи источники."""

            response = openai.ChatCompletion.create(
                model=self.gpt_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=400
            )
            
            answer = response['choices'][0]['message']['content'].strip()
            
            if '[' not in answer:
                sources = ', '.join([f"[{r['id']}]" for r in results[:3]])
                answer += f"\n\nИсточники: {sources}"
            
            return answer
        except:
            return f"{results[0]['answer'][:300]}\n\nИсточник: [{results[0]['id']}]"


class AutoLearner:
    """Автоматическое обучение из сообщений"""
    
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
    
    def should_learn(self, text: str) -> bool:
        """Проверка: нужно ли запоминать это сообщение"""
        # Игнорируем короткие
        if len(text) < 20:
            return False
        
        # Игнорируем команды
        if text.startswith('/'):
            return False
        
        # Игнорируем вопросы
        if text.strip().endswith('?'):
            return False
        
        # Ключевые слова клуба
        keywords = ['клуб', 'компьютер', 'игр', 'час', 'цена', 'стоимость', 'адрес', 'телефон', 
                   'время', 'работа', 'запись', 'парковка', 'оплата', 'карта', 'cls', 'биос', 'bios']
        
        text_lower = text.lower()
        
        # Если есть ключевые слова
        for keyword in keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def learn_from_message(self, text: str, user_id: int) -> Optional[int]:
        """Обучение из сообщения"""
        try:
            if not self.should_learn(text):
                return None
            
            # Добавляем в базу
            kb_id = self.kb.add_info_only(text, added_by=user_id)
            
            logger.info(f"Auto-learned from message: {text[:50]}... [ID: {kb_id}]")
            return kb_id
            
        except Exception as e:
            logger.error(f"Auto-learn error: {e}")
            return None


class ClubAssistantBot:
    """Главный класс бота v4.6"""
    
    def __init__(self, config: dict):
        self.config = config
        
        logger.info("🚀 Инициализация v4.6...")
        
        self.embedding_service = EmbeddingService(config['openai_api_key'])
        self.vector_store = VectorStore()
        self.vector_store.load()
        
        self.admin_manager = AdminManager(DB_PATH)
        self.creds_manager = CredentialManager(DB_PATH)
        self.kb = KnowledgeBase(DB_PATH, self.embedding_service, self.vector_store)
        self.draft_queue = DraftQueue(DB_PATH)
        self.rag = RAGAnswerer(self.kb, config.get('gpt_model', 'gpt-4o-mini'))
        self.auto_learner = AutoLearner(self.kb)
        
        openai.api_key = config['openai_api_key']
        
        self.bot_username = None
        
        logger.info(f"✅ Бот v{VERSION} готов!")
        logger.info(f"   Векторов: {self.vector_store.stats()['total_vectors']}")
        logger.info(f"   Записей: {self.kb.count()}")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_admin = self.admin_manager.is_admin(user.id)
        
        text = f"""👋 Привет, {user.first_name}!

Я ассистент клуба v{VERSION} с автообучением.

💬 В личке: просто спрашивай
💬 В группе: упомяни @{self.bot_username or 'bot'}

Команды: /help"""

        if is_admin:
            text += "\n\n🔧 Админ: /admin"
        
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_admin = self.admin_manager.is_admin(update.effective_user.id)
        
        text = f"""📖 Помощь v{VERSION}

🤖 Автообучение включено!
Бот запоминает всё что связано с клубом.

💬 В личке: просто спрашивай
💬 В группе: @{self.bot_username or 'bot'} вопрос

Команды:
/start - приветствие
/stats - статистика
/help - справка"""

        if is_admin:
            text += """\n\n🔧 Админ:
/admin - панель
/learn <инфо> - добавить
/import - файл
/approveall - принять все черновики
/addadmin <id>
/admins
/savecreds <сервис> <логин> <пароль>
/getcreds
/update - обновить"""

        await update.message.reply_text(text)
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        kb_count = self.kb.count()
        vector_stats = self.vector_store.stats()
        draft_stats = self.draft_queue.stats()
        
        text = f"""📊 Статистика v{VERSION}

📚 База знаний:
• Записей: {kb_count}
• Векторов: {vector_stats['total_vectors']}

📝 Черновики (старые):
• Ожидают: {draft_stats.get('pending', 0)}

🤖 Автообучение: ВКЛ"""

        await update.message.reply_text(text)
    
    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        pending = self.draft_queue.stats().get('pending', 0)
        
        text = f"""🔧 Админ-панель v{VERSION}

🤖 Автообучение: ВКЛ
Бот автоматически запоминает всё о клубе!

/learn <информация> - добавить вручную
/import - импорт файла
/approveall - принять {pending} черновиков
/addadmin <id>
/admins
/savecreds <сервис> <логин> <пароль>
/getcreds
/update - обновить из GitHub"""

        await update.message.reply_text(text)
    
    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        text = update.message.text.replace('/learn', '').strip()
        
        if not text or len(text) < 10:
            await update.message.reply_text("Напиши информацию после /learn")
            return
        
        try:
            kb_id = self.kb.add_info_only(text, added_by=update.effective_user.id)
            await update.message.reply_text(f"✅ Добавлено [ID: {kb_id}]")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_approveall(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принять все черновики сразу"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        await update.message.reply_text("⏳ Принимаю все черновики...")
        
        try:
            drafts = self.draft_queue.get_pending(limit=10000)
            
            if not drafts:
                await update.message.reply_text("✅ Нет черновиков")
                return
            
            approved = 0
            
            for draft in drafts:
                try:
                    kb_id = self.kb.add(
                        draft['question'], 
                        draft['answer'], 
                        draft['category'], 
                        draft['tags'], 
                        'approved_draft', 
                        update.effective_user.id
                    )
                    self.draft_queue.approve(draft['id'], update.effective_user.id)
                    approved += 1
                    
                    if approved % 50 == 0:
                        await update.message.reply_text(f"⏳ {approved}/{len(drafts)}...")
                        
                except Exception as e:
                    logger.error(f"Approve error: {e}")
            
            await update.message.reply_text(f"✅ Принято: {approved} из {len(drafts)}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_import(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        await update.message.reply_text("📥 Импорт\n\nОтправь .txt файл (каждая строка = инфо)")
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        doc = update.message.document
        
        if not doc.file_name.endswith('.txt'):
            await update.message.reply_text("Только .txt!")
            return
        
        await update.message.reply_text("⏳ Импортирую...")
        
        try:
            file = await context.bot.get_file(doc.file_id)
            content = await file.download_as_bytearray()
            text = content.decode('utf-8')
            
            imported = 0
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 10]
            
            for i, info in enumerate(lines, 1):
                try:
                    if i % 10 == 0:
                        await update.message.reply_text(f"⏳ {i}/{len(lines)}...")
                    
                    self.kb.add_info_only(info, added_by=update.effective_user.id)
                    imported += 1
                except:
                    pass
            
            await update.message.reply_text(f"✅ Импортировано: {imported}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_addadmin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            new_admin_id = int(context.args[0])
            self.admin_manager.add_admin(new_admin_id, added_by=update.effective_user.id)
            await update.message.reply_text(f"✅ Админ: {new_admin_id}")
        except:
            await update.message.reply_text("Использование: /addadmin <user_id>")
    
    async def cmd_admins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        admins = self.admin_manager.list_admins()
        
        if not admins:
            await update.message.reply_text("Нет админов")
            return
        
        text = "👥 Админы:\n\n"
        for user_id, username, full_name in admins:
            text += f"• {user_id}"
            if username:
                text += f" @{username}"
            text += "\n"
        
        await update.message.reply_text(text)
    
    async def cmd_savecreds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            service = context.args[0]
            login = context.args[1]
            password = context.args[2]
            
            self.creds_manager.save(update.effective_user.id, service, login, password)
            await update.message.reply_text(f"✅ Сохранено: {service}")
            await update.message.delete()
        except:
            await update.message.reply_text("Использование: /savecreds <сервис> <логин> <пароль>")
    
    async def cmd_getcreds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        creds = self.creds_manager.get(update.effective_user.id)
        
        if not creds:
            await update.message.reply_text("Нет учёток")
            return
        
        text = "🔑 Учётки:\n\n"
        for c in creds:
            text += f"🔹 {c['service']}\n{c['login']} / {c['password']}\n\n"
        
        await context.bot.send_message(chat_id=update.effective_user.id, text=text)
        
        if update.message.chat.type != 'private':
            await update.message.reply_text("✅ Отправил в личку")
    
    async def cmd_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text("🔄 Обновляю...")
        
        import subprocess
        subprocess.Popen(['bash', '/opt/club_assistant/update.sh'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
    
    def _should_respond(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Проверка: нужно ли отвечать"""
        message = update.message
        
        # В личке - всегда
        if message.chat.type == 'private':
            return True
        
        # Reply на бота
        if message.reply_to_message:
            bot_id = context.bot.id if hasattr(context.bot, 'id') else None
            if bot_id and message.reply_to_message.from_user.id == bot_id:
                return True
        
        # Упомянут бот
        if message.text and self.bot_username:
            if f"@{self.bot_username}" in message.text:
                return True
        
        # Команда
        if message.text and message.text.startswith('/'):
            return True
        
        return False
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений"""
        user = update.effective_user
        message = update.message
        text = message.text.strip()
        
        if len(text) < 3:
            return
        
        # Автообучение (в группах и личке)
        self.auto_learner.learn_from_message(text, user.id)
        
        # Проверяем нужно ли отвечать
        if not self._should_respond(update, context):
            return
        
        # Убираем упоминание
        question = text
        if self.bot_username and f"@{self.bot_username}" in question:
            question = question.replace(f"@{self.bot_username}", "").strip()
        
        await context.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        logger.info(f"Q: {user.username}: {question}")
        
        # RAG ответ
        answer, confidence, results, source_type = self.rag.answer_question(question)
        
        logger.info(f"A: source={source_type}, conf={confidence:.2f}")
        
        # Метка источника
        if source_type == "knowledge_base":
            prefix = "📚 Из базы:\n\n"
        elif source_type == "gpt":
            prefix = "🤖 GPT:\n\n"
        else:
            prefix = ""
        
        await message.reply_text(prefix + answer)
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Фото"""
        if not self._should_respond(update, context):
            return
        
        caption = update.message.caption or "Что на фото?"
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()
            photo_b64 = base64.b64encode(photo_bytes).decode('utf-8')
            
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{photo_b64}"}}
                    ]
                }],
                max_tokens=500
            )
            
            answer = response['choices'][0]['message']['content']
            await update.message.reply_text(f"🤖 Vision:\n\n{answer}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
    
    async def post_init(self, application: Application):
        """Инициализация"""
        bot = await application.bot.get_me()
        self.bot_username = bot.username
        logger.info(f"Bot: @{self.bot_username}")
    
    def run(self):
        """Запуск"""
        app = Application.builder().token(self.config['telegram_token']).build()
        
        app.post_init = self.post_init
        
        # Команды
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("admin", self.cmd_admin))
        app.add_handler(CommandHandler("learn", self.cmd_learn))
        app.add_handler(CommandHandler("approveall", self.cmd_approveall))
        app.add_handler(CommandHandler("import", self.cmd_import))
        app.add_handler(CommandHandler("addadmin", self.cmd_addadmin))
        app.add_handler(CommandHandler("admins", self.cmd_admins))
        app.add_handler(CommandHandler("savecreds", self.cmd_savecreds))
        app.add_handler(CommandHandler("getcreds", self.cmd_getcreds))
        app.add_handler(CommandHandler("update", self.cmd_update))
        
        # Документы
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
        # Фото
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        # Текст
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info(f"🤖 Бот v{VERSION} запущен!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Не найден {CONFIG_PATH}")
        sys.exit(1)
    
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, added_by INTEGER,
        can_teach BOOLEAN DEFAULT 1, can_import BOOLEAN DEFAULT 1, 
        can_manage_admins BOOLEAN DEFAULT 1, is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, answer TEXT NOT NULL,
        category TEXT DEFAULT 'general', tags TEXT DEFAULT '', source TEXT DEFAULT '',
        added_by INTEGER DEFAULT 0, version INTEGER DEFAULT 1, is_current BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge_drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, answer TEXT NOT NULL,
        category TEXT DEFAULT 'general', tags TEXT DEFAULT '', source TEXT DEFAULT '',
        confidence REAL DEFAULT 0.5, added_by INTEGER, reviewed_by INTEGER,
        status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_credentials (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        service TEXT NOT NULL, login TEXT, password TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, service))''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_current ON knowledge(is_current)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_draft_status ON knowledge_drafts(status)')
    
    conn.commit()
    conn.close()


def main():
    print("=" * 60)
    print(f"   Club Assistant Bot v{VERSION}")
    print("   Auto-Learning Final Edition")
    print("=" * 60)
    
    init_database()
    config = load_config()
    
    bot = ClubAssistantBot(config)
    bot.run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n👋 Остановлен")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
