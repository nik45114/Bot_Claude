#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Assistant Bot v4.4 - Production Edition
Telegram бот с RAG, векторным поиском и автогенерацией вопросов
"""

import os
import sys
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import io
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

VERSION = "4.4"


class AdminManager:
    """Управление администраторами"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def add_admin(self, user_id: int, username: str = "", full_name: str = "", added_by: int = 0) -> bool:
        """Добавить админа"""
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
        """Удалить админа"""
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
        """Список админов"""
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
        """Проверка админа"""
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
    """Управление учётками (savecreds/getcreds)"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def save(self, user_id: int, service: str, login: str, password: str) -> bool:
        """Сохранить учётку"""
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
        """Получить учётки"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if service:
                cursor.execute('''
                    SELECT service, login, password 
                    FROM admin_credentials 
                    WHERE user_id = ? AND service = ?
                ''', (user_id, service))
            else:
                cursor.execute('''
                    SELECT service, login, password 
                    FROM admin_credentials 
                    WHERE user_id = ?
                ''', (user_id,))
            
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
        """Добавление знания"""
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
        """Добавление информации с автогенерацией вопросов"""
        try:
            # Генерируем 3-5 вопросов через GPT
            prompt = f"""Из этого текста сформулируй 3-5 коротких вопросов (3-10 слов каждый), на которые этот текст отвечает.

Текст:
{info}

Верни только вопросы, каждый с новой строки, без нумерации."""

            response = openai.ChatCompletion.create(
                model=gpt_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=200
            )
            
            questions_text = response['choices'][0]['message']['content'].strip()
            questions = [q.strip() for q in questions_text.split('\n') if q.strip()]
            
            if not questions:
                questions = ["Информация"]
            
            # Берём первый вопрос как основной
            main_question = questions[0]
            
            # Добавляем в базу
            kb_id = self.add(main_question, info, source='info_import', added_by=added_by)
            
            logger.info(f"Добавлено (auto-Q): {main_question[:50]}...")
            return kb_id
            
        except Exception as e:
            logger.error(f"Ошибка add_info_only: {e}")
            # Fallback - добавляем с дефолтным вопросом
            return self.add("Информация", info, source='info_import', added_by=added_by)
    
    def get_by_id(self, kb_id: int) -> Optional[Dict]:
        """Получить по ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, question, answer, category, tags FROM knowledge WHERE id = ? AND is_current = 1', (kb_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {'id': row[0], 'question': row[1], 'answer': row[2], 'category': row[3], 'tags': row[4]}
            return None
        except:
            return None
    
    def vector_search(self, query: str, top_k: int = 5, min_score: float = 0.5) -> List[Dict]:
        """Векторный поиск"""
        try:
            query_vector = self.embedding_service.embed(query)
            results = self.vector_store.search(query_vector, top_k=top_k, min_score=min_score)
            
            if not results:
                return []
            
            kb_ids = [r['kb_id'] for r in results]
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            placeholders = ','.join(['?'] * len(kb_ids))
            cursor.execute(f'SELECT id, question, answer, category, tags FROM knowledge WHERE id IN ({placeholders}) AND is_current = 1', kb_ids)
            rows = cursor.fetchall()
            conn.close()
            
            kb_dict = {row[0]: {'id': row[0], 'question': row[1], 'answer': row[2], 'category': row[3], 'tags': row[4]} for row in rows}
            
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
    """RAG ответчик"""
    
    def __init__(self, knowledge_base: KnowledgeBase, gpt_model: str = 'gpt-4o-mini'):
        self.kb = knowledge_base
        self.gpt_model = gpt_model
    
    def answer_question(self, question: str, use_fallback_gpt: bool = True) -> Tuple[str, float, List[Dict]]:
        """Ответ с RAG + fallback на GPT"""
        # 1. Векторный поиск
        search_results = self.kb.vector_search(question, top_k=5, min_score=0.5)
        
        # 2. Если нашли хорошие результаты - используем RAG
        if search_results and search_results[0]['score'] >= 0.65:
            context = self._build_context(search_results[:3])
            confidence = search_results[0]['score']
            answer = self._generate_rag_answer(question, context, search_results)
            return answer, confidence, search_results
        
        # 3. Если ничего не нашли И разрешён fallback - используем чистый GPT
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
                return answer, 0.3, []
            except Exception as e:
                logger.error(f"GPT fallback error: {e}")
                return "Не нашёл информации. Попробуй переформулировать.", 0.0, []
        
        # 4. Без fallback - честно говорим что не знаем
        return "Не нашёл информации по этому вопросу. Попробуй переформулировать или уточнить.", 0.0, []
    
    def _build_context(self, results: List[Dict]) -> str:
        """Построение контекста"""
        parts = []
        for r in results:
            answer = r['answer'][:500] + ("..." if len(r['answer']) > 500 else "")
            parts.append(f"[{r['id']}] {r['question']}\n{answer}")
        return "\n\n".join(parts)
    
    def _generate_rag_answer(self, question: str, context: str, results: List[Dict]) -> str:
        """Генерация RAG ответа"""
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
            
            # Добавляем источники если их нет
            if '[' not in answer:
                sources = ', '.join([f"[{r['id']}]" for r in results[:3]])
                answer += f"\n\nИсточники: {sources}"
            
            return answer
        except Exception as e:
            logger.error(f"RAG generation error: {e}")
            # Fallback на первый результат
            return f"{results[0]['answer'][:300]}\n\nИсточник: [{results[0]['id']}]"


class ClubAssistantBot:
    """Главный класс бота v4.4"""
    
    def __init__(self, config: dict):
        self.config = config
        
        logger.info("🚀 Инициализация v4.4...")
        
        self.embedding_service = EmbeddingService(config['openai_api_key'])
        self.vector_store = VectorStore()
        self.vector_store.load()
        
        self.admin_manager = AdminManager(DB_PATH)
        self.creds_manager = CredentialManager(DB_PATH)
        self.kb = KnowledgeBase(DB_PATH, self.embedding_service, self.vector_store)
        self.draft_queue = DraftQueue(DB_PATH)
        self.rag = RAGAnswerer(self.kb, config.get('gpt_model', 'gpt-4o-mini'))
        
        openai.api_key = config['openai_api_key']
        
        self.confidence_threshold = config.get('draft_queue', {}).get('confidence_threshold', 0.7)
        
        logger.info(f"✅ Бот v{VERSION} готов!")
        logger.info(f"   Векторов: {self.vector_store.stats()['total_vectors']}")
        logger.info(f"   Записей: {self.kb.count()}")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Старт"""
        user = update.effective_user
        is_admin = self.admin_manager.is_admin(user.id)
        
        text = f"""👋 Привет, {user.first_name}!

Я ассистент клуба v{VERSION}.

💬 Просто задай вопрос - я отвечу!

Команды: /help"""

        if is_admin:
            text += "\n\n🔧 Админ: /admin"
        
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Помощь"""
        is_admin = self.admin_manager.is_admin(update.effective_user.id)
        
        text = f"""📖 Помощь v{VERSION}

