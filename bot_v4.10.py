#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Assistant Bot v4.10 - Learning Logic Fix
Автообучение ТОЛЬКО в группах, улучшенные фильтры
"""

import os
import sys
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import base64
import subprocess

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import openai

try:
    from embeddings import EmbeddingService
    from vector_store import VectorStore
    from draft_queue import DraftQueue
    from v2ray_manager import V2RayManager
    from v2ray_commands import V2RayCommands
except ImportError:
    print("❌ Не найдены модули v4.0!")
    sys.exit(1)

CONFIG_PATH = 'config.json'
DB_PATH = 'knowledge.db'

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

VERSION = "4.10"


class AdminManager:
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
        except:
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
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def save(self, user_id: int, service: str, login: str, password: str) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO admin_credentials (user_id, service, login, password) VALUES (?, ?, ?, ?)', 
                         (user_id, service, login, password))
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
            
            logger.info(f"✅ Добавлено: kb_id={kb_id}, Q: {question[:50]}")
            return kb_id
        except Exception as e:
            logger.error(f"❌ Ошибка add: {e}")
            return 0
    
    def add_smart(self, info: str, category: str, gpt_model: str = 'gpt-4o-mini', added_by: int = 0) -> int:
        """Умное добавление с генерацией вопроса через GPT"""
        try:
            # Генерируем вопрос
            prompt = f"""Из текста сформулируй короткий вопрос (3-10 слов).

Категория: {category}

Текст:
{info}

ВАЖНО: Вопрос должен быть ДРУГИМ, не просто повторять текст!

Верни только вопрос."""

            response = openai.ChatCompletion.create(
                model=gpt_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50
            )
            
            question = response['choices'][0]['message']['content'].strip()
            
            # Проверка: вопрос не должен совпадать с ответом
            if not question or len(question) < 3 or question == info:
                # Если GPT вернул тот же текст - делаем вопрос из первых слов
                words = info.split()[:8]
                question = ' '.join(words) + '?'
            
            kb_id = self.add(question, info, category=category, source='auto_smart', added_by=added_by)
            
            logger.info(f"  Q: {question[:50]}")
            logger.info(f"  A: {info[:50]}")
            
            return kb_id
            
        except Exception as e:
            logger.error(f"❌ add_smart error: {e}")
            return 0
    
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
            logger.error(f"❌ vector_search error: {e}")
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
    
    def cleanup_duplicates(self) -> int:
        """Удаление дубликатов и мусора"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Удаляем точные дубликаты
            cursor.execute('''
                DELETE FROM knowledge 
                WHERE id NOT IN (
                    SELECT MIN(id) 
                    FROM knowledge 
                    GROUP BY question, answer
                )
            ''')
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            return deleted
        except:
            return 0


