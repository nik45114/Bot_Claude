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

from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler
)
import openai

try:
    from embeddings import EmbeddingService
    from vector_store import VectorStore
    from draft_queue import DraftQueue
    from v2ray_manager import V2RayManager
    from v2ray_commands import V2RayCommands
    from club_manager import ClubManager
    from club_commands import ClubCommands, WAITING_REPORT
    from cash_manager import CashManager
    from cash_commands import CashCommands, CASH_SELECT_CLUB, CASH_SELECT_TYPE, CASH_ENTER_AMOUNT, CASH_ENTER_DESCRIPTION, CASH_ENTER_CATEGORY
    from product_manager import ProductManager
    from product_commands import ProductCommands, PRODUCT_ENTER_NAME, PRODUCT_ENTER_PRICE, PRODUCT_SELECT, PRODUCT_ENTER_QUANTITY
    from issue_manager import IssueManager
    from issue_commands import IssueCommands, ISSUE_SELECT_CLUB, ISSUE_ENTER_DESCRIPTION, ISSUE_EDIT_DESCRIPTION
except ImportError as e:
    print(f"❌ Не найдены модули v4.10: {e}")
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
        self.owner_id = owner_id  # Сохраняем для использования в других модулях
        self.v2ray_commands = V2RayCommands(self.v2ray_manager, self.admin_manager, owner_id)
        
        # Club Manager (только для владельца)
        self.club_manager = ClubManager(DB_PATH)
        self.club_commands = ClubCommands(self.club_manager, owner_id)
        
        # Cash Manager - финансовый мониторинг (только для владельца)
        self.cash_manager = CashManager(DB_PATH)
        self.cash_commands = None  # Будет инициализирован позже с bot_app
        
        # Product Manager - управление товарами (для владельца и админов)
        self.product_manager = ProductManager(DB_PATH)
        self.product_commands = None  # Будет инициализирован позже
        
        # Issue Manager - отслеживание проблем (для владельца и админов)
        self.issue_manager = IssueManager(DB_PATH)
        self.issue_commands = None  # Будет инициализирован позже с bot_app
        
        openai.api_key = config['openai_api_key']
        
        self.bot_username = None
        
        logger.info(f"✅ Бот v{VERSION} готов!")
        logger.info(f"   Векторов: {self.vector_store.stats()['total_vectors']}")
        logger.info(f"   Записей: {self.kb.count()}")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = self._get_main_menu_text()
        reply_markup = self._build_main_menu_keyboard(update.effective_user.id)
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = f"""📖 Справка - Club Assistant Bot v{VERSION}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Умное автообучение:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Автоматически запоминаю:
  • Проблемы и их решения
  • Инструкции по работе
  • Инциденты
  • Важную информацию о клубе

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 Как пользоваться:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• В личке: просто спрашивай
• В группе: @{self.bot_username or 'bot'} вопрос

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Команды:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/start - начало работы
/help - эта справка
/stats - статистика базы знаний"""

        if self.admin_manager.is_admin(update.effective_user.id):
            text += "\n\n🔧 /admin - админ-панель"
            text += "\n🔐 /v2ray - управление VPN"

        await update.message.reply_text(text)
    
    def _get_help_text(self) -> str:
        """Получить текст справки"""
        text = f"""📖 Справка - Club Assistant Bot v{VERSION}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Умное автообучение:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Автоматически запоминаю:
  • Проблемы и их решения
  • Инструкции по работе
  • Инциденты
  • Важную информацию о клубе

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 Как пользоваться:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• В личке: просто спрашивай
• В группе: @{self.bot_username or 'bot'} вопрос

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Команды:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/start - начало работы
/help - эта справка
/stats - статистика базы знаний"""
        return text
    
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
    
    async def _perform_bot_update(self) -> Tuple[bool, str]:
        """
        Выполнить обновление бота из GitHub.
        
        Returns:
            Tuple[bool, str]: (success, message) - успех операции и сообщение для пользователя
        
        Возможные сценарии ошибок:
        - Git fetch failed: Ошибка при проверке обновлений (network/git issues)
        - Git rev-list failed: Ошибка при подсчёте коммитов
        - Commit count parsing: Ошибка при обработке количества коммитов (invalid output)
        - Git pull failed: Ошибка при загрузке обновлений
        - Timeout: Превышено время ожидания операции (>30 sec)
        - General exception: Общая ошибка обновления
        
        Успешные сценарии:
        - No updates: "Бот уже использует последнюю версию"
        - Updates applied: "Обновления загружены (N коммитов)"
        """
        try:
            work_dir = '/opt/club_assistant'
            
            # Fetch обновлений
            logger.info("📥 Fetching updates from GitHub...")
            result = subprocess.run(
                ['git', 'fetch', 'origin', 'main'],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"❌ Git fetch failed: {result.stderr}")
                return False, f"❌ Ошибка при проверке обновлений:\n{result.stderr}"
            
            # Проверяем количество новых коммитов
            logger.info("🔍 Checking for new commits...")
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD..origin/main'],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"❌ Git rev-list failed: {result.stderr}")
                return False, "❌ Ошибка при подсчёте коммитов"
            
            try:
                commits_count = int(result.stdout.strip())
            except ValueError as e:
                logger.error(f"❌ Failed to parse commit count: '{result.stdout.strip()}' - {e}")
                return False, f'❌ Ошибка при обработке количества коммитов: "{result.stdout.strip()}"'
            
            logger.info(f"📊 Found {commits_count} new commits")
            
            if commits_count == 0:
                return True, "✅ Бот уже использует последнюю версию"
            
            # Pull обновлений
            logger.info("📥 Pulling updates...")
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"❌ Git pull failed: {result.stderr}")
                return False, f"❌ Ошибка при загрузке обновлений:\n{result.stderr}"
            
            logger.info("✅ Updates pulled successfully")
            
            # Перезапуск сервиса (асинхронно через Popen)
            logger.info("🔄 Restarting service...")
            subprocess.Popen(
                ['systemctl', 'restart', 'club_assistant.service'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            logger.info("✅ Update completed, restart initiated")
            return True, f"✅ Обновления загружены ({commits_count} коммитов)\n🔄 Бот перезапускается..."
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Git command timeout")
            return False, "❌ Превышено время ожидания операции"
        except Exception as e:
            logger.error(f"❌ Update failed: {e}", exc_info=True)
            return False, f"❌ Ошибка обновления:\n{str(e)}"
    
    async def cmd_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Автообновление бота из GitHub"""
        if not self.admin_manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        
        logger.info(f"🔄 Update requested by user {update.effective_user.id}")
        await update.message.reply_text("🔄 Проверяю наличие обновлений...")
        
        success, message = await self._perform_bot_update()
        await update.message.reply_text(message)
    
    def _build_main_menu_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Построить клавиатуру главного меню"""
        keyboard = []
        keyboard.append([InlineKeyboardButton("📖 Справка", callback_data="help")])
        keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="stats")])
        
        if self.admin_manager.is_admin(user_id):
            keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="admin")])
            keyboard.append([InlineKeyboardButton("🔐 V2Ray VPN", callback_data="v2ray")])
            keyboard.append([InlineKeyboardButton("📦 Управление товарами", callback_data="product_menu")])
            keyboard.append([InlineKeyboardButton("⚠️ Проблемы клуба", callback_data="issue_menu")])
        
        # Финансовый мониторинг только для владельца
        if user_id == self.owner_id:
            keyboard.append([InlineKeyboardButton("💰 Финансовый мониторинг", callback_data="cash_menu")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _get_main_menu_text(self) -> str:
        """Получить текст главного меню"""
        return f"""👋 Привет!

Я ассистент клуба v{VERSION}.

🤖 Запоминаю только важное:
• Проблемы и решения
• Инструкции
• Инциденты
• Важную информацию о клубе

💬 В личке: просто спрашивай
💬 В группе: @{self.bot_username or 'bot'} вопрос"""
    
    def _get_v2ray_menu_text(self) -> str:
        """Получить текст меню V2Ray"""
        return """🔐 V2Ray Manager (REALITY)

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Системные требования:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • ОС: Debian/Ubuntu Linux
  • Python: 3.8+
  • Требуется: SSH доступ с root

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 REALITY маскировка:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• По умолчанию: rutube.ru
• Доступны: youtube.com, yandex.ru"""
    
    def _build_v2ray_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Построить клавиатуру меню V2Ray"""
        keyboard = [
            [InlineKeyboardButton("📡 Серверы", callback_data="v2_servers")],
            [InlineKeyboardButton("👤 Пользователи", callback_data="v2_users")],
            [InlineKeyboardButton("📖 Справка по командам", callback_data="v2_help")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик inline-кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Главное меню
        if data == "main_menu":
            text = self._get_main_menu_text()
            reply_markup = self._build_main_menu_keyboard(query.from_user.id)
            await query.edit_message_text(text, reply_markup=reply_markup)
            return
        
        # Справка
        if data == "help":
            help_text = self._get_help_text()
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
            await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # Статистика
        if data == "stats":
            kb_count = self.kb.count()
            vector_stats = self.vector_store.stats()
            text = f"""📊 Статистика v{VERSION}

📚 База знаний:
• Записей: {kb_count}
• Векторов: {vector_stats['total_vectors']}

🤖 Умное автообучение: ВКЛ"""
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # Админ-панель
        if data == "admin":
            if not self.admin_manager.is_admin(query.from_user.id):
                await query.answer("❌ Только для админов")
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
/addadmin <id>"""
            
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить бота", callback_data="admin_update")],
                [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # V2Ray меню (обрабатывает и "v2ray" и "v2ray_menu")
        if data in ("v2ray", "v2ray_menu"):
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            text = self._get_v2ray_menu_text()
            reply_markup = self._build_v2ray_menu_keyboard()
            await query.edit_message_text(text, reply_markup=reply_markup)
            return
        
        # === НОВЫЕ МОДУЛИ ===
        
        # Финансовый мониторинг
        if data == "cash_menu":
            await self.cash_commands.show_cash_menu(update, context)
            return
        
        if data == "cash_balances":
            await self.cash_commands.show_balances(update, context)
            return
        
        if data == "cash_movements":
            await self.cash_commands.show_movements(update, context)
            return
        
        if data.startswith("cash_movements_"):
            await self.cash_commands.show_movements_club(update, context)
            return
        
        if data in ("cash_add_income", "cash_add_expense"):
            # Эти обрабатываются через conversation handler
            return
        
        if data == "cash_monthly":
            await self.cash_commands.show_monthly_summary(update, context)
            return
        
        if data.startswith("cash_month_"):
            await self.cash_commands.show_monthly_club(update, context)
            return
        
        # Управление товарами
        if data == "product_menu":
            await self.product_commands.show_product_menu(update, context)
            return
        
        if data == "product_my_debt":
            await self.product_commands.show_my_debt(update, context)
            return
        
        if data == "product_all_debts":
            await self.product_commands.show_all_debts(update, context)
            return
        
        if data == "product_report":
            await self.product_commands.show_products_report(update, context)
            return
        
        if data == "product_clear_settled":
            await self.product_commands.clear_settled_products(update, context)
            return
        
        if data == "product_clear_all_confirm":
            await self.product_commands.clear_all_debts_confirm(update, context)
            return
        
        if data == "product_clear_all_execute":
            await self.product_commands.clear_all_debts_execute(update, context)
            return
        
        if data.startswith("product_clear_") and data != "product_clear_settled":
            await self.product_commands.clear_admin_debt(update, context)
            return
        
        # Проблемы клуба
        if data == "issue_menu":
            await self.issue_commands.show_issue_menu(update, context)
            return
        
        if data == "issue_list":
            await self.issue_commands.show_issues_list(update, context)
            return
        
        if data.startswith("issue_filter_"):
            await self.issue_commands.show_filtered_issues(update, context)
            return
        
        if data == "issue_current":
            await self.issue_commands.show_current_issues(update, context)
            return
        
        if data.startswith("issue_manage_"):
            await self.issue_commands.manage_issue(update, context)
            return
        
        if data.startswith("issue_resolve_"):
            await self.issue_commands.resolve_issue(update, context)
            return
        
        if data.startswith("issue_delete_"):
            await self.issue_commands.delete_issue(update, context)
            return
        
        # === КОНЕЦ НОВЫХ МОДУЛЕЙ ===
        
        # Админ - обновление бота через кнопку
        if data == "admin_update":
            if not self.admin_manager.is_admin(query.from_user.id):
                await query.answer("❌ Только для админов")
                return
            
            logger.info(f"🔄 Bot update via button by user {query.from_user.id}")
            await query.answer("🔄 Начинаю обновление...")
            await query.edit_message_text("🔄 Проверяю наличие обновлений...")
            
            success, message = await self._perform_bot_update()
            await query.edit_message_text(message)
            return
        
        # V2Ray подменю
        if data == "v2_servers":
            await self._show_v2_servers_menu(query)
            return
        
        if data == "v2_users":
            await self._show_v2_users_menu(query)
            return
        
        if data == "v2_help":
            await self._show_v2_help_menu(query)
            return
        
        # V2Ray - детали сервера
        if data.startswith("v2server_"):
            server_name = data.replace("v2server_", "")
            await self._show_v2_server_details(query, server_name)
            return
        
        # V2Ray - установка Xray
        if data.startswith("v2setup_"):
            server_name = data.replace("v2setup_", "")
            await self._install_xray_async(query, server_name)
            return
        
        # V2Ray - диагностика сервера
        if data.startswith("v2diag_"):
            server_name = data.replace("v2diag_", "")
            await self._diagnose_server(query, server_name)
            return
        
        # V2Ray - статистика сервера
        if data.startswith("v2stats_"):
            server_name = data.replace("v2stats_", "")
            await self._show_v2_server_stats(query, server_name)
            return
        
        # Список пользователей сервера
        if data.startswith("v2users_"):
            server_name = data.replace("v2users_", "")
            await self._show_server_users(query, server_name)
            return
        
        # Добавление пользователя через кнопку
        if data.startswith("v2adduser_"):
            server_name = data.replace("v2adduser_", "")
            await query.edit_message_text(
                f"➕ Добавление пользователя на {server_name}\n\n"
                f"Используйте команду:\n"
                f"/v2user {server_name} <ID> <комментарий>\n\n"
                f"Пример:\n"
                f"/v2user {server_name} 1 Nikita"
            )
            return
        
        # Удаление пользователя
        if data.startswith("v2deluser_"):
            parts = data.replace("v2deluser_", "").split("_")
            server_name = parts[0]
            uuid = parts[1]
            await self._delete_user(query, server_name, uuid)
            return
        
        # Удаление сервера - подтверждение
        if data.startswith("v2delete_confirm_"):
            server_name = data.replace("v2delete_confirm_", "")
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            logger.info(f"🗑️ Deleting server {server_name}...")
            if self.v2ray_manager.delete_server(server_name):
                await query.edit_message_text(
                    f"✅ Сервер {server_name} удалён!\n\n"
                    f"Данные очищены из БД.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К серверам", callback_data="v2_servers")
                    ]])
                )
            else:
                await query.edit_message_text(
                    "❌ Ошибка при удалении сервера",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К серверам", callback_data="v2_servers")
                    ]])
                )
            return
        
        # Удаление сервера
        if data.startswith("v2delete_"):
            server_name = data.replace("v2delete_", "")
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            # Подтверждение удаления
            keyboard = [
                [InlineKeyboardButton("✅ Да, удалить", callback_data=f"v2delete_confirm_{server_name}")],
                [InlineKeyboardButton("❌ Отмена", callback_data=f"v2server_{server_name}")]
            ]
            await query.edit_message_text(
                f"⚠️ Удалить сервер {server_name}?\n\n"
                f"Будут удалены:\n"
                f"• Сервер из списка\n"
                f"• Все пользователи сервера из БД\n\n"
                f"❗ Конфиг на сервере НЕ удаляется",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Изменение SNI
        if data.startswith("v2changesni_"):
            parts = data.replace("v2changesni_", "").split("_")
            server_name = parts[0]
            user_id = parts[1]
            
            # Сохраняем в контексте
            context.user_data['change_sni'] = {'server': server_name, 'user_id': user_id}
            
            await query.edit_message_text(
                f"🌐 Изменение SNI для пользователя {user_id}\n\n"
                f"Текущий SNI: rutube.ru\n\n"
                f"Введите новый SNI (например: youtube.com, yandex.ru):"
            )
            return
    
    async def _show_v2_servers_menu(self, query):
        """Меню управления серверами"""
        servers = self.v2ray_manager.list_servers()
        
        text = "📡 Управление серверами\n\n"
        
        if servers:
            text += "Ваши серверы:\n\n"
            for srv in servers:
                text += f"🖥️ {srv['name']} - {srv['host']}\n"
        else:
            text += "Нет добавленных серверов\n\n"
            text += "Добавьте сервер командой:\n"
            text += "/v2add <имя> <host> <user> <pass> [sni]"
        
        keyboard = []
        for srv in servers:
            keyboard.append([
                InlineKeyboardButton(f"⚙️ {srv['name']}", callback_data=f"v2server_{srv['name']}")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="v2ray")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def _show_v2_users_menu(self, query):
        """Меню управления пользователями"""
        text = """👤 Управление пользователями

Добавить пользователя:
/v2user <сервер> <user_id> [email]

Удалить пользователя:
/v2remove <сервер> <uuid>"""
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="v2ray")]]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def _show_v2_help_menu(self, query):
        """Справка по командам V2Ray"""
        text = """📖 Справка по командам V2Ray

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 Управление серверами:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/v2add <имя> <host> <user> <pass> [sni]
  └─ Добавить новый сервер
  
/v2list
  └─ Список всех серверов
  
/v2setup <имя>
  └─ Установить Xray на сервер
  
/v2stats <имя>
  └─ Статистика сервера

━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Управление пользователями:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/v2user <сервер> <user_id> [email]
  └─ Добавить пользователя
  
/v2remove <сервер> <uuid>
  └─ Удалить пользователя

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ Настройки:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/v2sni <сервер> <сайт>
  └─ Изменить маскировку

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Пример использования:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ /v2add main 192.168.1.100 root Pass123
2️⃣ /v2setup main
3️⃣ /v2user main @username Иван
4️⃣ /v2sni main youtube.com"""
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="v2ray")]]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def _show_v2_server_details(self, query, server_name: str):
        """Показать детали конкретного сервера"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            logger.info(f"📋 Showing details for server: {server_name}")
            
            servers = self.v2ray_manager.list_servers()
            server_info = next((s for s in servers if s['name'] == server_name), None)
            
            if not server_info:
                await query.answer("❌ Сервер не найден")
                return
            
            # Получаем ключи сервера
            server_keys = self.v2ray_manager.get_server_keys(server_name)
            
            text = f"""🖥️ Сервер: {server_name}
            
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Информация:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Host: {server_info['host']}
🔌 Port: {server_info['port']}
👤 User: {server_info['username']}
🌐 SNI: {server_info.get('sni', 'rutube.ru')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 REALITY ключи:
━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            
            if server_keys:
                public_key = server_keys.get('public_key', 'не установлен')
                if public_key and public_key != 'не установлен':
                    text += f"\n🔑 Public Key: `{public_key[:32]}...`"
                else:
                    text += f"\n🔑 Public Key: `{public_key}`"
                text += f"\n🆔 Short ID: `{server_keys.get('short_id', 'не установлен')}`"
            else:
                text += "\n⚠️ Xray не установлен"
            
            keyboard = [
                [InlineKeyboardButton("👥 Пользователи", callback_data=f"v2users_{server_name}")],
                [InlineKeyboardButton("➕ Добавить", callback_data=f"v2adduser_{server_name}")],
                [InlineKeyboardButton("🔧 Установить Xray", callback_data=f"v2setup_{server_name}")],
                [InlineKeyboardButton("🔍 Диагностика", callback_data=f"v2diag_{server_name}")],
                [InlineKeyboardButton("📊 Статистика", callback_data=f"v2stats_{server_name}")],
                [InlineKeyboardButton("🗑️ Удалить сервер", callback_data=f"v2delete_{server_name}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="v2_servers")]
            ]
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Error showing server details: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    async def _install_xray_async(self, query, server_name: str):
        """Асинхронная установка Xray на сервер"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            logger.info(f"🔧 Installing Xray on server: {server_name}")
            await query.answer("⏳ Начинаю установку...")
            await query.edit_message_text(f"⏳ Подключаюсь к серверу {server_name}...")
            
            server = self.v2ray_manager.get_server(server_name)
            
            if not server:
                await query.edit_message_text(f"❌ Сервер {server_name} не найден")
                return
            
            if not server.connect():
                await query.edit_message_text("❌ Не удалось подключиться к серверу")
                return
            
            await query.edit_message_text("📥 Устанавливаю Xray (2-3 минуты)...\nПожалуйста, подождите...")
            
            if not server.install_v2ray():
                await query.edit_message_text("❌ Ошибка установки Xray")
                server.disconnect()
                return
            
            await query.edit_message_text("⚙️ Создаю REALITY конфигурацию...")
            
            # Получаем SNI из базы
            server_keys = self.v2ray_manager.get_server_keys(server_name)
            sni = server_keys.get('sni', 'rutube.ru')
            
            config = server.create_reality_config(port=443, sni=sni)
            
            if not config:
                await query.edit_message_text("❌ Ошибка создания конфигурации")
                server.disconnect()
                return
            
            # Сохраняем ключи в базу
            client_keys = config.get('_client_keys', {})
            if client_keys:
                self.v2ray_manager.save_server_keys(
                    server_name,
                    client_keys['public_key'],
                    client_keys['short_id'],
                    client_keys.get('private_key', '')
                )
            
            if not server.deploy_config(config):
                await query.edit_message_text("❌ Ошибка применения конфигурации")
                server.disconnect()
                return
            
            server.disconnect()
            
            text = f"""✅ Xray успешно установлен на {server_name}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 Настройки:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 Протокол: REALITY
🌐 Маскировка: {sni}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Следующий шаг:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Добавьте пользователей:
/v2user {server_name} <user_id> [email]"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Статистика", callback_data=f"v2stats_{server_name}")],
                [InlineKeyboardButton("◀️ К серверу", callback_data=f"v2server_{server_name}")]
            ]
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            logger.info(f"✅ Xray installed successfully on {server_name}")
            
        except Exception as e:
            logger.error(f"❌ Error installing Xray: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка установки: {str(e)}")
    
    async def _diagnose_server(self, query, server_name: str):
        """Диагностика сервера и исправление проблем"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            await query.edit_message_text(f"🔍 Диагностика сервера {server_name}...\n\nПроверяю конфигурацию...")
            
            # Получаем информацию о сервере
            server_info = self.v2ray_manager.get_server_info(server_name)
            
            if not server_info:
                await query.edit_message_text(f"❌ Сервер {server_name} не найден в БД")
                return
            
            issues = []
            fixes_applied = []
            
            # Проверка 1: Наличие public_key
            if not server_info.get('public_key'):
                issues.append("❌ Отсутствует Public Key")
            else:
                issues.append(f"✅ Public Key: {server_info['public_key'][:20]}...")
            
            # Проверка 2: Наличие short_id
            if not server_info.get('short_id'):
                issues.append("❌ Отсутствует Short ID")
            else:
                issues.append(f"✅ Short ID: {server_info['short_id']}")
            
            # Проверка 3: Xray запущен на сервере
            logger.info(f"🔍 Checking if Xray is running on {server_name}...")
            xray_status = self.v2ray_manager.check_xray_status(server_name)
            
            if xray_status:
                issues.append("✅ Xray запущен")
            else:
                issues.append("❌ Xray не запущен или недоступен")
            
            # Проверка 4: Ключи на сервере
            keys_on_server = self.v2ray_manager.get_keys_from_server(server_name)
            
            if keys_on_server:
                issues.append("✅ Ключи найдены на сервере")
                
                # Если ключей нет в БД, но есть на сервере - сохраняем
                if not server_info.get('public_key') and keys_on_server.get('public_key'):
                    result = self.v2ray_manager.save_keys_to_db(
                        server_name, 
                        keys_on_server['public_key'],
                        keys_on_server.get('private_key', ''),
                        keys_on_server.get('short_id', '')
                    )
                    if result:
                        fixes_applied.append("✅ Ключи сохранены в БД")
                        issues.append(f"✅ Public Key: {keys_on_server['public_key'][:20]}...")
                        issues.append(f"✅ Short ID: {keys_on_server.get('short_id', 'N/A')}")
            else:
                issues.append("❌ Ключи не найдены на сервере")
            
            # Формируем отчет
            text = f"🔍 Диагностика {server_name}\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "📋 Результаты проверки:\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            text += "\n".join(issues)
            
            if fixes_applied:
                text += "\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
                text += "🔧 Исправления:\n"
                text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                text += "\n".join(fixes_applied)
                text += "\n\n✅ Проблемы исправлены!"
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"v2server_{server_name}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Diagnose error: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка диагностики: {e}")
    
    async def _show_v2_server_stats(self, query, server_name: str):
        """Показать статистику сервера"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            logger.info(f"📊 Getting stats for server: {server_name}")
            await query.answer("⏳ Получаю статистику...")
            await query.edit_message_text("⏳ Подключаюсь к серверу...")
            
            server = self.v2ray_manager.get_server(server_name)
            
            if not server:
                await query.edit_message_text(f"❌ Сервер {server_name} не найден")
                return
            
            if not server.connect():
                await query.edit_message_text("❌ Не удалось подключиться")
                return
            
            stats = server.get_stats()
            
            server.disconnect()
            
            if not stats:
                await query.edit_message_text("❌ Ошибка получения статистики")
                return
            
            status_emoji = "✅" if stats['running'] else "❌"
            status_text = "🟢 Работает" if stats['running'] else "🔴 Остановлен"
            
            text = f"""📊 Статистика сервера: {server_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Состояние:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{status_emoji} Статус: {status_text}
📍 Host: {stats['host']}
🔌 Port: {stats['port']}
🔐 Protocol: {stats['protocol']}
🌐 SNI: {stats['sni']}
👥 Пользователей: {stats['users']}"""
            
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data=f"v2stats_{server_name}")],
                [InlineKeyboardButton("◀️ К серверу", callback_data=f"v2server_{server_name}")]
            ]
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            logger.info(f"✅ Stats shown for {server_name}")
            
        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка: {str(e)}")
    
    async def _show_server_users(self, query, server_name: str):
        """Показать список пользователей сервера"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            users = self.v2ray_manager.get_server_users(server_name)
            
            text = f"👥 Пользователи сервера {server_name}\n\n"
            
            if users:
                text += f"Всего: {len(users)}\n\n"
                for user in users:
                    text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    text += f"👤 {user['comment']}\n"
                    text += f"🆔 ID: {user['user_id']}\n"
                    text += f"🔑 UUID: {user['uuid'][:8]}...\n"
                    text += f"🌐 SNI: {user.get('sni', 'rutube.ru')}\n"
            else:
                text += "Нет пользователей\n"
            
            keyboard = []
            
            for user in users[:10]:  # Максимум 10 кнопок
                keyboard.append([
                    InlineKeyboardButton(
                        f"🗑️ {user['comment']}", 
                        callback_data=f"v2deluser_{server_name}_{user['uuid']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("➕ Добавить", callback_data=f"v2adduser_{server_name}"),
                InlineKeyboardButton("◀️ Назад", callback_data=f"v2server_{server_name}")
            ])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Error showing server users: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    async def _delete_user(self, query, server_name: str, uuid: str):
        """Удалить пользователя"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            result = self.v2ray_manager.delete_user(server_name, uuid)
            
            if result:
                text = f"✅ Пользователь удалён"
            else:
                text = f"❌ Ошибка удаления пользователя"
            
            keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data=f"v2users_{server_name}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Error deleting user: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    
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
        
        # IssueCommands теперь инициализируется в run() сразу после создания Application
        # self.issue_commands = IssueCommands(self.issue_manager, self.kb, self.admin_manager, self.owner_id, application)
    
    def run(self):
        """Запуск бота"""
        logger.info("🤖 Запуск бота...")
        
        # 1. Инициализация команд ПЕРЕД созданием Application
        # CashCommands и ProductCommands не требуют bot_app, инициализируем их сразу
        logger.info("Инициализация команд...")
        
        try:
            self.cash_commands = CashCommands(self.cash_manager, self.owner_id)
            logger.info("✅ CashCommands инициализированы")
        except Exception as e:
            logger.error(f"❌ Ошибка при инициализации CashCommands: {e}")
            raise
        
        try:
            self.product_commands = ProductCommands(self.product_manager, self.admin_manager, self.owner_id)
            logger.info("✅ ProductCommands инициализированы")
        except Exception as e:
            logger.error(f"❌ Ошибка при инициализации ProductCommands: {e}")
            raise
        
        # 2. Создание Application
        application = Application.builder().token(self.config['telegram_token']).build()
        logger.info("✅ Application создан")
        
        # 3. Инициализируем IssueCommands (требует application)
        self.issue_commands = IssueCommands(self.issue_manager, self.kb, self.admin_manager, self.owner_id, application)
        logger.info("✅ IssueCommands инициализированы")
        
        application.post_init = self.post_init
        
        # 4. Регистрируем обработчики
        application.add_handler(CommandHandler("start", self.cmd_start))
        application.add_handler(CommandHandler("help", self.cmd_help))
        application.add_handler(CommandHandler("stats", self.cmd_stats))
        application.add_handler(CommandHandler("admin", self.cmd_admin))
        application.add_handler(CommandHandler("learn", self.cmd_learn))
        application.add_handler(CommandHandler("cleanup", self.cmd_cleanup))
        application.add_handler(CommandHandler("fixdb", self.cmd_fixdb))
        application.add_handler(CommandHandler("deletetrash", self.cmd_deletetrash))
        application.add_handler(CommandHandler("viewrecord", self.cmd_viewrecord))
        application.add_handler(CommandHandler("fixjson", self.cmd_fixjson))
        application.add_handler(CommandHandler("import", self.cmd_import))
        application.add_handler(CommandHandler("addadmin", self.cmd_addadmin))
        application.add_handler(CommandHandler("admins", self.cmd_admins))
        application.add_handler(CommandHandler("savecreds", self.cmd_savecreds))
        application.add_handler(CommandHandler("getcreds", self.cmd_getcreds))
        application.add_handler(CommandHandler("update", self.cmd_update))
        
        # Обработчик inline-кнопок
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # V2Ray команды
        application.add_handler(CommandHandler("v2ray", self.v2ray_commands.cmd_v2ray))
        application.add_handler(CommandHandler("v2add", self.v2ray_commands.cmd_v2add))
        application.add_handler(CommandHandler("v2list", self.v2ray_commands.cmd_v2list))
        application.add_handler(CommandHandler("v2setup", self.v2ray_commands.cmd_v2setup))
        application.add_handler(CommandHandler("v2user", self.v2ray_commands.cmd_v2user))
        application.add_handler(CommandHandler("v2stats", self.v2ray_commands.cmd_v2stats))
        application.add_handler(CommandHandler("v2traffic", self.v2ray_commands.cmd_v2traffic))
        application.add_handler(CommandHandler("v2remove", self.v2ray_commands.cmd_v2remove))
        
        # Club команды
        application.add_handler(CommandHandler("clubs", self.club_commands.cmd_clubs))
        application.add_handler(CommandHandler("clubadd", self.club_commands.cmd_clubadd))
        application.add_handler(CommandHandler("clublist", self.club_commands.cmd_clublist))
        application.add_handler(CommandHandler("lastreport", self.club_commands.cmd_lastreport))
        application.add_handler(CommandHandler("clubstats", self.club_commands.cmd_clubstats))
        application.add_handler(CommandHandler("issues", self.club_commands.cmd_issues))
        
        # ConversationHandler для отчётов
        report_handler = ConversationHandler(
            entry_points=[CommandHandler("report", self.club_commands.cmd_report)],
            states={
                WAITING_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.club_commands.handle_report_text)]
            },
            fallbacks=[CommandHandler("cancel", self.club_commands.cmd_cancel)]
        )
        application.add_handler(report_handler)
        
        # === НОВЫЕ CONVERSATION HANDLERS ===
        
        # ConversationHandler для финансового мониторинга
        cash_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.cash_commands.start_add_movement, pattern="^cash_add_(income|expense)$")
            ],
            states={
                CASH_SELECT_CLUB: [CallbackQueryHandler(self.cash_commands.select_club, pattern="^cash_club_")],
                CASH_SELECT_TYPE: [CallbackQueryHandler(self.cash_commands.select_type, pattern="^cash_type_")],
                CASH_ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.cash_commands.enter_amount)],
                CASH_ENTER_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.cash_commands.enter_description)],
                CASH_ENTER_CATEGORY: [CallbackQueryHandler(self.cash_commands.select_category, pattern="^cash_cat_")]
            },
            fallbacks=[CallbackQueryHandler(self.cash_commands.cancel, pattern="^cash_menu$")]
        )
        application.add_handler(cash_handler)
        
        # ConversationHandler для добавления товара
        product_add_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.product_commands.start_add_product, pattern="^product_add$")
            ],
            states={
                PRODUCT_ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.product_commands.enter_product_name)],
                PRODUCT_ENTER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.product_commands.enter_product_price)]
            },
            fallbacks=[CallbackQueryHandler(self.product_commands.cancel, pattern="^product_menu$")]
        )
        application.add_handler(product_add_handler)
        
        # ConversationHandler для взятия товара админом
        product_take_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.product_commands.start_take_product, pattern="^product_take$")
            ],
            states={
                PRODUCT_SELECT: [CallbackQueryHandler(self.product_commands.select_product, pattern="^product_select_")],
                PRODUCT_ENTER_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.product_commands.enter_quantity)]
            },
            fallbacks=[CallbackQueryHandler(self.product_commands.cancel, pattern="^product_menu$")]
        )
        application.add_handler(product_take_handler)
        
        # ConversationHandler для обнуления долга (кнопка выбора админа)
        product_clear_debt_handler = CallbackQueryHandler(self.product_commands.start_clear_debt, pattern="^product_clear_debt$")
        application.add_handler(product_clear_debt_handler)
        
        # ConversationHandler для изменения цены товара
        product_edit_price_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.product_commands.start_edit_price, pattern="^product_edit_price$")
            ],
            states={
                PRODUCT_EDIT_PRICE: [CallbackQueryHandler(self.product_commands.select_product_for_price_edit, pattern="^product_price_")],
                PRODUCT_ENTER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.product_commands.enter_new_product_price)]
            },
            fallbacks=[CallbackQueryHandler(self.product_commands.cancel, pattern="^product_menu$")]
        )
        application.add_handler(product_edit_price_handler)
        
        # ConversationHandler для сообщения о проблеме
        issue_report_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.issue_commands.start_report_issue, pattern="^issue_report$")
            ],
            states={
                ISSUE_SELECT_CLUB: [CallbackQueryHandler(self.issue_commands.select_club_for_issue, pattern="^issue_club_")],
                ISSUE_ENTER_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.issue_commands.enter_issue_description)]
            },
            fallbacks=[CallbackQueryHandler(self.issue_commands.cancel, pattern="^issue_menu$")]
        )
        application.add_handler(issue_report_handler)
        
        # ConversationHandler для редактирования проблемы
        issue_edit_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.issue_commands.start_edit_issue, pattern="^issue_edit_")
            ],
            states={
                ISSUE_EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.issue_commands.edit_issue_description)]
            },
            fallbacks=[CallbackQueryHandler(self.issue_commands.cancel, pattern="^issue_current$")]
        )
        application.add_handler(issue_edit_handler)
        
        # === КОНЕЦ НОВЫХ HANDLERS ===
        
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info(f"🤖 Бот v{VERSION} запущен!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


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
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS club_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        club_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cash_fact REAL DEFAULT 0,
        cash_in_safe REAL DEFAULT 0,
        cashless_fact REAL DEFAULT 0,
        qr_payment REAL DEFAULT 0,
        cashless_new_register REAL DEFAULT 0,
        cash_products REAL DEFAULT 0,
        cash_in_box REAL DEFAULT 0,
        joysticks_total INTEGER DEFAULT 0,
        joysticks_in_repair INTEGER DEFAULT 0,
        joysticks_need_repair INTEGER DEFAULT 0,
        games_count INTEGER DEFAULT 0,
        toilet_supplies BOOLEAN DEFAULT 0,
        paper_towels BOOLEAN DEFAULT 0,
        notes TEXT,
        FOREIGN KEY (club_id) REFERENCES clubs(id),
        FOREIGN KEY (user_id) REFERENCES admins(user_id))''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_club_reports_date ON club_reports(club_id, report_date DESC)')
    
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