💬 Просто спрашивай - я отвечу!

Команды:
/start - приветствие
/stats - статистика
/help - эта справка"""

        if is_admin:
            text += """\n\n🔧 Админ-команды:
/admin - админ-панель
/learn <текст> - добавить инфу
/import - импорт файла
/addadmin <user_id>
/admins - список админов
/review - черновики
/savecreds <сервис> <логин> <пароль>
/getcreds [сервис]"""

        await update.message.reply_text(text)
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика"""
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
        """Админ-панель"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        text = f"""🔧 Админ-панель v{VERSION}

/learn <информация>
  Просто пиши инфу, вопрос сгенерится сам
  Пример: /learn Клуб на ул. Ленина 123

/import
  Отправь .txt файл с информацией
  Формат: каждая строка = 1 запись (только инфа!)
  
/review - черновики ({self.draft_queue.stats().get('pending', 0)} шт)
/approve <id> - одобрить
/reject <id> - отклонить

/addadmin <id> - добавить админа
/admins - список админов

/savecreds <сервис> <логин> <пароль>
/getcreds [сервис]

/update - обновить бота из GitHub"""

        await update.message.reply_text(text)
    
    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обучение - свободная форма"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        text = update.message.text.replace('/learn', '').strip()
        
        if not text or len(text) < 10:
            await update.message.reply_text("Напиши информацию после /learn\n\nПример:\n/learn Клуб находится на ул. Ленина 123, работает с 10 до 22")
            return
        
        await update.message.reply_text("⏳ Генерирую вопрос и добавляю...")
        
        try:
            kb_id = self.kb.add_info_only(text, added_by=update.effective_user.id)
            
            # Получаем что добавили
            record = self.kb.get_by_id(kb_id)
            
            if record:
                await update.message.reply_text(f"✅ Добавлено [ID: {kb_id}]\n\n❓ {record['question']}\n💬 {text[:150]}...")
            else:
                await update.message.reply_text(f"✅ Добавлено [ID: {kb_id}]")
            
        except Exception as e:
            logger.error(f"Learn error: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_import(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Импорт"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        await update.message.reply_text("""📥 Импорт информации