class SmartAutoLearner:
    """Умное автообучение через GPT-анализ"""
    
    def __init__(self, kb: KnowledgeBase, gpt_model: str = 'gpt-4o-mini'):
        self.kb = kb
        self.gpt_model = gpt_model
    
    def analyze_message(self, text: str) -> Optional[Dict]:
        """Анализ сообщения через GPT: стоит ли запоминать?"""
        
        if len(text) < 10:  # Минимум 10 символов
            return None
        
        if text.startswith('/'):
            return None
        
        # НЕ запоминаем вопросы
        if text.strip().endswith('?'):
            return None
        
        # НЕ запоминаем если начинается с вопросительных слов
        question_starts = ['что ', 'как ', 'где ', 'когда ', 'почему ', 'зачем ', 'кто ', 'куда ', 'откуда ']
        text_lower = text.lower()
        for q in question_starts:
            if text_lower.startswith(q):
                return None
        
        try:
            prompt = f"""Проанализируй сообщение из чата компьютерного клуба.

Сообщение:
{text}

Определи:
1. Это полезная информация для базы знаний? (да/нет)
2. Категория:
   - "problem" - проблема
   - "solution" - решение/инструкция
   - "incident" - инцидент
   - "info" - важная информация о клубе
   - "skip" - не нужно

Верни JSON:
{{"should_remember": true/false, "category": "...", "reason": "..."}}

Запоминать ТОЛЬКО:
- Решения технических проблем (с конкретными действиями)
- Инструкции по работе оборудования
- Инциденты и их решения
- Важную информацию о клубе (цены, адрес, время)

НЕ запоминать:
- Вопросы (даже если есть "что делать")
- Обычное общение
- Приветствия
- Короткие фразы
- Обсуждения без конкретных решений"""

            response = openai.ChatCompletion.create(
                model=self.gpt_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150
            )
            
            result_text = response['choices'][0]['message']['content'].strip()
            
            import re
            json_match = re.search(r'\{[^}]+\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                
                if result.get('should_remember') and result.get('category') != 'skip':
                    return {
                        'category': result['category'],
                        'reason': result.get('reason', '')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ GPT analyze error: {e}")
            return None
    
    def learn_from_message(self, text: str, user_id: int) -> Optional[int]:
        """Обучение из сообщения"""
        
        analysis = self.analyze_message(text)
        
        if not analysis:
            return None
        
        category = analysis['category']
        reason = analysis['reason']
        
        logger.info(f"📚 Запоминаю ({category}): {text[:50]}... | {reason}")
        
        kb_id = self.kb.add_smart(text, category=category, added_by=user_id)
        
        if kb_id:
            logger.info(f"✅ Запомнил [ID: {kb_id}]")
        
        return kb_id


class RAGAnswerer:
    """RAG с защитой от галлюцинаций"""
    
    def __init__(self, knowledge_base: KnowledgeBase, gpt_model: str = 'gpt-4o-mini'):
        self.kb = knowledge_base
        self.gpt_model = gpt_model
    
    def answer_question(self, question: str) -> Tuple[str, float, List[Dict], str]:
        """Ответ с защитой от галлюцинаций"""
        
        # Векторный поиск
        search_results = self.kb.vector_search(question, top_k=3, min_score=0.65)
        
        # Если нашли с хорошим скором - используем базу
        if search_results and search_results[0]['score'] >= 0.70:
            # Строгий RAG - только из базы
            answer = self._build_strict_answer(search_results)
            return answer, search_results[0]['score'], search_results, "knowledge_base"
        
        # Если скор средний - честно говорим что нет в базе
        if search_results and search_results[0]['score'] >= 0.55:
            answer = f"В базе нет точной информации по этому вопросу.\n\nНашёл похожее:\n\n"
            answer += search_results[0]['answer'][:200]
            answer += f"\n\nИсточник: [{search_results[0]['id']}]"
            return answer, search_results[0]['score'], search_results, "partial"
        
        # Fallback на GPT БЕЗ обмана
        try:
            response = openai.ChatCompletion.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": "Ты - помощник компьютерного клуба. Отвечай кратко. Если не знаешь - честно скажи."},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=300
            )
            answer = response['choices'][0]['message']['content'].strip()
            return answer, 0.3, [], "gpt"
        except:
            return "Не знаю ответа на этот вопрос.", 0.0, [], "none"
    
    def _build_strict_answer(self, results: List[Dict]) -> str:
        """Строгий ответ только из базы"""
        # Берём топ результат
        top = results[0]
        
        answer = top['answer']
        
        # Обрезаем если слишком длинный
        if len(answer) > 800:
            answer = answer[:800] + "..."
        
        # Добавляем источники
        sources = ', '.join([f"[{r['id']}]" for r in results[:2]])
        answer += f"\n\nИсточники: {sources}"
        
        return answer


class ClubAssistantBot:
    def __init__(self, config: dict):
        self.config = config
        
        logger.info("🚀 Инициализация v4.8...")
        
        self.embedding_service = EmbeddingService(config['openai_api_key'])
        self.vector_store = VectorStore()
        self.vector_store.load()
        
        self.admin_manager = AdminManager(DB_PATH)
        self.creds_manager = CredentialManager(DB_PATH)
        self.kb = KnowledgeBase(DB_PATH, self.embedding_service, self.vector_store)
        self.draft_queue = DraftQueue(DB_PATH)
        self.rag = RAGAnswerer(self.kb, config.get('gpt_model', 'gpt-4o-mini'))
        self.smart_learner = SmartAutoLearner(self.kb, config.get('gpt_model', 'gpt-4o-mini'))
        
        # V2Ray Manager (только для владельца)
        self.v2ray_manager = V2RayManager(DB_PATH)
        owner_id = config.get('owner_id', config['admin_ids'][0] if config.get('admin_ids') else 0)
        self.v2ray_commands = V2RayCommands(self.v2ray_manager, self.admin_manager, owner_id)
        
        openai.api_key = config['openai_api_key']
        
        self.bot_username = None
        
        logger.info(f"✅ Бот v{VERSION} готов!")
        logger.info(f"   Векторов: {self.vector_store.stats()['total_vectors']}")
        logger.info(f"   Записей: {self.kb.count()}")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = f"""👋 Привет!

Я ассистент клуба v{VERSION}.

🤖 Запоминаю только важное:
• Проблемы и решения
• Инструкции
• Инциденты
• Важную информацию о клубе

💬 В личке: просто спрашивай
💬 В группе: @{self.bot_username or 'bot'} вопрос

/help - справка"""

        if self.admin_manager.is_admin(update.effective_user.id):
            text += "\n\n🔧 /admin"
        
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = f"""📖 Помощь v{VERSION}

🤖 Умное автообучение:
Запоминаю проблемы, решения, инциденты

💬 В личке: спрашивай
💬 В группе: @{self.bot_username or 'bot'} вопрос

/stats - статистика"""

        if self.admin_manager.is_admin(update.effective_user.id):
            text += "\n\n🔧 /admin - админ-панель"

        await update.message.reply_text(text)
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        kb_count = self.kb.count()
        vector_stats = self.vector_store.stats()
        
        text = f"""📊 Статистика v{VERSION}

📚 База знаний:
• Записей: {kb_count}
• Векторов: {vector_stats['total_vectors']}

🤖 Умное автообучение: ВКЛ"""

        await update.message.reply_text(text)
    
    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Только для админов")
            return
        
        text = f"""🔧 Админ-панель v{VERSION}

Команды:
/learn <инфо> - добавить
/import - импорт файла
/cleanup - удалить дубликаты
/fixdb - исправить битые записи
/fixjson - исправить JSON в ответах ⚠️
/deletetrash - удалить мусорные записи ⚠️
/viewrecord <id> - посмотреть запись
/addadmin <id>
/admins
/savecreds <сервис> <логин> <пароль>
/getcreds
/update - обновить"""

        await update.message.reply_text(text)
    
    async def cmd_cleanup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Очистка дубликатов"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text("⏳ Удаляю дубликаты...")
        
        deleted = self.kb.cleanup_duplicates()
        
        await update.message.reply_text(f"✅ Удалено: {deleted}")
    
    async def cmd_fixdb(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Исправление записей где вопрос = ответ"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text("⏳ Исправляю плохие записи...")
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Находим записи где вопрос = ответ
            cursor.execute('''
                SELECT id, answer 
                FROM knowledge 
                WHERE question = answer 
                AND is_current = 1
            ''')
            
            bad_records = cursor.fetchall()
            
            if not bad_records:
                await update.message.reply_text("✅ Нет плохих записей")
                conn.close()
                return
            
            fixed = 0
            
            for rec_id, answer in bad_records[:100]:  # По 100 за раз
                try:
                    # Генерируем вопрос из первых слов
                    words = answer.split()[:8]
                    new_question = ' '.join(words) + '?'
                    
                    # Обновляем
                    cursor.execute('UPDATE knowledge SET question = ? WHERE id = ?', (new_question, rec_id))
                    fixed += 1
                    
                except:
                    pass
            
            conn.commit()
            conn.close()
            
            await update.message.reply_text(f"✅ Исправлено: {fixed} из {len(bad_records)}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_deletetrash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление мусорных автогенерированных записей"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text("⏳ Ищу мусорные записи...")
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Ищем записи где ответ - это вопрос
            cursor.execute('''
                SELECT id, question, answer 
                FROM knowledge 
                WHERE is_current = 1 
                AND (
                    answer LIKE 'что %'
                    OR answer LIKE 'как %'
                    OR answer LIKE 'где %'
                    OR answer LIKE 'когда %'
                    OR answer LIKE 'почему %'
                    OR answer LIKE 'зачем %'
                    OR LENGTH(answer) < 30
                )
                LIMIT 20
            ''')
            
            examples = cursor.fetchall()
            
            if examples:
                msg = "📋 Найдены мусорные записи:\n\n"
                for rec_id, q, a in examples[:5]:
                    msg += f"ID: {rec_id}\n"
                    msg += f"Q: {q[:60]}\n"
                    msg += f"A: {a[:60]}\n\n"
                await update.message.reply_text(msg)
            
            # Считаем всего
            cursor.execute('''
                SELECT COUNT(*) 
                FROM knowledge 
                WHERE is_current = 1 
                AND (
                    answer LIKE 'что %'
                    OR answer LIKE 'как %'
                    OR answer LIKE 'где %'
                    OR answer LIKE 'когда %'
                    OR answer LIKE 'почему %'
                    OR answer LIKE 'зачем %'
                    OR LENGTH(answer) < 30
                )
            ''')
            
            count = cursor.fetchone()[0]
            
            if count == 0:
                await update.message.reply_text("✅ Нет мусорных записей")
                conn.close()
                return
            
            await update.message.reply_text(f"Найдено мусорных записей: {count}\n\nУдаляю...")
            
            # Удаляем
            cursor.execute('''
                DELETE FROM knowledge 
                WHERE is_current = 1 
                AND (
                    answer LIKE 'что %'
                    OR answer LIKE 'как %'
                    OR answer LIKE 'где %'
                    OR answer LIKE 'когда %'
                    OR answer LIKE 'почему %'
                    OR answer LIKE 'зачем %'
                    OR LENGTH(answer) < 30
                )
            ''')
            
            deleted = cursor.rowcount
            conn.commit()
            
            # Статистика
            cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 1')
            remaining = cursor.fetchone()[0]
            
            conn.close()
            
            await update.message.reply_text(f"✅ Удалено: {deleted}\nОсталось записей: {remaining}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_viewrecord(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Просмотр конкретной записи по ID"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            rec_id = int(context.args[0])
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT id, question, answer, category, source FROM knowledge WHERE id = ?', (rec_id,))
            record = cursor.fetchone()
            conn.close()
            
            if not record:
                await update.message.reply_text(f"❌ Запись {rec_id} не найдена")
                return
            
            rec_id, question, answer, category, source = record
            
            msg = f"📋 Запись #{rec_id}\n\n"
            msg += f"🔹 Категория: {category}\n"
            msg += f"🔹 Источник: {source}\n\n"
            msg += f"❓ Вопрос:\n{question}\n\n"
            msg += f"💬 Ответ:\n{answer[:500]}"
            
            if len(answer) > 500:
                msg += f"\n\n... (всего {len(answer)} символов)"
            
            await update.message.reply_text(msg)
            
        except:
            await update.message.reply_text("Использование: /viewrecord <id>\n\nПример: /viewrecord 7023")
    
    async def cmd_fixjson(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Исправление записей с JSON в ответах"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text("⏳ Ищу записи с JSON...")
        
        try:
            import re
            import json as json_lib
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Ищем записи с JSON
            cursor.execute('''
                SELECT COUNT(*) FROM knowledge 
                WHERE is_current = 1 
                AND (answer LIKE '%"text":%' OR answer LIKE 'Ответ:%' OR answer LIKE '%"answer":%')
            ''')
            
            count = cursor.fetchone()[0]
            
            if count == 0:
                await update.message.reply_text("✅ Нет записей с JSON")
                conn.close()
                return
            
            await update.message.reply_text(f"Найдено записей с JSON: {count}\n\nИсправляю...")
            
            # Получаем все проблемные записи
            cursor.execute('''
                SELECT id, answer FROM knowledge 
                WHERE is_current = 1 
                AND (answer LIKE '%"text":%' OR answer LIKE 'Ответ:%' OR answer LIKE '%"answer":%')
            ''')
            
            records = cursor.fetchall()
            fixed = 0
            
            for rec_id, answer in records:
                try:
                    clean_answer = answer
                    
                    # Убираем "text": "..."
                    clean_answer = re.sub(r'"text"\s*:\s*"([^"]+)"', r'\1', clean_answer)
                    
                    # Убираем Ответ: "..."
                    clean_answer = re.sub(r'Ответ:\s*"([^"]+)"', r'\1', clean_answer)
                    
                    # Убираем "answer": "..."
                    clean_answer = re.sub(r'"answer"\s*:\s*"([^"]+)"', r'\1', clean_answer)
                    
                    # Убираем экранирование \n
                    clean_answer = clean_answer.replace('\\n', '\n')
                    
                    # Убираем экранирование \"
                    clean_answer = clean_answer.replace('\\"', '"')
                    
                    # Убираем лишние кавычки в начале/конце
                    clean_answer = clean_answer.strip('"')
                    
                    # Обновляем если изменилось
                    if clean_answer != answer:
                        cursor.execute('UPDATE knowledge SET answer = ? WHERE id = ?', (clean_answer, rec_id))
                        fixed += 1
                    
                    if fixed % 100 == 0 and fixed > 0:
                        conn.commit()
                        await update.message.reply_text(f"⏳ Исправлено: {fixed}/{len(records)}...")
                
                except Exception as e:
                    logger.error(f"Error fixing record {rec_id}: {e}")
            
            conn.commit()
            conn.close()
            
            await update.message.reply_text(f"✅ Исправлено: {fixed} из {count}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        text = update.message.text.replace('/learn', '').strip()
        
        if len(text) < 10:
            await update.message.reply_text("Напиши информацию после /learn")
            return
        
        try:
            kb_id = self.kb.add_smart(text, category='manual', added_by=update.effective_user.id)
            await update.message.reply_text(f"✅ Добавлено [ID: {kb_id}]")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
    
    async def cmd_import(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text("📥 Отправь .txt файл")
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        doc = update.message.document
        
        if not doc.file_name.endswith('.txt'):
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
                    
                    self.kb.add_smart(info, category='import', added_by=update.effective_user.id)
                    imported += 1
                except:
                    pass
            
            await update.message.reply_text(f"✅ Импортировано: {imported}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
    
    async def cmd_addadmin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.admin_manager.is_admin(update.effective_user.id):
            return
        
        try:
            new_admin_id = int(context.args[0])
            self.admin_manager.add_admin(new_admin_id, added_by=update.effective_user.id)
            await update.message.reply_text(f"✅ Админ: {new_admin_id}")
        except:
            await update.message.reply_text("/addadmin <user_id>")
    
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
            service, login, password = context.args[0], context.args[1], context.args[2]
            self.creds_manager.save(update.effective_user.id, service, login, password)
            await update.message.reply_text(f"✅ {service}")
            await update.message.delete()
        except:
            await update.message.reply_text("/savecreds <сервис> <логин> <пароль>")
    
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
        
        subprocess.Popen(['bash', '/opt/club_assistant/update.sh'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
    
    def _should_respond(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        message = update.message
        
        if message.chat.type == 'private':
            return True
        
        if message.reply_to_message:
            bot_id = context.bot.id if hasattr(context.bot, 'id') else None
            if bot_id and message.reply_to_message.from_user.id == bot_id:
                return True
        
        if message.text and self.bot_username and f"@{self.bot_username}" in message.text:
            return True
        
        if message.text and message.text.startswith('/'):
            return True
        
        return False
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        message = update.message
        text = message.text.strip()
        
        if len(text) < 3:
            return
        
        # Автообучение ТОЛЬКО в группах (не в личке!)
        if message.chat.type != 'private':
            try:
                self.smart_learner.learn_from_message(text, user.id)
            except Exception as e:
                logger.error(f"❌ Auto-learn error: {e}")
        
        # Проверяем нужно ли отвечать
        if not self._should_respond(update, context):
            return
        
        # Убираем упоминание
        question = text
        if self.bot_username and f"@{self.bot_username}" in question:
            question = question.replace(f"@{self.bot_username}", "").strip()
        
        await context.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        logger.info(f"❓ {user.username}: {question}")
        
        # RAG ответ
        answer, confidence, results, source_type = self.rag.answer_question(question)
        
        logger.info(f"✅ source={source_type}, conf={confidence:.2f}")
        
        # Метка
        if source_type == "knowledge_base":
            prefix = "📚 Из базы:\n\n"
        elif source_type == "partial":
            prefix = "🔍 Похожее:\n\n"
        elif source_type == "gpt":
            prefix = "🤖 GPT (нет в базе):\n\n"
        else:
            prefix = ""
        
        await message.reply_text(prefix + answer)
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        bot = await application.bot.get_me()
        self.bot_username = bot.username
        logger.info(f"✅ Bot: @{self.bot_username}")
    
    def run(self):
        app = Application.builder().token(self.config['telegram_token']).build()
        
        app.post_init = self.post_init
        
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("admin", self.cmd_admin))
        app.add_handler(CommandHandler("learn", self.cmd_learn))
        app.add_handler(CommandHandler("cleanup", self.cmd_cleanup))
        app.add_handler(CommandHandler("fixdb", self.cmd_fixdb))
        app.add_handler(CommandHandler("deletetrash", self.cmd_deletetrash))
        app.add_handler(CommandHandler("viewrecord", self.cmd_viewrecord))
        app.add_handler(CommandHandler("fixjson", self.cmd_fixjson))
        app.add_handler(CommandHandler("import", self.cmd_import))
        app.add_handler(CommandHandler("addadmin", self.cmd_addadmin))
        app.add_handler(CommandHandler("admins", self.cmd_admins))
        app.add_handler(CommandHandler("savecreds", self.cmd_savecreds))
        app.add_handler(CommandHandler("getcreds", self.cmd_getcreds))
        app.add_handler(CommandHandler("update", self.cmd_update))
        
        # V2Ray команды
        app.add_handler(CommandHandler("v2ray", self.v2ray_commands.cmd_v2ray))
        app.add_handler(CommandHandler("v2add", self.v2ray_commands.cmd_v2add))
        app.add_handler(CommandHandler("v2list", self.v2ray_commands.cmd_v2list))
        app.add_handler(CommandHandler("v2setup", self.v2ray_commands.cmd_v2setup))
        app.add_handler(CommandHandler("v2user", self.v2ray_commands.cmd_v2user))
        app.add_handler(CommandHandler("v2stats", self.v2ray_commands.cmd_v2stats))
        app.add_handler(CommandHandler("v2traffic", self.v2ray_commands.cmd_v2traffic))
        app.add_handler(CommandHandler("v2remove", self.v2ray_commands.cmd_v2remove))
        
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info(f"🤖 Бот v{VERSION} запущен!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ {CONFIG_PATH}")
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
    print("   Database Fix Edition")
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
