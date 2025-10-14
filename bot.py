#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Assistant Bot v4.5 - Production Edition
Telegram бот с RAG, векторным поиском и обучением из диалога
"""

import os
import sys
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import base64

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

VERSION = "4.5"


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
    
    def remove_admin(self, user_id: int) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE admins SET is_active = 0 WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True
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
                (user_id, service, login, password, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
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


class DialogMemory:
    """Память диалога для обучения из контекста"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.sessions = {}  # chat_id -> [messages]
    
    def add_message(self, chat_id: int, user_id: int, text: str, is_bot: bool = False):
        """Добавить сообщение в историю"""
        if chat_id not in self.sessions:
            self.sessions[chat_id] = []
        
        self.sessions[chat_id].append({
            'user_id': user_id,
            'text': text,
            'is_bot': is_bot,
            'timestamp': datetime.now()
        })
        
        # Храним только последние 20 сообщений
        if len(self.sessions[chat_id]) > 20:
            self.sessions[chat_id] = self.sessions[chat_id][-20:]
    
    def get_context(self, chat_id: int, limit: int = 10) -> str:
        """Получить контекст диалога"""
        if chat_id not in self.sessions:
            return ""
        
        messages = self.sessions[chat_id][-limit:]
        
        context_parts = []
        for msg in messages:
            prefix = "Бот: " if msg['is_bot'] else "Пользователь: "
            context_parts.append(f"{prefix}{msg['text']}")
        
        return "\n".join(context_parts)


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
            self.vector_store.upsert(kb_id, vector, {'category': category, 'tags': tags})
            self.vector_store.save()
            
            logger.info(f"Добавлено: kb_id={kb_id}")
            return kb_id
        except Exception as e:
            logger.error(f"Ошибка add: {e}")
            return 0
    
    def add_info_only(self, info: str, gpt_model: str = 'gpt-4o-mini', added_by: int = 0) -> int:
        """Добавление информации с автогенерацией вопроса"""
        try:
            prompt = f"""Из этого текста сформулируй короткий вопрос (3-10 слов), на который этот текст отвечает.

Текст:
{info}

Верни только один вопрос, без лишнего."""

            response = openai.ChatCompletion.create(
                model=gpt_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=50
            )
            
            question = response['choices'][0]['message']['content'].strip()
            
            if not question or len(question) < 3:
                question = "Информация"
            
            kb_id = self.add(question, info, source='info_import', added_by=added_by)
            
            logger.info(f"Добавлено (auto-Q): {question[:50]}...")
            return kb_id
            
        except Exception as e:
            logger.error(f"Ошибка add_info_only: {e}")
            return self.add("Информация", info, source='info_import', added_by=added_by)
    
    def get_by_id(self, kb_id: int) -> Optional[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, question, answer FROM knowledge WHERE id = ? AND is_current = 1', (kb_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {'id': row[0], 'question': row[1], 'answer': row[2]}
            return None
        except:
            return None
    
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
    
    def answer_question(self, question: str, use_fallback_gpt: bool = True) -> Tuple[str, float, List[Dict], str]:
        """Ответ с RAG + fallback на GPT. Возвращает (answer, confidence, results, source_type)"""
        
        # 1. Векторный поиск
        search_results = self.kb.vector_search(question, top_k=5, min_score=0.5)
        
        # 2. Если нашли хорошие результаты - используем RAG
        if search_results and search_results[0]['score'] >= 0.65:
            context = self._build_context(search_results[:3])
            confidence = search_results[0]['score']
            answer = self._generate_rag_answer(question, context, search_results)
            return answer, confidence, search_results, "knowledge_base"
        
        # 3. Fallback на GPT
        if use_fallback_gpt:
            try:
                response = openai.ChatCompletion.create(
                    model=self.gpt_model,
                    messages=[
                        {"role": "system", "content": "Ты - помощник компьютерного клуба. Отвечай кратко и по делу."},
                        {"role": "user", "content": question}
                    ],
                    temperature=0.7,
                    max_tokens=300
                )
                answer = response['choices'][0]['message']['content'].strip()
                return answer, 0.3, [], "gpt"
            except Exception as e:
                logger.error(f"GPT fallback error: {e}")
                return "Не нашёл информации.", 0.0, [], "none"
        
        return "Не нашёл информации.", 0.0, [], "none"
    
    def _build_context(self, results: List[Dict]) -> str:
        parts = []
        for r in results:
            answer = r['answer'][:500] + ("..." if len(r['answer']) > 500 else "")
            parts.append(f"[{r['id']}] {r['question']}\n{answer}")
        return "\n\n".join(parts)
    
    def _generate_rag_answer(self, question: str, context: str, results: List[Dict]) -> str:
        try:
            prompt = f"""Ты - ассистент компьютерного клуба. Ответь на вопрос используя контекст.

Вопрос: {question}

Контекст:
{context}

Ответь кратко (2-4 предложения). В конце укажи источники."""

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
        except Exception as e:
            logger.error(f"RAG generation error: {e}")
            return f"{results[0]['answer'][:300]}\n\nИсточник: [{results[0]['id']}]"


class ClubAssistantBot:
    """Главный класс бота v4.5"""
    
    def __init__(self, config: dict):
        self.config = config
        
        logger.info("🚀 Инициализация v4.5...")
        
        self.embedding_service = EmbeddingService(config['openai_api_key'])
        self.vector_store = VectorStore()
        self.vector_store.load()
        
        self.admin_manager = AdminManager(DB_PATH)
        self.creds_manager = CredentialManager(DB_PATH)
        self.kb = KnowledgeBase(DB_PATH, self.embedding_service, self.vector_store)
        self.draft_queue = DraftQueue(DB_PATH)
        self.rag = RAGAnswerer(self.kb, config.get('gpt_model', 'gpt-4o-mini'))
        self.dialog_memory = DialogMemory(DB_PATH)
        
        openai.api_key = config['openai_api_key']
        
        self.confidence_threshold = config.get('draft_queue', {}).get('confidence_threshold', 0.7)
        self.bot_username = None  # Установим при запуске
        
        logger.info(f"✅ Бот v{VERSION} готов!")
        logger.info(f"   Векторов: {self.vector_store.stats()['total_vectors']}")
        logger.info(f"   Записей: {self.kb.count()}")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_admin = self.admin_manager.is_admin(user.id)
        
        text = f"""👋 Привет, {user.first_name}!

Я ассистент клуба v{VERSION}.

💬 Просто задай вопрос - я отвечу!

В группах: упомяни меня @{self.bot_username or 'botname'}

Команды: /help"""

        if is_admin:
            text += "\n\n🔧 Админ: /admin"
        
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_admin = self.admin_manager.is_admin(update.effective_user.id)
        
        text = f"""📖 Помощь v{VERSION}

💬 В личке: просто спрашивай
💬 В группе: упомяни @{self.bot_username or 'botname'}

Команды:
/start - приветствие
/stats - статистика
/help - справка"""

        if is_admin:
            text += """\n\n🔧 Админ:
/admin - панель
/learn <инфо> - добавить
/remember - запомнить из диалога
/import - файл
/addadmin <id>
/admins
/review
/savecreds <сервис> <логин> <пароль>
/getcreds [сервис]"""

        await update.message.reply_text(text)
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        kb_count = self.kb.count()
        vector_stats = self.vector_store.stats()
        draft_stats = self.draft_queue.stats()
        
        text = f"""📊 Статистика v{VERSION}

📚 База знаний:
• Записей: {kb_count}
• Векторов: {vector_stats['total_vectors']}

📝 Черновики:
• Ожидают: {draft_stats.get('pending', 0)}
• Одобрено: {draft_stats.get('approved', 0)}"""

        await update.message.reply_text(text)
    
    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        text = f"""🔧 Админ-панель v{VERSION}

/learn <информация> - добавить инфу
/remember - запомнить из последнего диалога
/import - импорт файла
/review - черновики ({self.draft_queue.stats().get('pending', 0)} шт)
/approve <id> - одобрить
/reject <id> - отклонить
/addadmin <id>
/admins
/savecreds <сервис> <логин> <пароль>
/getcreds [сервис]
/update - обновить из GitHub"""

        await update.message.reply_text(text)
    
    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        text = update.message.text.replace('/learn', '').strip()
        
        if not text or len(text) < 10:
            await update.message.reply_text("Напиши информацию после /learn\n\nПример:\n/learn Клуб находится на ул. Ленина 123")
            return
        
        try:
            kb_id = self.kb.add_info_only(text, added_by=update.effective_user.id)
            record = self.kb.get_by_id(kb_id)
            
            if record:
                await update.message.reply_text(f"✅ Добавлено [ID: {kb_id}]\n\n❓ {record['question']}")
            else:
                await update.message.reply_text(f"✅ Добавлено [ID: {kb_id}]")
            
        except Exception as e:
            logger.error(f"Learn error: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_remember(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запомнить информацию из диалога"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        chat_id = update.effective_chat.id
        dialog_context = self.dialog_memory.get_context(chat_id, limit=10)
        
        if not dialog_context:
            await update.message.reply_text("Нет истории диалога")
            return
        
        await update.message.reply_text("⏳ Анализирую диалог и запоминаю...")
        
        try:
            # Просим GPT извлечь полезную информацию
            prompt = f"""Из этого диалога извлеки полезную информацию, которую можно сохранить в базу знаний.

Диалог:
{dialog_context}

Верни только чистую информацию (факты) без вопросов, в 1-3 предложениях."""

            response = openai.ChatCompletion.create(
                model='gpt-4o-mini',
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            info = response['choices'][0]['message']['content'].strip()
            
            if len(info) < 10:
                await update.message.reply_text("Не нашёл полезной информации в диалоге")
                return
            
            # Добавляем в базу
            kb_id = self.kb.add_info_only(info, added_by=update.effective_user.id)
            record = self.kb.get_by_id(kb_id)
            
            text = f"✅ Запомнил! [ID: {kb_id}]\n\n"
            if record:
                text += f"❓ {record['question']}\n"
            text += f"💬 {info[:200]}..."
            
            await update.message.reply_text(text)
            
        except Exception as e:
            logger.error(f"Remember error: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_import(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        await update.message.reply_text("""📥 Импорт информации

Формат .txt:
```
информация 1
информация 2
информация 3
```

Каждая строка = 1 запись.
Вопросы генерятся автоматически!

Отправь файл.""")
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        doc = update.message.document
        
        if not doc.file_name.endswith('.txt'):
            await update.message.reply_text("Только .txt файлы!")
            return
        
        await update.message.reply_text("⏳ Импортирую...")
        
        try:
            file = await context.bot.get_file(doc.file_id)
            content = await file.download_as_bytearray()
            text = content.decode('utf-8')
            
            imported = 0
            errors = 0
            
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 10]
            total = len(lines)
            
            for i, info in enumerate(lines, 1):
                try:
                    if i % 10 == 0:
                        await update.message.reply_text(f"⏳ {i}/{total}...")
                    
                    self.kb.add_info_only(info, added_by=update.effective_user.id)
                    imported += 1
                except Exception as e:
                    logger.error(f"Import line error: {e}")
                    errors += 1
            
            await update.message.reply_text(f"✅ Импортировано: {imported}\n⚠️ Ошибок: {errors}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        drafts = self.draft_queue.get_pending(limit=5)
        
        if not drafts:
            await update.message.reply_text("✅ Нет черновиков!")
            return
        
        text = f"📝 Черновиков: {self.draft_queue.stats().get('pending', 0)}\n\n"
        
        for d in drafts:
            text += f"#{d['id']} (conf: {d['confidence']:.2f})\n"
            text += f"❓ {d['question'][:100]}\n"
            text += f"💬 {d['answer'][:150]}...\n\n"
        
        text += "Одобрить: /approve <id>\nУдалить: /reject <id>"
        
        await update.message.reply_text(text)
    
    async def cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            draft_id = int(context.args[0])
            draft = self.draft_queue.get_draft(draft_id)
            
            if not draft:
                await update.message.reply_text("❌ Не найден")
                return
            
            kb_id = self.kb.add(draft['question'], draft['answer'], draft['category'], draft['tags'], 'approved_draft', update.effective_user.id)
            self.draft_queue.approve(draft_id, update.effective_user.id)
            
            await update.message.reply_text(f"✅ Одобрено! [ID: {kb_id}]")
        except:
            await update.message.reply_text("Использование: /approve <id>")
    
    async def cmd_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            draft_id = int(context.args[0])
            self.draft_queue.reject(draft_id, update.effective_user.id)
            await update.message.reply_text("🗑 Отклонено")
        except:
            await update.message.reply_text("Использование: /reject <id>")
    
    async def cmd_addadmin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            new_admin_id = int(context.args[0])
            self.admin_manager.add_admin(new_admin_id, added_by=update.effective_user.id)
            await update.message.reply_text(f"✅ Админ добавлен: {new_admin_id}")
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
                text += f" (@{username})"
            if full_name:
                text += f" - {full_name}"
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
        
        service = context.args[0] if context.args else None
        creds = self.creds_manager.get(update.effective_user.id, service)
        
        if not creds:
            await update.message.reply_text("Нет сохранённых учёток")
            return
        
        text = "🔑 Учётки:\n\n"
        for c in creds:
            text += f"🔹 {c['service']}\n"
            text += f"Login: {c['login']}\n"
            text += f"Pass: {c['password']}\n\n"
        
        await context.bot.send_message(chat_id=update.effective_user.id, text=text)
        
        if update.message.chat.type != 'private':
            await update.message.reply_text("✅ Отправил в личку")
    
    async def cmd_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text("🔄 Запускаю обновление...\nБот перезапустится через несколько секунд.")
        os.system('bash /opt/club_assistant/update.sh > /tmp/update.log 2>&1 &')
    
    def _should_respond_in_group(self, update: Update) -> bool:
        """Проверка: нужно ли отвечать в группе"""
        message = update.message
        
        # В личке - всегда отвечаем
        if message.chat.type == 'private':
            return True
        
        # В группе - только если:
        # 1. Это reply на бота
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            return True
        
        # 2. Упомянут бот @username
        if message.text and self.bot_username and f"@{self.bot_username}" in message.text:
            return True
        
        # 3. Это команда
        if message.text and message.text.startswith('/'):
            return True
        
        return False
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений"""
        user = update.effective_user
        message = update.message
        question = message.text.strip()
        chat_id = message.chat.id
        
        # Сохраняем в память диалога (для админов)
        if self.admin_manager.is_admin(user.id):
            self.dialog_memory.add_message(chat_id, user.id, question, is_bot=False)
        
        if len(question) < 3:
            return
        
        # Проверяем нужно ли отвечать в группе
        if not self._should_respond_in_group(update):
            return
        
        # Убираем упоминание бота из вопроса
        if self.bot_username and f"@{self.bot_username}" in question:
            question = question.replace(f"@{self.bot_username}", "").strip()
        
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        logger.info(f"Q: {user.username}: {question}")
        
        # RAG ответ
        answer, confidence, results, source_type = self.rag.answer_question(question, use_fallback_gpt=True)
        
        logger.info(f"A: conf={confidence:.2f}, source={source_type}")
        
        # Добавляем метку источника
        if source_type == "knowledge_base":
            prefix = "📚 Из базы знаний:\n\n"
        elif source_type == "gpt":
            prefix = "🤖 GPT (нет в базе):\n\n"
        else:
            prefix = ""
        
        full_answer = prefix + answer
        
        # Сохраняем ответ в память
        if self.admin_manager.is_admin(user.id):
            self.dialog_memory.add_message(chat_id, context.bot.id, answer, is_bot=True)
        
        # Если низкая уверенность - в черновики
        if 0.3 < confidence < self.confidence_threshold and source_type == "gpt":
            self.draft_queue.add_draft(question, answer, confidence=confidence, source='low_conf', added_by=user.id)
        
        await message.reply_text(full_answer)
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка фото (GPT-4 Vision)"""
        # В группе - только если упомянут бот
        if not self._should_respond_in_group(update):
            return
        
        user = update.effective_user
        caption = update.message.caption or ""
        
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
                        {"type": "text", "text": caption or "Что на этом изображении?"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{photo_b64}"}}
                    ]
                }],
                max_tokens=500
            )
            
            answer = response['choices'][0]['message']['content']
            await update.message.reply_text(f"🤖 GPT Vision:\n\n{answer}")
            
        except Exception as e:
            logger.error(f"Photo error: {e}")
            await update.message.reply_text(f"Не могу обработать фото: {e}")
    
    async def post_init(self, application: Application):
        """Инициализация после запуска"""
        bot = await application.bot.get_me()
        self.bot_username = bot.username
        logger.info(f"Bot username: @{self.bot_username}")
    
    def run(self):
        """Запуск"""
        app = Application.builder().token(self.config['telegram_token']).build()
        
        # Post init
        app.post_init = self.post_init
        
        # Команды
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("admin", self.cmd_admin))
        app.add_handler(CommandHandler("learn", self.cmd_learn))
        app.add_handler(CommandHandler("remember", self.cmd_remember))
        app.add_handler(CommandHandler("import", self.cmd_import))
        app.add_handler(CommandHandler("review", self.cmd_review))
        app.add_handler(CommandHandler("approve", self.cmd_approve))
        app.add_handler(CommandHandler("reject", self.cmd_reject))
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
    print("   Dialog Learning Edition")
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