Формат файла .txt:
```
информация 1
информация 2
информация 3
```

Каждая строка = 1 запись.
Вопросы генерятся автоматически!

Отправь файл.""")
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка файлов импорта"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        doc = update.message.document
        
        if not doc.file_name.endswith('.txt'):
            await update.message.reply_text("Только .txt файлы!")
            return
        
        await update.message.reply_text("⏳ Импортирую (генерирую вопросы)...")
        
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
        """Ревью черновиков"""
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
        """Одобрить черновик"""
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
        """Отклонить черновик"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            draft_id = int(context.args[0])
            self.draft_queue.reject(draft_id, update.effective_user.id)
            await update.message.reply_text("🗑 Отклонено")
        except:
            await update.message.reply_text("Использование: /reject <id>")
    
    async def cmd_addadmin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавить админа"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            new_admin_id = int(context.args[0])
            self.admin_manager.add_admin(new_admin_id, added_by=update.effective_user.id)
            await update.message.reply_text(f"✅ Админ добавлен: {new_admin_id}")
        except:
            await update.message.reply_text("Использование: /addadmin <user_id>")
    
    async def cmd_admins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список админов"""
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
        """Сохранить учётку"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            service = context.args[0]
            login = context.args[1]
            password = context.args[2]
            
            self.creds_manager.save(update.effective_user.id, service, login, password)
            await update.message.reply_text(f"✅ Сохранено: {service}")
            
            # Удаляем сообщение с паролем
            await update.message.delete()
        except:
            await update.message.reply_text("Использование: /savecreds <сервис> <логин> <пароль>")
    
    async def cmd_getcreds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получить учётки"""
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
        
        # Отправляем в приват
        await context.bot.send_message(chat_id=update.effective_user.id, text=text)
        
        if update.message.chat.type != 'private':
            await update.message.reply_text("✅ Отправил в личку")
    
    async def cmd_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновление из GitHub"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text("🔄 Запускаю обновление...\nБот перезапустится через несколько секунд.")
        
        # Запускаем update.sh
        os.system('bash /opt/club_assistant/update.sh > /tmp/update.log 2>&1 &')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка вопросов"""
        user = update.effective_user
        question = update.message.text.strip()
        
        if len(question) < 3:
            return
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        logger.info(f"Q: {user.username}: {question}")
        
        # RAG ответ
        answer, confidence, results = self.rag.answer_question(question, use_fallback_gpt=True)
        
        logger.info(f"A: conf={confidence:.2f}, results={len(results)}")
        
        # Если низкая уверенность - в черновики
        if 0.3 < confidence < self.confidence_threshold:
            self.draft_queue.add_draft(question, answer, confidence=confidence, source='low_conf', added_by=user.id)
        
        await update.message.reply_text(answer)
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка фото (GPT-4 Vision)"""
        user = update.effective_user
        caption = update.message.caption or ""
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            # Получаем фото
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()
            
            # Base64
            photo_b64 = base64.b64encode(photo_bytes).decode('utf-8')
            
            # GPT-4 Vision
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": caption or "Что на этом изображении?"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{photo_b64}"}}
                        ]
                    }
                ],
                max_tokens=500
            )
            
            answer = response['choices'][0]['message']['content']
            await update.message.reply_text(answer)
            
        except Exception as e:
            logger.error(f"Photo error: {e}")
            await update.message.reply_text(f"Не могу обработать фото: {e}")
    
    def run(self):
        """Запуск"""
        app = Application.builder().token(self.config['telegram_token']).build()
        
        # Команды
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("admin", self.cmd_admin))
        app.add_handler(CommandHandler("learn", self.cmd_learn))
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
    """Загрузка конфига"""
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Не найден {CONFIG_PATH}")
        sys.exit(1)
    
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def init_database():
    """Инициализация БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблицы
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
    print("   Auto-Question Generation Edition")
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
