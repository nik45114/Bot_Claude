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
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import base64
import subprocess

# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))

def get_msk_now():
    """Получить текущее время в московском часовом поясе"""
    return datetime.now(MSK)

def get_msk_today():
    """Получить сегодняшнюю дату по московскому времени"""
    return get_msk_now().date()

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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
    from product_manager import ProductManager
    from product_commands import ProductCommands, PRODUCT_ENTER_NAME, PRODUCT_ENTER_PRICE, PRODUCT_SELECT, PRODUCT_ENTER_QUANTITY, PRODUCT_EDIT_PRICE, PRODUCT_SET_NICKNAME
    from issue_manager import IssueManager
    from issue_commands import IssueCommands, ISSUE_SELECT_CLUB, ISSUE_ENTER_DESCRIPTION, ISSUE_EDIT_DESCRIPTION
    from content_generator import ContentGenerator
    from content_commands import ContentCommands
    # from modules.finmon import register_finmon  # Временно отключено - модуль в разработке
    from modules.admins import register_admins
    # Улучшенные модули управления админами и сменами
    from modules.enhanced_admin_shift_integration import register_enhanced_admin_shift_management
    from modules.backup_commands import register_backup_commands
    # Accounting receipts and invoices
    from modules.accounting_receipts import (
        AccountingReceipts,
        RECEIPT_ENTER_QR, RECEIPT_ENTER_CATEGORY, RECEIPT_CONFIRM,
        INVOICE_ENTER_SUPPLIER, INVOICE_ENTER_AMOUNT, INVOICE_UPLOAD_PHOTO, INVOICE_ENTER_DESCRIPTION, INVOICE_CONFIRM,
        start_send_receipt, receipt_enter_qr, receipt_select_category, receipt_confirm,
        start_send_invoice, invoice_enter_supplier, invoice_enter_amount, invoice_upload_photo, invoice_enter_description, invoice_confirm,
        cancel_operation
    )
    # Shift checklist and controller panel
    from modules.shift_checklist import create_checklist_conversation_handler, ShiftChecklistManager
    # controller_panel импортируется локально в handle_callback при необходимости
    # New shift checklists (cleaning rating, cleaning service reviews, inventory)
    from modules.shift_cleaning_rating import create_cleaning_rating_handlers
    from modules.cleaning_service_reviews import create_cleaning_review_handlers
    from modules.shift_inventory_checklist import create_inventory_handlers
    # Shift reminders system
    from modules.shift_reminders import setup_reminder_jobs
    # Duty shift manager
    from modules.duty_shift_manager import create_duty_shift_handlers, show_duty_shift_menu
    # Maintenance tasks
    from modules.maintenance_commands import create_maintenance_handlers, show_maintenance_tasks
except ImportError as e:
    print(f"Ошибка: Не найдены модули v4.15: {e}")
    sys.exit(1)

CONFIG_PATH = 'config.json'
DB_PATH = 'knowledge.db'

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

VERSION = "4.20"


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

    def has_permission(self, user_id: int, permission: str) -> bool:
        """Check if user has specific permission"""
        try:
            # Import AdminDB для проверки прав
            from modules.admins.db import AdminDB
            admin_db = AdminDB(self.db_path)
            return admin_db.has_permission(user_id, permission)
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
    
    def set_full_name(self, user_id: int, full_name: str) -> bool:
        """Set admin's full name"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE admins SET full_name = ? WHERE user_id = ?', (full_name, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error setting full name: {e}")
            return False
    
    def get_display_name(self, user_id: int) -> str:
        """Get display name with priority: full_name > username > user_id"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT full_name, username FROM admins WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                full_name, username = result
                if full_name and full_name.strip():
                    return full_name
                if username and username.strip():
                    return f"@{username}"
            
            return str(user_id)
        except:
            return str(user_id)
    
    def log_admin_message(self, user_id: int, username: str, full_name: str, text: str, 
                         chat_id: int, chat_type: str, is_command: bool) -> bool:
        """Log admin message to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admin_chat_logs 
                (user_id, username, full_name, message_text, chat_id, chat_type, is_command)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, full_name, text, chat_id, chat_type, is_command))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error logging admin message: {e}")
            return False
    
    def get_admin_logs(self, user_id: int = None, limit: int = 50, period: str = 'all') -> List[Dict]:
        """Get admin logs with filtering"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build query based on period
            where_clause = ""
            params = []
            
            if user_id:
                where_clause = "WHERE user_id = ?"
                params.append(user_id)
            
            # Add time filter
            if period == 'today':
                time_filter = "date(timestamp) = date('now')"
            elif period == 'week':
                time_filter = "date(timestamp) >= date('now', '-7 days')"
            elif period == 'month':
                time_filter = "date(timestamp) >= date('now', '-30 days')"
            else:
                time_filter = None
            
            if time_filter:
                if where_clause:
                    where_clause += f" AND {time_filter}"
                else:
                    where_clause = f"WHERE {time_filter}"
            
            query = f'''
                SELECT id, user_id, username, full_name, message_text, chat_id, chat_type, 
                       is_command, timestamp
                FROM admin_chat_logs
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'id': r[0], 'user_id': r[1], 'username': r[2], 'full_name': r[3],
                'message_text': r[4], 'chat_id': r[5], 'chat_type': r[6],
                'is_command': r[7], 'timestamp': r[8]
            } for r in rows]
        except Exception as e:
            logger.error(f"❌ Error getting admin logs: {e}")
            return []
    
    def get_admin_stats(self, user_id: int, period: str = 'today') -> Dict:
        """Get admin statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build time filter
            if period == 'today':
                time_filter = "date(timestamp) = date('now')"
            elif period == 'week':
                time_filter = "date(timestamp) >= date('now', '-7 days')"
            elif period == 'month':
                time_filter = "date(timestamp) >= date('now', '-30 days')"
            else:
                time_filter = "1=1"
            
            # Total messages
            cursor.execute(f'''
                SELECT COUNT(*) FROM admin_chat_logs 
                WHERE user_id = ? AND {time_filter}
            ''', (user_id,))
            total_messages = cursor.fetchone()[0]
            
            # Messages by chat type
            cursor.execute(f'''
                SELECT chat_type, COUNT(*) FROM admin_chat_logs 
                WHERE user_id = ? AND {time_filter}
                GROUP BY chat_type
            ''', (user_id,))
            by_chat_type = dict(cursor.fetchall())
            
            # Commands
            cursor.execute(f'''
                SELECT COUNT(*) FROM admin_chat_logs 
                WHERE user_id = ? AND is_command = 1 AND {time_filter}
            ''', (user_id,))
            total_commands = cursor.fetchone()[0]
            
            # Top commands
            cursor.execute(f'''
                SELECT message_text, COUNT(*) as cnt FROM admin_chat_logs 
                WHERE user_id = ? AND is_command = 1 AND {time_filter}
                GROUP BY message_text
                ORDER BY cnt DESC
                LIMIT 5
            ''', (user_id,))
            top_commands = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_messages': total_messages,
                'by_chat_type': by_chat_type,
                'total_commands': total_commands,
                'top_commands': top_commands
            }
        except Exception as e:
            logger.error(f"❌ Error getting admin stats: {e}")
            return {
                'total_messages': 0,
                'by_chat_type': {},
                'total_commands': 0,
                'top_commands': []
            }
    
    def get_all_admins_activity(self, period: str = 'today') -> List[Dict]:
        """Get activity for all admins"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build time filter
            if period == 'today':
                time_filter = "date(timestamp) = date('now')"
            elif period == 'week':
                time_filter = "date(timestamp) >= date('now', '-7 days')"
            elif period == 'month':
                time_filter = "date(timestamp) >= date('now', '-30 days')"
            else:
                time_filter = "1=1"
            
            cursor.execute(f'''
                SELECT a.user_id, a.username, a.full_name, COUNT(*) as msg_count
                FROM admin_chat_logs l
                JOIN admins a ON l.user_id = a.user_id
                WHERE {time_filter}
                GROUP BY a.user_id, a.username, a.full_name
                ORDER BY msg_count DESC
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'user_id': r[0],
                'username': r[1],
                'full_name': r[2],
                'message_count': r[3]
            } for r in rows]
        except Exception as e:
            logger.error(f"❌ Error getting all admins activity: {e}")
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
        self.db_path = DB_PATH  # Store DB path for easy access

        # Инициализация улучшенной системы управления админами и сменами
        self.enhanced_admin_shift_integration = None

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
        
        # Get owner IDs from environment or config
        owner_ids_str = os.getenv('OWNER_TG_IDS', '')
        owner_ids = []
        if owner_ids_str:
            try:
                owner_ids = [int(id.strip()) for id in owner_ids_str.split(',') if id.strip()]
            except ValueError:
                logger.error("❌ Invalid OWNER_TG_IDS format")
        
        # Fallback to config if no env variable
        if not owner_ids:
            owner_id = config.get('owner_id', config['admin_ids'][0] if config.get('admin_ids') else 0)
            owner_ids = [owner_id] if owner_id else []
        
        # Store for use in other modules (backward compatibility)
        self.owner_id = owner_ids[0] if owner_ids else 0
        self.owner_ids = owner_ids
        
        # V2Ray Manager (только для владельца)
        self.v2ray_manager = V2RayManager(DB_PATH)
        self.v2ray_commands = V2RayCommands(self.v2ray_manager, self.admin_manager, owner_ids=owner_ids)
        
        # Store owner IDs from environment
        owner_ids_str = os.getenv('OWNER_TG_IDS', '')
        self.owner_ids = []
        if owner_ids_str:
            try:
                self.owner_ids = [int(id.strip()) for id in owner_ids_str.split(',') if id.strip()]
            except ValueError:
                logger.error("❌ Invalid OWNER_TG_IDS format")
        
        # Fallback to single owner from config
        if not self.owner_ids:
            logger.warning("⚠️ OWNER_TG_IDS not configured, using fallback from config")
            self.owner_ids = [self.owner_id] if hasattr(self, 'owner_id') else []
        
        if not self.owner_ids:
            logger.warning("⚠️ No owner IDs configured!")
        
        # Club Manager (только для владельца)
        self.club_manager = ClubManager(DB_PATH)
        self.club_commands = ClubCommands(self.club_manager, self.owner_id)
        
        
        # Product Manager - управление товарами (для владельца и админов)
        logger.info("🔧 Initializing ProductManager...")
        try:
            self.product_manager = ProductManager(DB_PATH)
            logger.info("✅ ProductManager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ProductManager: {e}")
            raise
        self.product_commands = None  # Будет инициализирован позже
        
        # Issue Manager - отслеживание проблем (для владельца и админов)
        self.issue_manager = IssueManager(DB_PATH)
        self.issue_commands = None  # Будет инициализирован позже с bot_app

        # Очистка старых решенных проблем (старше 14 дней)
        try:
            deleted = self.issue_manager.cleanup_old_resolved_issues(days=14)
            if deleted > 0:
                logger.info(f"🧹 Очищено {deleted} старых решенных проблем")
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке старых проблем: {e}")

        # Shift Checklist Manager - чек-листы приема смены
        logger.info("✅ Initializing ShiftChecklistManager...")
        try:
            db_path_for_checklist = os.getenv('DB_PATH', '/opt/club_assistant/club_assistant.db')
            self.shift_checklist_manager = ShiftChecklistManager(db_path_for_checklist)
            logger.info("✅ ShiftChecklistManager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ShiftChecklistManager: {e}")
            self.shift_checklist_manager = None
        
        # Content Generator - AI content generation
        logger.info("🎨 Initializing ContentGenerator...")
        try:
            self.content_generator = ContentGenerator(
                DB_PATH, 
                config['openai_api_key'],
                config.get('gpt_model', 'gpt-4o-mini')
            )
            logger.info("✅ ContentGenerator initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ContentGenerator: {e}")
            raise
        self.content_commands = ContentCommands(self.content_generator, self.admin_manager)

        # Message Summarizer - AI пересказ сообщений
        logger.info("📝 Initializing MessageSummarizer...")
        try:
            from modules.message_summarizer import MessageSummarizer
            self.message_summarizer = MessageSummarizer(config['openai_api_key'])
            logger.info("✅ MessageSummarizer initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize MessageSummarizer: {e}")
            self.message_summarizer = None

        # Video generation (if enabled)
        video_config = config.get('content_generation', {}).get('video', {})
        if video_config.get('enabled'):
            try:
                from video_generator import VideoGenerator
                self.video_generator = VideoGenerator(config)
                logger.info("✅ Video generator initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize VideoGenerator: {e}")
                self.video_generator = None
        else:
            self.video_generator = None
            logger.info("⏸️ Video generation disabled")
        
        openai.api_key = config['openai_api_key']
        
        self.bot_username = None
        
        logger.info(f"✅ Бот v{VERSION} готов!")
        logger.info(f"   Векторов: {self.vector_store.stats()['total_vectors']}")
        logger.info(f"   Записей: {self.kb.count()}")
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        if not self.owner_ids:
            logger.warning("⚠️ No owner IDs configured")
            return user_id == self.owner_id  # Fallback to legacy owner_id
        return user_id in self.owner_ids
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Check for admin invite deep link
        if hasattr(self, 'admin_invite_interceptor') and context.args:
            intercepted = await self.admin_invite_interceptor(update, context)
            if intercepted:
                return

        user_id = update.effective_user.id
        username = update.effective_user.username or "без username"

        # Show user ID info
        # Экранируем специальные символы Markdown в username
        username_escaped = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        id_text = f"🆔 Ваш Telegram ID: `{user_id}`\n"
        id_text += f"👤 Username: @{username_escaped}\n\n"

        text = self._get_main_menu_text(user_id)
        # Add ID info at the beginning
        text = id_text + text

        inline_markup = self._build_main_menu_keyboard(user_id)

        # Отправить меню с inline кнопками, удалив reply-клавиатуру
        await update.message.reply_text(
            text,
            reply_markup=inline_markup,
            parse_mode='Markdown'
        )

        # Удалить reply-клавиатуру отдельным сообщением
        await update.message.reply_text(
            "Используйте кнопки выше для навигации ⬆️",
            reply_markup=ReplyKeyboardRemove()
        )

    async def cmd_cancel_general(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Общая команда /cancel для отмены любых действий"""
        await update.message.reply_text(
            "❌ Действие отменено. Клавиатура очищена.",
            reply_markup=ReplyKeyboardRemove()
        )

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
🎨 Генерация контента:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/image <описание> - создать изображение
/video <описание> - создать видео

Примеры:
• /image космический корабль
• /video дракон летит

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Команды:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/start - начало работы
/help - эта справка
/stats - статистика базы знаний

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 FinMon - Финансовый мониторинг:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/shift - сдать смену (кнопочный мастер)
/balances - текущие остатки
/movements - последние движения"""

        if self.admin_manager.is_admin(update.effective_user.id):
            text += "\n\n🔧 /admin - админ-панель (+ настройки GPT)"
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
🎨 Генерация контента (NEW!):
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Автоматически определяю тип:
  • Текст - статьи, посты, описания
  • Изображения - DALL-E 3
  • Видео - скоро доступно

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
/stats - статистика базы знаний

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 FinMon - Финансовый мониторинг:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/shift - сдать смену (кнопочный мастер)
/balances - текущие остатки
/movements - последние движения"""
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

    async def cmd_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's Telegram ID and username"""
        user = update.effective_user
        user_id = user.id
        username = user.username
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()

        text = "🆔 **Ваша информация:**\n\n"
        text += f"**ID:** `{user_id}`\n"
        if username:
            text += f"**Username:** @{username}\n"
        if full_name:
            text += f"**Имя:** {full_name}\n"

        text += f"\n💡 ID можно скопировать нажав на него"

        await update.message.reply_text(text, parse_mode='Markdown')

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
            
            # Use new AdminDB system if available
            if hasattr(self, 'admin_db') and self.admin_db:
                # Add admin with default role 'staff'
                if self.admin_db.add_admin(
                    user_id=new_admin_id,
                    role='staff',
                    added_by=update.effective_user.id,
                    active=1
                ):
                    # Log the action
                    self.admin_db.log_action(
                        update.effective_user.id,
                        'add_admin',
                        new_admin_id,
                        {'via': 'command'}
                    )
                    await update.message.reply_text(
                        f"✅ Админ добавлен: {new_admin_id}\n"
                        f"🔖 Роль: staff\n\n"
                        f"Используйте /admins для управления правами"
                    )
                else:
                    await update.message.reply_text(f"❌ Ошибка при добавлении админа {new_admin_id}")
            else:
                # Fallback to old system
                self.admin_manager.add_admin(new_admin_id, added_by=update.effective_user.id)
                await update.message.reply_text(f"✅ Админ: {new_admin_id}")
        except (IndexError, ValueError):
            await update.message.reply_text(
                "❌ Неверный формат\n\n"
                "Использование: /addadmin <user_id>\n"
                "Пример: /addadmin 123456789"
            )
    
    
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
    
    async def cmd_setname(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set admin's full name (owner only)"""
        if update.effective_user.id != self.owner_id:
            await update.message.reply_text("❌ Только для владельца")
            return
        
        try:
            if len(context.args) < 2:
                await update.message.reply_text("Использование: /setname <user_id> <полное имя>")
                return
            
            user_id = int(context.args[0])
            full_name = ' '.join(context.args[1:])
            
            # Check if user is admin
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text(f"❌ Пользователь {user_id} не является админом")
                return
            
            if self.admin_manager.set_full_name(user_id, full_name):
                await update.message.reply_text(f"✅ Имя установлено: {full_name}")
            else:
                await update.message.reply_text("❌ Ошибка при установке имени")
        except ValueError:
            await update.message.reply_text("❌ Неверный user_id")
        except Exception as e:
            logger.error(f"❌ Error in cmd_setname: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def cmd_adminchats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin chat logs (owner only)"""
        if update.effective_user.id != self.owner_id:
            await update.message.reply_text("❌ Только для владельца")
            return
        
        try:
            if len(context.args) < 1:
                await update.message.reply_text("Использование: /adminchats <user_id>")
                return
            
            user_id = int(context.args[0])
            
            # Check if user is admin
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text(f"❌ Пользователь {user_id} не является админом")
                return
            
            # Show admin chat dashboard
            await self._show_admin_chats(update, context, user_id, 'today', 'all')
        except ValueError:
            await update.message.reply_text("❌ Неверный user_id")
        except Exception as e:
            logger.error(f"❌ Error in cmd_adminchats: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def cmd_adminstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all admins activity (owner only)"""
        if update.effective_user.id != self.owner_id:
            await update.message.reply_text("❌ Только для владельца")
            return
        
        try:
            await self._show_all_admins_activity(update, context, 'today')
        except Exception as e:
            logger.error(f"❌ Error in cmd_adminstats: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def cmd_adminmonitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin monitoring dashboard (owner only)"""
        if update.effective_user.id != self.owner_id:
            await update.message.reply_text("❌ Только для владельца")
            return
        
        try:
            await self._show_monitor_main(update, context)
        except Exception as e:
            logger.error(f"❌ Error in cmd_adminmonitor: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def _show_monitor_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main admin monitoring dashboard"""
        text = "👥 Мониторинг админов\n\n"
        text += "Выберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("📋 Список админов", callback_data="monitor_admins_list")],
            [InlineKeyboardButton("💬 Активность за сегодня", callback_data="monitor_activity_today")],
            [InlineKeyboardButton("📅 Активность за неделю", callback_data="monitor_activity_week")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def _show_admins_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show interactive admin list with stats"""
        admins = self.admin_manager.list_admins()
        
        if not admins:
            text = "Нет админов"
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="monitor_main")]]
            
            if update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        text = f"👥 Админы ({len(admins)})\n\n"
        
        keyboard = []
        for i, (user_id, username, full_name) in enumerate(admins, 1):
            text += "━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"{i}. 👤 {full_name if full_name else 'Не установлено'}\n"
            text += f"   ID: {user_id}"
            if username:
                text += f" | @{username}"
            
            # Get today's message count
            stats = self.admin_manager.get_admin_stats(user_id, 'today')
            text += f"\n   💬 Сегодня: {stats['total_messages']} сообщений\n"
            
            # Add buttons for this admin
            keyboard.append([
                InlineKeyboardButton("📝 Чаты", callback_data=f"monitor_admin_chats_{user_id}_today_all"),
                InlineKeyboardButton("📊 Статистика", callback_data=f"monitor_admin_stats_{user_id}_today")
            ])
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━"
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="monitor_main")])
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def _show_admin_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                user_id: int, period: str = 'today', filter_type: str = 'all',
                                offset: int = 0):
        """Show admin chat logs with filters"""
        display_name = self.admin_manager.get_display_name(user_id)
        
        # Get logs based on filter
        if filter_type == 'groups':
            logs = [l for l in self.admin_manager.get_admin_logs(user_id, 20 + offset, period) 
                   if l['chat_type'] in ['group', 'supergroup']]
        elif filter_type == 'commands':
            logs = [l for l in self.admin_manager.get_admin_logs(user_id, 20 + offset, period) 
                   if l['is_command']]
        else:
            logs = self.admin_manager.get_admin_logs(user_id, 20 + offset, period)
        
        # Apply offset for pagination
        logs = logs[offset:][:20]
        
        text = f"💬 Чаты: {display_name}\n\n"
        
        # Filter buttons
        text += "Фильтры:\n"
        period_buttons = [
            InlineKeyboardButton("🕐 Сегодня" if period == 'today' else "Сегодня", 
                               callback_data=f"monitor_admin_chats_{user_id}_today_{filter_type}"),
            InlineKeyboardButton("📅 Неделя" if period == 'week' else "Неделя", 
                               callback_data=f"monitor_admin_chats_{user_id}_week_{filter_type}"),
            InlineKeyboardButton("📆 Месяц" if period == 'month' else "Месяц", 
                               callback_data=f"monitor_admin_chats_{user_id}_month_{filter_type}")
        ]
        
        filter_buttons = [
            InlineKeyboardButton("💬 Все" if filter_type == 'all' else "Все", 
                               callback_data=f"monitor_admin_chats_{user_id}_{period}_all"),
            InlineKeyboardButton("👥 Группы" if filter_type == 'groups' else "Группы", 
                               callback_data=f"monitor_admin_chats_{user_id}_{period}_groups"),
            InlineKeyboardButton("⚙️ Команды" if filter_type == 'commands' else "Команды", 
                               callback_data=f"monitor_admin_chats_{user_id}_{period}_commands")
        ]
        
        keyboard = [period_buttons, filter_buttons]
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if not logs:
            text += "Нет сообщений за этот период"
        else:
            for log in logs:
                # Format timestamp
                ts = log['timestamp']
                time_str = ts.split()[1][:8] if ' ' in ts else ts[:8]
                
                # Chat type emoji
                if log['chat_type'] == 'private':
                    chat_emoji = "💬 Личка"
                elif log['chat_type'] in ['group', 'supergroup']:
                    chat_emoji = "👥 Группа"
                else:
                    chat_emoji = "💬"
                
                text += f"⏰ {time_str} | {chat_emoji}\n"
                
                # Message text
                msg_text = log['message_text']
                if log['is_command']:
                    text += f"🔧 {msg_text}\n"
                else:
                    # Truncate long messages
                    if len(msg_text) > 100:
                        msg_text = msg_text[:97] + "..."
                    text += f'"{msg_text}"\n'
                
                text += "\n"
        
        # Navigation buttons
        nav_buttons = [
            InlineKeyboardButton("◀️ Назад", callback_data="monitor_admins_list"),
            InlineKeyboardButton("🔄 Обновить", callback_data=f"monitor_admin_chats_{user_id}_{period}_{filter_type}")
        ]
        
        if len(logs) == 20:
            nav_buttons.append(InlineKeyboardButton("⬇️ Ещё 20", 
                                                   callback_data=f"monitor_admin_chats_{user_id}_{period}_{filter_type}_{offset + 20}"))
        
        keyboard.append(nav_buttons)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def _show_admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               user_id: int, period: str = 'today'):
        """Show admin statistics"""
        display_name = self.admin_manager.get_display_name(user_id)
        stats = self.admin_manager.get_admin_stats(user_id, period)
        
        period_names = {
            'today': 'За сегодня',
            'week': 'За неделю',
            'month': 'За месяц'
        }
        
        text = f"📊 Статистика: {display_name}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📅 {period_names.get(period, 'За период')}:\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💬 Сообщений: {stats['total_messages']}\n"
        
        # By chat type
        by_type = stats.get('by_chat_type', {})
        if by_type:
            text += f"   • Личка: {by_type.get('private', 0)}\n"
            text += f"   • Группы: {by_type.get('group', 0) + by_type.get('supergroup', 0)}\n"
        
        text += f"\n⚙️ Команд: {stats['total_commands']}\n"
        
        # Top commands
        top_commands = stats.get('top_commands', [])
        if top_commands:
            for cmd, cnt in top_commands[:5]:
                text += f"   • {cmd}: {cnt}\n"
        
        keyboard = [
            [InlineKeyboardButton("📅 Сегодня" if period != 'today' else "✅ Сегодня", 
                                callback_data=f"monitor_admin_stats_{user_id}_today"),
             InlineKeyboardButton("📅 Неделя" if period != 'week' else "✅ Неделя", 
                                callback_data=f"monitor_admin_stats_{user_id}_week"),
             InlineKeyboardButton("📅 Месяц" if period != 'month' else "✅ Месяц", 
                                callback_data=f"monitor_admin_stats_{user_id}_month")],
            [InlineKeyboardButton("◀️ Назад", callback_data="monitor_admins_list")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def _show_all_admins_activity(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                       period: str = 'today'):
        """Show all admins activity"""
        activity = self.admin_manager.get_all_admins_activity(period)
        
        period_names = {
            'today': 'сегодня',
            'week': 'за неделю',
            'month': 'за месяц'
        }
        
        text = f"💬 Активность админов ({period_names.get(period, 'за период')})\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if not activity:
            text += "Нет активности"
        else:
            medals = ['🥇', '🥈', '🥉']
            total_messages = 0
            
            for i, admin in enumerate(activity):
                medal = medals[i] if i < 3 else f"{i+1}."
                display_name = admin['full_name'] if admin['full_name'] else (
                    f"@{admin['username']}" if admin['username'] else str(admin['user_id'])
                )
                
                text += f"{medal} {display_name}: {admin['message_count']} сообщений\n"
                text += f"   [📝 Чаты]({admin['user_id']})\n\n"
                total_messages += admin['message_count']
            
            text += "━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 Всего: {total_messages} сообщений\n"
        
        keyboard = [
            [InlineKeyboardButton("🕐 Сегодня" if period != 'today' else "✅ Сегодня", 
                                callback_data="monitor_activity_today"),
             InlineKeyboardButton("📅 Неделя" if period != 'week' else "✅ Неделя", 
                                callback_data="monitor_activity_week"),
             InlineKeyboardButton("📆 Месяц" if period != 'month' else "✅ Месяц", 
                                callback_data="monitor_activity_month")],
            [InlineKeyboardButton("🔄 Обновить", callback_data=f"monitor_activity_{period}"),
             InlineKeyboardButton("◀️ Назад", callback_data="monitor_main")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
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
    
    async def cmd_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate image via DALL-E 3"""
        if not context.args:
            await update.message.reply_text(
                "Использование: /image <описание>\n\n"
                "Примеры:\n"
                "• /image красивый закат\n"
                "• /image космический корабль"
            )
            return
        
        prompt = ' '.join(context.args)
        user_id = update.effective_user.id
        
        # Show processing message
        await update.message.reply_text("🎨 Генерирую изображение... Это может занять ~30 секунд.")
        
        try:
            response = openai.Image.create(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )
            
            image_url = response['data'][0]['url']
            
            # Log to database (non-blocking - don't fail if logging fails)
            try:
                self.content_generator.generate_image(prompt, user_id)
            except Exception as log_err:
                logger.warning(f"⚠️ Failed to log image generation to database: {log_err}")
            
            await update.message.reply_photo(
                photo=image_url,
                caption=f"🎨 {prompt}"
            )
        except Exception as e:
            logger.error(f"❌ Image generation error: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def cmd_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Summarize messages - use with reply or in group"""
        # Check if summarizer is available
        if not hasattr(self, 'message_summarizer') or not self.message_summarizer:
            await update.message.reply_text("❌ Пересказ сообщений отключен (нет OpenAI API ключа)")
            return

        user_id = update.effective_user.id

        # Check if user is owner
        if user_id not in self.owner_ids:
            await update.message.reply_text("❌ Эта команда доступна только владельцу бота")
            return

        # For now, show info about upcoming feature
        await update.message.reply_text(
            "📝 Функция пересказа сообщений\n\n"
            "⚠️ В разработке. Скоро будет доступна!\n\n"
            "Планируемые возможности:\n"
            "• Пересказ последних N сообщений из группы\n"
            "• Пересказ переслан ных сообщений\n"
            "• Автоматическое выделение ключевых моментов\n\n"
            "Это будет дешевле автообучения, так как использует gpt-4o-mini."
        )

    async def cmd_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate video via OpenAI Sora"""
        if not self.video_generator:
            await update.message.reply_text("❌ Генерация видео отключена в конфигурации")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Использование: /video <описание>\n\n"
                "Примеры:\n"
                "• /video кот играет с мячиком\n"
                "• /video дракон летит над горами\n\n"
                "⏱️ Генерация занимает 30-90 секунд"
            )
            return
        
        prompt = ' '.join(context.args)
        user_id = update.effective_user.id
        msg = await update.message.reply_text("🎬 Генерирую видео...")
        
        try:
            result = self.video_generator.generate(prompt)
            
            if 'error' in result:
                await msg.edit_text(f"❌ Ошибка: {result['error']}")
                return
            
            video_url = result['video_url']
            
            # Log to database (non-blocking - don't fail if logging fails)
            try:
                self.content_generator.generate_video(
                    prompt, 
                    user_id, 
                    video_url=video_url,
                    duration=result.get('duration', 5),
                    resolution=result.get('resolution', '1080p')
                )
            except Exception as log_err:
                logger.warning(f"⚠️ Failed to log video generation to database: {log_err}")
            
            await update.message.reply_video(
                video=video_url,
                caption=f"🎬 {prompt}\n📊 {result['resolution']} • {result['duration']}s"
            )
            await msg.delete()
            
        except Exception as e:
            logger.error(f"❌ Video generation error: {e}")
            await msg.edit_text(f"❌ Ошибка: {e}")
    
    def _build_main_menu_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Построить клавиатуру главного меню"""
        keyboard = []

        # Проверяем, является ли пользователь контролером
        controller_id = self.config.get('controller_id')
        is_controller = controller_id and user_id == controller_id

        # Кнопки для всех пользователей (кроме контролера)
        if not is_controller:
            keyboard.append([InlineKeyboardButton("📖 Справка", callback_data="help")])
            keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="stats")])
            keyboard.append([InlineKeyboardButton("🎨 Генерация контента", callback_data="content_menu")])

        # Проверка активной смены для админов
        active_shift = None

        # Проверяем, является ли пользователь клубным аккаунтом
        club_accounts = self.config.get('club_accounts', {})
        is_club_account = user_id in club_accounts.values()

        # Проверяем, есть ли у админа полное ФИО (для доступа к меню Смены)
        has_full_name = False

        # Владелец - показываем только панель владельца, без кнопок обычного админа
        if user_id == self.owner_id:
            # Панель владельца с полным функционалом
            keyboard.append([InlineKeyboardButton("👑 Панель владельца", callback_data="owner_panel")])
            keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="admin")])
            keyboard.append([InlineKeyboardButton("🔐 V2Ray VPN", callback_data="v2ray")])
            keyboard.append([InlineKeyboardButton("👥 Управление админами", callback_data="adm_menu")])

        # Обычные админы (НЕ владелец и НЕ контролёр)
        elif self.admin_manager.is_admin(user_id) and not is_controller:
            try:
                admin_info = self.admin_db.get_admin(user_id) if hasattr(self, 'admin_db') and self.admin_db else None
                if admin_info and admin_info.get('full_name'):
                    has_full_name = True
            except Exception as e:
                logger.error(f"Error checking admin full_name: {e}")

            # Проверка активной смены для админов (но не для контролера)
            if hasattr(self, 'shift_manager') and self.shift_manager:
                try:
                    active_shift = self.shift_manager.get_active_shift(user_id)
                except Exception as e:
                    logger.error(f"❌ Failed to get active shift for {user_id}: {e}")

            # Кнопки смены - ТОЛЬКО для клубных аккаунтов
            if is_club_account:
                if active_shift:
                    # Есть открытая смена
                    keyboard.append([
                        InlineKeyboardButton("💸 Списать с кассы", callback_data="shift_expense"),
                        InlineKeyboardButton("💰 Взять зарплату", callback_data="shift_salary")
                    ])
                    keyboard.append([InlineKeyboardButton("🔒 Закрыть смену", callback_data="shift_close")])
                else:
                    # Нет открытой смены
                    keyboard.append([InlineKeyboardButton("🔓 Открыть смену", callback_data="shift_open")])

            # Кнопка "Смены" - ТОЛЬКО для админов с полным ФИО
            if has_full_name:
                keyboard.append([InlineKeyboardButton("📅 Смены", callback_data="shifts_menu")])

            # Кнопки доступные всем обычным админам
            keyboard.append([InlineKeyboardButton("📦 Управление товарами", callback_data="product_menu")])
            keyboard.append([InlineKeyboardButton("⚠️ Проблемы клуба", callback_data="issue_menu")])
            keyboard.append([InlineKeyboardButton("🔧 Задачи обслуживания", callback_data="maintenance_tasks")])

        # Панель большого брата (для контролера)
        controller_id = self.config.get('controller_id')
        if controller_id and user_id == controller_id:
            keyboard.append([InlineKeyboardButton("👁 Панель большого брата", callback_data="controller_panel")])

        return InlineKeyboardMarkup(keyboard)
    
    def _get_main_menu_text(self, user_id: int = None) -> str:
        """Получить текст главного меню"""

        # Проверяем, есть ли открытая смена у этого пользователя
        if user_id and hasattr(self, 'shift_manager') and self.shift_manager:
            try:
                # Проверяем смены где user_id является админом (admin_id или confirmed_by)
                active_shift = None
                all_shifts = self.shift_manager.get_all_active_shifts()
                for shift in all_shifts:
                    if shift.get('admin_id') == user_id or shift.get('confirmed_by') == user_id:
                        active_shift = shift
                        break

                if active_shift:
                    # Получаем имя пользователя
                    admin_name = "Админ"
                    try:
                        if hasattr(self, 'admin_db') and self.admin_db:
                            admin = self.admin_db.get_admin(user_id)
                            if admin:
                                admin_name = admin.get('full_name') or admin.get('name') or admin.get('username') or admin_name
                    except Exception as e:
                        logger.error(f"Error getting admin name: {e}")

                    shift_type_label = "☀️ Дневная" if active_shift['shift_type'] == "morning" else "🌙 Ночная"

                    return f"""👋 Привет, {admin_name}!

✨ Желаю удачной смены!

📊 Ваша смена:
🏢 Клуб: {active_shift['club']}
⏰ Тип: {shift_type_label}
🆔 ID: #{active_shift['id']}

Используйте меню ниже для работы."""
            except Exception as e:
                logger.error(f"Error getting active shift for greeting: {e}")

        # Стандартное приветствие
        return f"""👋 Привет!

Я ассистент компьютерного клуба v{VERSION}.

💼 Основные функции:
• 📅 Управление сменами и расписанием
• 💰 Учет финансов (выручка, остатки, расходы)
• 👥 Управление админами
• 📊 Отчеты и статистика
• 🔄 Обмен сменами между админами

🤖 Умный помощник:
• Запоминаю проблемы и решения
• Помогаю с инструкциями
• Веду учет инцидентов

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

    async def _show_shifts_menu(self, query):
        """Show shifts management menu"""
        text = """📅 Смены

Управление вашими сменами:

👁 **Мои смены** - посмотреть ваши смены на текущий и следующий месяц
🔄 **Обменяться сменой** - поменяться сменой с другим админом"""

        keyboard = [
            [InlineKeyboardButton("👁 Мои смены", callback_data="shifts_view")],
            [InlineKeyboardButton("🔄 Обменяться сменой", callback_data="shifts_swap")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except Exception as e:
            # Игнорируем ошибку "Message is not modified"
            if "message is not modified" not in str(e).lower():
                logger.error(f"❌ Error editing shifts menu: {e}")

    async def _show_swap_shift_selection(self, query, context):
        """Show user's shifts for swap selection"""
        user_id = query.from_user.id

        try:
            # Get admin info - try admin_db first, then use direct database access
            admin_info = None
            admin_name = None

            try:
                if hasattr(self, 'admin_db') and self.admin_db is not None:
                    admin_info = self.admin_db.get_admin(user_id)
                    if admin_info:
                        admin_name = admin_info.get('full_name')
                else:
                    logger.warning("⚠️ admin_db not available, using direct database access")
            except Exception as e:
                logger.warning(f"⚠️ admin_db error, using direct access: {e}")

            # Fallback to direct database access if admin_db failed
            if not admin_name:
                try:
                    import sqlite3
                    # Use the db_path from config
                    db_path = getattr(self, 'db_path', '/opt/club_assistant/bot_data.db')
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute('SELECT full_name FROM admins WHERE user_id = ? AND is_active = 1', (user_id,))
                    result = cursor.fetchone()
                    conn.close()
                    if result:
                        admin_name = result[0]
                except Exception as db_error:
                    logger.error(f"❌ Database error in swap shift selection: {db_error}")
                    import traceback
                    traceback.print_exc()
                    await query.edit_message_text(
                        f"❌ Ошибка доступа к базе данных: {db_error}\n\nОбратитесь к владельцу.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="shifts_menu")]])
                    )
                    return

            # Проверка наличия полного ФИО (минимум 3 слова: Фамилия Имя Отчество)
            if not admin_name or len(admin_name.strip().split()) < 3:
                try:
                    await query.edit_message_text(
                        "❌ Вы не найдены в списке админов или у вас не указано полное ФИО.\n\n"
                        "Эта функция доступна только для админов с полным ФИО (Фамилия Имя Отчество).",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="shifts_menu")]])
                    )
                except Exception as edit_error:
                    if "message is not modified" not in str(edit_error).lower():
                        logger.error(f"❌ Error editing message: {edit_error}")
                return

            # Get shifts for current and next month
            from datetime import date, timedelta
            today = date.today()
            current_month = today.replace(day=1)
            next_month = (current_month + timedelta(days=32)).replace(day=1)

            schedule_parser = self.schedule_commands.schedule_parser
            current_shifts = schedule_parser.get_admin_shifts_for_month(admin_name, current_month)
            next_shifts = schedule_parser.get_admin_shifts_for_month(admin_name, next_month)

            all_shifts = current_shifts + next_shifts

            # Filter only future shifts
            future_shifts = [s for s in all_shifts if s['date'] >= today]

            if not future_shifts:
                await query.edit_message_text(
                    "❌ У вас нет предстоящих смен для обмена.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="shifts_menu")]])
                )
                return

            # Build keyboard with shifts
            text = "🔄 **Выберите смену для обмена:**\n\n"
            keyboard = []

            for shift in future_shifts:
                shift_date = shift['date']
                club = shift['club']
                shift_type = shift['shift_type']

                # Format shift label
                club_emoji = "🔴" if club == "Рио" else "🔵"
                shift_emoji = "☀️" if shift_type == "morning" else "🌙"
                weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][shift_date.weekday()]

                label = f"{shift_date.day} {weekday} - {club_emoji} {club} {shift_emoji}"
                callback_data = f"swap_select_{shift_date.strftime('%Y%m%d')}_{club}_{shift_type}"

                keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
                text += f"• {label}\n"

            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="shifts_menu")])

            try:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            except Exception as edit_error:
                # Игнорируем ошибку "Message is not modified"
                if "message is not modified" not in str(edit_error).lower():
                    raise

        except Exception as e:
            logger.error(f"❌ Error showing swap shift selection: {e}")
            import traceback
            traceback.print_exc()
            try:
                await query.edit_message_text(
                    f"❌ Ошибка при получении списка смен: {e}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="shifts_menu")]])
                )
            except Exception as edit_error:
                # Игнорируем ошибку "Message is not modified"
                if "message is not modified" not in str(edit_error).lower():
                    logger.error(f"❌ Error editing message: {edit_error}")

    async def _show_admin_selection_for_swap(self, query, context, callback_data):
        """Show list of admins to swap shift with"""
        try:
            # Parse selected shift from callback_data
            # Format: swap_select_YYYYMMDD_club_shift_type
            parts = callback_data.replace("swap_select_", "").split("_")
            shift_date_str = parts[0]
            club = parts[1]
            shift_type = parts[2]

            from datetime import datetime
            shift_date = datetime.strptime(shift_date_str, "%Y%m%d").date()

            # Store selected shift in context for later
            context.user_data['swap_shift'] = {
                'date': shift_date,
                'club': club,
                'shift_type': shift_type
            }

            # Get list of all admins with full names (minimum 3 words: Фамилия Имя Отчество)
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, full_name
                    FROM admins
                    WHERE full_name IS NOT NULL
                    AND full_name != ''
                    AND user_id != ?
                    AND is_active = 1
                    ORDER BY full_name
                """, (query.from_user.id,))
                all_admins = cursor.fetchall()
                conn.close()

                # Фильтрация: только админы с полным ФИО (минимум 3 слова)
                # Исключаем технические аккаунты клубов и служебные аккаунты
                excluded_keywords = ['клуб', 'рио', 'север', 'главный', 'администратор', 'око', 'саурона']
                admins = []
                for user_id, full_name in all_admins:
                    if not full_name or len(full_name.strip().split()) < 3:
                        continue

                    # Проверяем, что это не технический аккаунт
                    full_name_lower = full_name.lower()
                    is_technical = any(keyword in full_name_lower for keyword in excluded_keywords)

                    if not is_technical:
                        admins.append((user_id, full_name))
            except Exception as db_error:
                logger.error(f"❌ Database error in swap admin selection: {db_error}")
                await query.edit_message_text(
                    f"❌ Ошибка доступа к базе данных: {db_error}\n\nОбратитесь к владельцу.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="shifts_swap")]])
                )
                return

            if not admins:
                await query.edit_message_text(
                    "❌ Нет доступных админов для обмена сменой.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="shifts_swap")]])
                )
                return

            # Format shift info
            club_emoji = "🔴" if club == "Рио" else "🔵"
            shift_emoji = "☀️" if shift_type == "morning" else "🌙"
            weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][shift_date.weekday()]
            month_names = ["января", "февраля", "марта", "апреля", "мая", "июня",
                          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
            month_name = month_names[shift_date.month - 1]

            text = f"🔄 **Обмен сменой**\n\n"
            text += f"📅 Ваша смена: {shift_date.day} {month_name} ({weekday}) - {club_emoji} {club} {shift_emoji}\n\n"
            text += f"👥 Выберите админа для обмена:\n"

            keyboard = []
            for admin_id, full_name in admins:
                # Shorten name if too long
                display_name = full_name if len(full_name) <= 30 else full_name[:27] + "..."
                callback = f"swap_admin_{admin_id}_{shift_date_str}_{club}_{shift_type}"
                keyboard.append([InlineKeyboardButton(display_name, callback_data=callback)])

            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="shifts_swap")])

            try:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            except Exception as edit_error:
                # Игнорируем ошибку "Message is not modified"
                if "message is not modified" not in str(edit_error).lower():
                    raise

        except Exception as e:
            logger.error(f"❌ Error showing admin selection: {e}")
            import traceback
            traceback.print_exc()
            try:
                await query.edit_message_text(
                    f"❌ Ошибка: {e}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="shifts_swap")]])
                )
            except Exception as edit_error:
                # Игнорируем ошибку "Message is not modified"
                if "message is not modified" not in str(edit_error).lower():
                    logger.error(f"❌ Error editing message: {edit_error}")

    async def _send_swap_request(self, query, context, callback_data):
        """Send swap request to selected admin"""
        try:
            # Parse callback_data
            # Format: swap_admin_USERID_YYYYMMDD_club_shift_type
            parts = callback_data.replace("swap_admin_", "").split("_")
            target_admin_id = int(parts[0])
            shift_date_str = parts[1]
            club = parts[2]
            shift_type = parts[3]

            from datetime import datetime
            shift_date = datetime.strptime(shift_date_str, "%Y%m%d").date()

            # Get requester info
            requester_id = query.from_user.id
            requester_info = self.admin_db.get_admin(requester_id)
            requester_name = requester_info.get('full_name', 'Админ') if requester_info else 'Админ'

            # Get target admin info
            target_info = self.admin_db.get_admin(target_admin_id)
            target_name = target_info.get('full_name', 'Админ') if target_info else 'Админ'

            # Format shift info
            club_emoji = "🔴" if club == "Рио" else "🔵"
            shift_emoji = "☀️" if shift_type == "morning" else "🌙"
            weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][shift_date.weekday()]
            month_names = ["января", "февраля", "марта", "апреля", "мая", "июня",
                          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
            month_name = month_names[shift_date.month - 1]

            # Get target admin's shift on that day (if any)
            schedule_parser = self.schedule_commands.schedule_parser
            target_shifts_month = schedule_parser.get_admin_shifts_for_month(target_name, shift_date.replace(day=1))
            target_shift_on_date = None
            for s in target_shifts_month:
                if s['date'] == shift_date:
                    target_shift_on_date = s
                    break

            # Send notification to target admin
            notification_text = f"🔄 **Запрос на обмен сменой**\n\n"
            notification_text += f"От: {requester_name}\n\n"
            notification_text += f"📅 Смена: {shift_date.day} {month_name} ({weekday})\n"
            notification_text += f"🏢 Клуб: {club_emoji} {club} {shift_emoji}\n\n"

            if target_shift_on_date:
                target_club_emoji = "🔴" if target_shift_on_date['club'] == "Рио" else "🔵"
                target_shift_emoji = "☀️" if target_shift_on_date['shift_type'] == "morning" else "🌙"
                notification_text += f"↔️ **Обмен на вашу смену:**\n"
                notification_text += f"🏢 {target_club_emoji} {target_shift_on_date['club']} {target_shift_emoji}\n\n"
                swap_type = "exchange"  # Both admins have shifts on this date
            else:
                notification_text += f"⚠️ У вас нет смены в этот день.\n\n"
                swap_type = "takeover"  # Target admin will just take the shift

            notification_text += f"Вы согласны?"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Согласен", callback_data=f"swap_confirm_{requester_id}_{shift_date_str}_{club}_{shift_type}_{swap_type}"),
                    InlineKeyboardButton("❌ Отказать", callback_data=f"swap_reject_{requester_id}_{shift_date_str}_{club}_{shift_type}")
                ]
            ]

            # Send to target admin
            sent_message = await context.bot.send_message(
                chat_id=target_admin_id,
                text=notification_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

            # Store swap request info for later
            if 'pending_swap_requests' not in context.bot_data:
                context.bot_data['pending_swap_requests'] = {}

            swap_key = f"{requester_id}_{shift_date_str}_{club}_{shift_type}"
            context.bot_data['pending_swap_requests'][swap_key] = {
                'requester_id': requester_id,
                'requester_name': requester_name,
                'target_id': target_admin_id,
                'target_name': target_name,
                'shift_date': shift_date,
                'club': club,
                'shift_type': shift_type,
                'target_shift': target_shift_on_date,
                'swap_type': swap_type,
                'message_id': sent_message.message_id,
                'chat_id': target_admin_id
            }

            # Confirm to requester
            await query.edit_message_text(
                f"✅ Запрос на обмен отправлен {target_name}!\n\n"
                f"📅 Смена: {shift_date.day} {month_name} ({weekday}) - {club_emoji} {club} {shift_emoji}\n\n"
                f"Ожидайте ответа...",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]])
            )

            logger.info(f"📤 Swap request sent: {requester_name} -> {target_name} for {shift_date} {club} {shift_type}")

        except Exception as e:
            logger.error(f"❌ Error sending swap request: {e}")
            import traceback
            traceback.print_exc()
            await query.edit_message_text(
                f"❌ Ошибка при отправке запроса: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="shifts_swap")]])
            )

    async def _handle_swap_response(self, query, context, callback_data):
        """Handle swap confirmation or rejection"""
        try:
            is_confirm = callback_data.startswith("swap_confirm_")

            # Parse callback_data
            if is_confirm:
                # Format: swap_confirm_REQUESTERID_YYYYMMDD_club_shift_type_swaptype
                parts = callback_data.replace("swap_confirm_", "").split("_")
                requester_id = int(parts[0])
                shift_date_str = parts[1]
                club = parts[2]
                shift_type = parts[3]
                swap_type = parts[4]
            else:
                # Format: swap_reject_REQUESTERID_YYYYMMDD_club_shift_type
                parts = callback_data.replace("swap_reject_", "").split("_")
                requester_id = int(parts[0])
                shift_date_str = parts[1]
                club = parts[2]
                shift_type = parts[3]
                swap_type = None

            from datetime import datetime
            shift_date = datetime.strptime(shift_date_str, "%Y%m%d").date()

            # Get swap request info
            swap_key = f"{requester_id}_{shift_date_str}_{club}_{shift_type}"
            swap_info = context.bot_data.get('pending_swap_requests', {}).get(swap_key)

            if not swap_info:
                await query.edit_message_text(
                    "❌ Запрос на обмен не найден или уже обработан.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]])
                )
                return

            responder_id = query.from_user.id
            responder_name = swap_info['target_name']
            requester_name = swap_info['requester_name']

            # Format shift info
            club_emoji = "🔴" if club == "Рио" else "🔵"
            shift_emoji = "☀️" if shift_type == "morning" else "🌙"
            month_names = ["января", "февраля", "марта", "апреля", "мая", "июня",
                          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
            month_name = month_names[shift_date.month - 1]
            weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][shift_date.weekday()]

            if is_confirm:
                # Update Google Sheets
                schedule_parser = self.schedule_commands.schedule_parser

                try:
                    # Update the shift assignment
                    success = schedule_parser.update_duty_assignment(
                        duty_date=shift_date,
                        club=club,
                        shift_type=shift_type,
                        old_admin_name=requester_name,
                        new_admin_name=responder_name
                    )

                    if success:
                        # If this was an exchange (both had shifts), update the second shift too
                        if swap_type == "exchange" and swap_info.get('target_shift'):
                            target_shift = swap_info['target_shift']
                            success2 = schedule_parser.update_duty_assignment(
                                duty_date=shift_date,
                                club=target_shift['club'],
                                shift_type=target_shift['shift_type'],
                                old_admin_name=responder_name,
                                new_admin_name=requester_name
                            )

                            if success2:
                                result_text = f"✅ **Обмен сменами выполнен!**\n\n"
                                result_text += f"📅 Дата: {shift_date.day} {month_name} ({weekday})\n\n"
                                result_text += f"↔️ **Обмен:**\n"
                                result_text += f"{requester_name}: {club_emoji} {club} {shift_emoji} → "
                                target_club_emoji = "🔴" if target_shift['club'] == "Рио" else "🔵"
                                target_shift_emoji = "☀️" if target_shift['shift_type'] == "morning" else "🌙"
                                result_text += f"{target_club_emoji} {target_shift['club']} {target_shift_emoji}\n"
                                result_text += f"{responder_name}: {target_club_emoji} {target_shift['club']} {target_shift_emoji} → {club_emoji} {club} {shift_emoji}"
                            else:
                                result_text = f"⚠️ **Частичный обмен**\n\n"
                                result_text += f"Смена {club_emoji} {club} {shift_emoji} передана вам, но не удалось обновить вторую смену.\n"
                                result_text += f"Обратитесь к владельцу для проверки."
                        else:
                            result_text = f"✅ **Смена передана!**\n\n"
                            result_text += f"📅 {shift_date.day} {month_name} ({weekday}) - {club_emoji} {club} {shift_emoji}\n\n"
                            result_text += f"{requester_name} → {responder_name}"

                        logger.info(f"✅ Swap completed: {requester_name} <-> {responder_name} on {shift_date} {club} {shift_type}")

                        # Notify requester
                        await context.bot.send_message(
                            chat_id=requester_id,
                            text=f"✅ {responder_name} согласился на обмен!\n\n{result_text}",
                            parse_mode='Markdown'
                        )

                        # Update responder's message
                        await query.edit_message_text(
                            result_text,
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]]),
                            parse_mode='Markdown'
                        )
                    else:
                        error_text = f"❌ Не удалось обновить расписание в Google Sheets.\n\n"
                        error_text += f"Возможно, ячейки защищены. Обратитесь к владельцу."

                        await query.edit_message_text(
                            error_text,
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]])
                        )

                        # Notify requester about failure
                        await context.bot.send_message(
                            chat_id=requester_id,
                            text=f"❌ {responder_name} согласился, но не удалось обновить расписание.\n\n{error_text}"
                        )

                except Exception as e:
                    logger.error(f"❌ Error updating Google Sheets for swap: {e}")
                    import traceback
                    traceback.print_exc()

                    error_text = f"❌ Ошибка при обновлении расписания: {e}"
                    await query.edit_message_text(
                        error_text,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]])
                    )

                    # Notify requester about error
                    await context.bot.send_message(
                        chat_id=requester_id,
                        text=f"❌ Технический сбой при обмене сменой:\n\n{error_text}"
                    )

            else:
                # Rejection
                result_text = f"❌ **Запрос отклонен**\n\n"
                result_text += f"📅 {shift_date.day} {month_name} ({weekday}) - {club_emoji} {club} {shift_emoji}\n\n"
                result_text += f"Вы отклонили запрос от {requester_name}."

                await query.edit_message_text(
                    result_text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]]),
                    parse_mode='Markdown'
                )

                # Notify requester
                await context.bot.send_message(
                    chat_id=requester_id,
                    text=f"❌ {responder_name} отклонил запрос на обмен сменой.\n\n"
                         f"📅 {shift_date.day} {month_name} ({weekday}) - {club_emoji} {club} {shift_emoji}"
                )

                logger.info(f"❌ Swap rejected: {requester_name} -> {responder_name} on {shift_date} {club} {shift_type}")

            # Remove swap request from pending
            context.bot_data['pending_swap_requests'].pop(swap_key, None)

        except Exception as e:
            logger.error(f"❌ Error handling swap response: {e}")
            import traceback
            traceback.print_exc()
            await query.edit_message_text(
                f"❌ Ошибка: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]])
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик inline-кнопок"""
        query = update.callback_query
        await query.answer()

        data = query.data
        logger.info(f"🔔 Callback received: {data} from user {query.from_user.id}")
        
        # Главное меню
        if data == "main_menu":
            text = self._get_main_menu_text(query.from_user.id)
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
        
        # Content generation menu
        if data == "content_menu":
            await self.content_commands.show_content_menu(query)
            return
        
        # Content type info
        if data == "content_image":
            await self.content_commands.show_content_type_info(query, 'image')
            return
        
        if data == "content_video":
            await self.content_commands.show_content_type_info(query, 'video')
            return
        
        # Content generation history
        if data == "content_history":
            await self.content_commands.show_generation_history(query)
            return
        
        # Model settings
        if data == "model_settings":
            await self.content_commands.show_model_settings(query)
            return
        
        # Model change handlers
        if data.startswith("model_"):
            model_name = data.replace("model_", "")
            await self.content_commands.handle_model_change(query, model_name)
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
                [InlineKeyboardButton("⚙️ Настройки GPT модели", callback_data="model_settings")],
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

        # Управление товарами
        if data == "product_menu":
            await self.product_commands.show_product_menu(update, context)
            return
        
        if data == "product_my_debt":
            await self.product_commands.show_my_debt(update, context)
            return
        
        if data == "product_all_debts" or data == "product_all_debts_by_name":
            await self.product_commands.show_all_debts(update, context)
            return
        
        if data == "product_report" or data == "product_report_by_product":
            await self.product_commands.show_products_report(update, context)
            return
        
        if data == "product_summary":
            await self.product_commands.show_products_summary(update, context)
            return
        
        if data == "product_detailed_debts":
            await self.product_commands.show_detailed_debts(update, context)
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
        
        # Check for callbacks that should be handled by ConversationHandlers
        if data in ("product_add", "product_edit_price", "product_set_nickname", "product_clear_debt", "issue_report"):
            # These are handled through conversation handlers
            return

        # Debt management callbacks (must be before product_clear_ to avoid conflicts)
        if data.startswith("product_manage_debt_"):
            logger.info(f"📋 Calling manage_admin_debt for callback: {data}")
            await self.product_commands.manage_admin_debt(update, context)
            return

        if data.startswith("product_notify_debt_"):
            await self.product_commands.notify_admin_debt(update, context)
            return

        if data.startswith("product_settle_debt_"):
            await self.product_commands.settle_admin_debt(update, context)
            return

        if data.startswith("product_clear_") and data != "product_clear_settled":
            await self.product_commands.clear_admin_debt(update, context)
            return

        # Проблемы клуба
        if data == "issue_menu":
            await self.issue_commands.show_issue_menu(update, context)
            return

        # Shifts menu
        if data == "shifts_menu":
            logger.info(f"shifts_menu callback from user {query.from_user.id} ({query.from_user.full_name})")
            await self._show_shifts_menu(query)
            return

        # View my shifts
        if data == "shifts_view":
            # Delete the old message first
            try:
                await query.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")

            # Send new message with shifts
            # Create a fake update with message that can send new messages
            class FakeMessage:
                def __init__(self, chat_id, bot):
                    self.chat_id = chat_id
                    self.bot = bot

                async def reply_text(self, text, **kwargs):
                    return await self.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

            class FakeUpdate:
                def __init__(self, user, message):
                    self.effective_user = user
                    self.message = message

            fake_message = FakeMessage(query.message.chat.id, context.bot)
            fake_update = FakeUpdate(query.from_user, fake_message)
            await self.schedule_commands.cmd_my_shifts(fake_update, context)
            return

        # Swap shifts - show user's shifts
        if data == "shifts_swap":
            await self._show_swap_shift_selection(query, context)
            return

        # Shift selected for swap - show admin selection
        if data.startswith("swap_select_"):
            await self._show_admin_selection_for_swap(query, context, data)
            return

        # Admin selected for swap - send confirmation request
        if data.startswith("swap_admin_"):
            await self._send_swap_request(query, context, data)
            return

        # Swap confirmation response
        if data.startswith("swap_confirm_") or data.startswith("swap_reject_"):
            await self._handle_swap_response(query, context, data)
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

        # Owner panel
        if data == "owner_panel" or data.startswith("owner_"):
            from modules.owner_panel import handle_owner_callback
            await handle_owner_callback(update, context)
            return

        # Controller panel and archive
        if data == "controller_panel" or data.startswith("ctrl_"):
            from modules.controller_panel import handle_controller_callback
            await handle_controller_callback(update, context)
            return

        # Обработчики кнопок смен
        if data == "shift_open":
            # Открыть смену - делегируем в finmon wizard
            if hasattr(self, 'shift_wizard') and self.shift_wizard is not None:
                await self.shift_wizard.cmd_open_shift(update, context)
            else:
                await query.answer("❌ Модуль смен не загружен", show_alert=True)
            return

        if data == "shift_close":
            # Закрыть смену - обрабатывается в ConversationHandler
            # Не нужно обрабатывать здесь, иначе ConversationHandler не сработает
            return

        # shift_expense обрабатывается в ConversationHandler для expense_handler

        # shift_salary обрабатывается в ConversationHandler для withdrawal_handler

        # Admin monitoring callbacks (owner only)
        if data == "monitor_main":
            if query.from_user.id != self.owner_id:
                await query.answer("❌ Доступ запрещён")
                return
            await self._show_monitor_main(update, context)
            return
        
        if data == "monitor_admins_list":
            if query.from_user.id != self.owner_id:
                await query.answer("❌ Доступ запрещён")
                return
            await self._show_admins_list(update, context)
            return
        
        if data.startswith("monitor_admin_chats_"):
            if query.from_user.id != self.owner_id:
                await query.answer("❌ Доступ запрещён")
                return
            # Parse: monitor_admin_chats_{user_id}_{period}_{filter}[_{offset}]
            parts = data.replace("monitor_admin_chats_", "").split("_")
            user_id = int(parts[0])
            period = parts[1] if len(parts) > 1 else 'today'
            filter_type = parts[2] if len(parts) > 2 else 'all'
            offset = int(parts[3]) if len(parts) > 3 else 0
            await self._show_admin_chats(update, context, user_id, period, filter_type, offset)
            return
        
        if data.startswith("monitor_admin_stats_"):
            if query.from_user.id != self.owner_id:
                await query.answer("❌ Доступ запрещён")
                return
            # Parse: monitor_admin_stats_{user_id}_{period}
            parts = data.replace("monitor_admin_stats_", "").split("_")
            user_id = int(parts[0])
            period = parts[1] if len(parts) > 1 else 'today'
            await self._show_admin_stats(update, context, user_id, period)
            return
        
        if data.startswith("monitor_activity_"):
            if query.from_user.id != self.owner_id:
                await query.answer("❌ Доступ запрещён")
                return
            # Parse: monitor_activity_{period}
            period = data.replace("monitor_activity_", "")
            await self._show_all_admins_activity(update, context, period)
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
        
        # Детали пользователя
        if data.startswith("v2userdetail_"):
            parts = data.replace("v2userdetail_", "").split("_", 1)
            server_name = parts[0]
            uuid = parts[1]
            await self._show_user_detail(query, server_name, uuid)
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
            parts = data.replace("v2deluser_", "").split("_", 1)
            server_name = parts[0]
            uuid = parts[1]
            await self._delete_user(query, server_name, uuid)
            return
        
        # Подтверждение удаления пользователя
        if data.startswith("v2deluser_confirm_"):
            parts = data.replace("v2deluser_confirm_", "").split("_", 1)
            server_name = parts[0]
            uuid = parts[1]
            await self._confirm_delete_user(query, server_name, uuid)
            return
        
        # Временный доступ - выбор периода
        if data.startswith("v2tempaccess_"):
            parts = data.replace("v2tempaccess_", "").split("_", 1)
            server_name = parts[0]
            uuid = parts[1]
            await self._show_temp_access_options(query, server_name, uuid)
            return
        
        # Временный доступ - установка
        if data.startswith("v2settemp_"):
            # Format: v2settemp_<server>_<uuid>_<days>
            parts = data.replace("v2settemp_", "").split("_")
            server_name = parts[0]
            uuid = parts[1]
            days = int(parts[2])
            await self._set_temp_access(query, server_name, uuid, days)
            return
        
        # Отключить временный доступ
        if data.startswith("v2removetemp_"):
            parts = data.replace("v2removetemp_", "").split("_", 1)
            server_name = parts[0]
            uuid = parts[1]
            await self._remove_temp_access(query, server_name, uuid)
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
        """Показать список пользователей сервера (из конфига Xray на сервере)"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            # Получаем пользователей напрямую с сервера из Xray config
            users = self.v2ray_manager.get_users(server_name)
            
            text = f"👥 Пользователи сервера {server_name}\n\n"
            
            if users:
                text += f"Всего: {len(users)}\n\n"
                for user in users:
                    text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    text += f"👤 {user['email']}\n"
                    text += f"🔑 UUID: {user['uuid'][:8]}...\n"
                    text += f"⚡ Flow: {user.get('flow', 'xtls-rprx-vision')}\n"
            else:
                text += "Нет пользователей\n"
            
            keyboard = []
            
            # Добавляем кнопки для каждого пользователя
            for user in users[:10]:  # Максимум 10 кнопок
                keyboard.append([
                    InlineKeyboardButton(
                        f"⚙️ {user['email'][:20]}", 
                        callback_data=f"v2userdetail_{server_name}_{user['uuid']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("➕ Добавить", callback_data=f"v2adduser_{server_name}"),
                InlineKeyboardButton("🔄 Обновить", callback_data=f"v2users_{server_name}")
            ])
            keyboard.append([
                InlineKeyboardButton("◀️ Назад", callback_data=f"v2server_{server_name}")
            ])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Error showing server users: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    async def _delete_user(self, query, server_name: str, uuid: str):
        """Показать подтверждение удаления пользователя"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            text = "⚠️ Подтверждение удаления\n\n"
            text += f"Вы действительно хотите удалить пользователя?\n"
            text += f"🔑 UUID: {uuid[:8]}...\n\n"
            text += "Это действие нельзя отменить!"
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Да, удалить", callback_data=f"v2deluser_confirm_{server_name}_{uuid}"),
                    InlineKeyboardButton("❌ Отмена", callback_data=f"v2userdetail_{server_name}_{uuid}")
                ]
            ]
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Error showing delete confirmation: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    async def _confirm_delete_user(self, query, server_name: str, uuid: str):
        """Удалить пользователя с сервера"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            await query.answer("⏳ Удаляю пользователя...")
            
            result = self.v2ray_manager.delete_user(server_name, uuid)
            
            if result:
                text = f"✅ Пользователь удалён\n\n"
                text += f"🔑 UUID: {uuid[:8]}...\n"
                text += f"Пользователь удалён из Xray конфигурации и базы данных."
            else:
                text = f"❌ Ошибка удаления пользователя\n\n"
                text += f"Проверьте логи для деталей."
            
            keyboard = [[InlineKeyboardButton("◀️ К списку", callback_data=f"v2users_{server_name}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Error deleting user: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    async def _show_user_detail(self, query, server_name: str, uuid: str):
        """Показать детали пользователя"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            # Получаем пользователей с сервера
            users = self.v2ray_manager.get_users(server_name)
            user = next((u for u in users if u['uuid'] == uuid), None)
            
            if not user:
                await query.answer("❌ Пользователь не найден")
                return
            
            # Проверяем временный доступ из БД
            temp_access = self.v2ray_manager.get_temp_access(server_name, uuid)
            
            text = f"👤 Детали пользователя\n\n"
            text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📧 Email: {user['email']}\n"
            text += f"🔑 UUID: `{uuid}`\n"
            text += f"⚡ Flow: {user.get('flow', 'xtls-rprx-vision')}\n"
            text += f"🖥️ Сервер: {server_name}\n"
            
            if temp_access:
                from datetime import datetime
                expires = datetime.fromisoformat(temp_access['expires_at'])
                now = datetime.now()
                if expires > now:
                    days_left = (expires - now).days
                    text += f"\n⏰ Временный доступ:\n"
                    text += f"   Истекает: {expires.strftime('%Y-%m-%d %H:%M')}\n"
                    text += f"   Осталось: {days_left} дней\n"
                else:
                    text += f"\n⚠️ Доступ истёк: {expires.strftime('%Y-%m-%d %H:%M')}\n"
            
            text += f"━━━━━━━━━━━━━━━━━━━━━━"
            
            keyboard = []
            
            # Кнопки управления временным доступом
            if temp_access:
                keyboard.append([
                    InlineKeyboardButton("🔄 Изменить срок", callback_data=f"v2tempaccess_{server_name}_{uuid}"),
                    InlineKeyboardButton("♾️ Убрать ограничение", callback_data=f"v2removetemp_{server_name}_{uuid}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("⏰ Временный доступ", callback_data=f"v2tempaccess_{server_name}_{uuid}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("🗑️ Удалить", callback_data=f"v2deluser_{server_name}_{uuid}")
            ])
            keyboard.append([
                InlineKeyboardButton("◀️ К списку", callback_data=f"v2users_{server_name}")
            ])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Error showing user detail: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    async def _show_temp_access_options(self, query, server_name: str, uuid: str):
        """Показать опции временного доступа"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            text = "⏰ Выберите срок доступа\n\n"
            text += "После истечения срока пользователь будет автоматически удалён."
            
            keyboard = [
                [
                    InlineKeyboardButton("1 день", callback_data=f"v2settemp_{server_name}_{uuid}_1"),
                    InlineKeyboardButton("3 дня", callback_data=f"v2settemp_{server_name}_{uuid}_3")
                ],
                [
                    InlineKeyboardButton("7 дней", callback_data=f"v2settemp_{server_name}_{uuid}_7"),
                    InlineKeyboardButton("14 дней", callback_data=f"v2settemp_{server_name}_{uuid}_14")
                ],
                [
                    InlineKeyboardButton("30 дней", callback_data=f"v2settemp_{server_name}_{uuid}_30"),
                    InlineKeyboardButton("60 дней", callback_data=f"v2settemp_{server_name}_{uuid}_60")
                ],
                [
                    InlineKeyboardButton("90 дней", callback_data=f"v2settemp_{server_name}_{uuid}_90")
                ],
                [
                    InlineKeyboardButton("◀️ Назад", callback_data=f"v2userdetail_{server_name}_{uuid}")
                ]
            ]
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Error showing temp access options: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    async def _set_temp_access(self, query, server_name: str, uuid: str, days: int):
        """Установить временный доступ"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            from datetime import datetime, timedelta
            expires_at = datetime.now() + timedelta(days=days)
            
            result = self.v2ray_manager.set_temp_access(server_name, uuid, expires_at)
            
            if result:
                text = f"✅ Временный доступ установлен\n\n"
                text += f"⏰ Срок: {days} дней\n"
                text += f"📅 Истекает: {expires_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                text += f"Пользователь будет автоматически удалён после истечения срока."
            else:
                text = f"❌ Ошибка установки временного доступа"
            
            keyboard = [[InlineKeyboardButton("◀️ К деталям", callback_data=f"v2userdetail_{server_name}_{uuid}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Error setting temp access: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}")
    
    async def _remove_temp_access(self, query, server_name: str, uuid: str):
        """Убрать временное ограничение доступа"""
        try:
            if not self.v2ray_commands.is_owner(query.from_user.id):
                await query.answer("❌ Доступ запрещён")
                return
            
            result = self.v2ray_manager.remove_temp_access(server_name, uuid)
            
            if result:
                text = f"✅ Временное ограничение снято\n\n"
                text += f"Пользователь теперь имеет постоянный доступ."
            else:
                text = f"❌ Ошибка снятия ограничения"
            
            keyboard = [[InlineKeyboardButton("◀️ К деталям", callback_data=f"v2userdetail_{server_name}_{uuid}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"❌ Error removing temp access: {e}", exc_info=True)
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

        # DEBUG: Log all incoming messages
        logger.info(f"📨 Message from {user.id}: '{text}' (len={len(text)}, repr={repr(text)})")

        # IMPORTANT: Skip if user is in a conversation (ConversationHandler is active)
        # Check for common conversation states to avoid conflicts
        conversation_keys = [
            'shift_data', 'shift_club', 'shift_type',  # Shift closing
            'product_add_state', 'product_take_state',  # Product management
            'issue_state',  # Issue reporting
            'checklist_manager', 'checklist_shift_id',  # Checklist
            'waiting_for_expense_amount', 'waiting_for_withdrawal_amount'  # Finance
        ]

        # If any conversation key exists in user_data, skip general message handling
        if any(key in context.user_data for key in conversation_keys):
            logger.info(f"⏩ Skipping message handling - user in conversation (keys: {[k for k in conversation_keys if k in context.user_data]})")
            return

        # Note: Reply keyboard buttons are handled by MessageHandlers in group=-1
        # See button handlers registration at the top of run() method

        # Skip processing for reply keyboard buttons to prevent "Не знаю ответа" error
        BUTTON_TEXTS = ["🔒 Закрыть смену", "🔓 Открыть смену", "💸 Списать с кассы", "💰 Взять зарплату", "📊 Меню"]
        if text in BUTTON_TEXTS:
            logger.info(f"🔘 Skipping button text: {text}")
            return

        if len(text) < 3:
            return
        
        # Log admin messages automatically
        if self.admin_manager.is_admin(user.id):
            try:
                is_command = text.startswith('/')
                chat_type = message.chat.type  # 'private', 'group', 'supergroup'
                self.admin_manager.log_admin_message(
                    user_id=user.id,
                    username=user.username or "",
                    full_name=user.full_name or "",
                    text=text,
                    chat_id=message.chat.id,
                    chat_type=chat_type,
                    is_command=is_command
                )
            except Exception as e:
                logger.error(f"❌ Error logging admin message: {e}")
        
        # Автообучение ОТКЛЮЧЕНО для экономии OpenAI API ($20/день было!)
        # Можно включить вручную через команду /learn если нужно
        # if message.chat.type != 'private':
        #     try:
        #         self.smart_learner.learn_from_message(text, user.id)
        #     except Exception as e:
        #         logger.error(f"❌ Auto-learn error: {e}")
        
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

            # ВНИМАНИЕ: GPT-4o дорогой! (~$2.50 input + $10 output за 1M токенов)
            # Вызывается только когда бота упоминают с фото
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

        # Настройка Bot Menu (команды в меню Telegram)
        logger.info("⚙️ Настройка Bot Menu...")
        try:
            from telegram import BotCommand
            commands = [
                BotCommand("start", "🏠 Главное меню"),
                BotCommand("menu", "📊 Показать меню"),
                BotCommand("help", "❓ Справка"),
                BotCommand("admins", "👥 Управление админами (owner)"),
                BotCommand("finmon", "💰 Финансовый мониторинг"),
                BotCommand("shiftstatus", "📊 Статус смен и касс"),
                BotCommand("salary", "💼 Система зарплат"),
                BotCommand("products", "📦 Управление товарами"),
                BotCommand("issues", "🐛 Проблемы клуба"),
                BotCommand("v2ray", "🔐 V2Ray VPN"),
                BotCommand("content", "🎨 Генерация контента"),
            ]
            await application.bot.set_my_commands(commands)
            logger.info("✅ Bot Menu настроено")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось настроить Bot Menu: {e}")

        # IssueCommands теперь инициализируется в run() сразу после создания Application
        # self.issue_commands = IssueCommands(self.issue_manager, self.kb, self.admin_manager, self.owner_id, application)
    
    def run(self):
        """Запуск бота"""
        logger.info("🤖 Запуск бота...")
        
        # 1. Инициализация команд ПЕРЕД созданием Application
        logger.info("Инициализация команд...")
        
        try:
            # Получаем ID клубных аккаунтов из конфига
            # Используем список всех клубных аккаунтов
            club_accounts = self.config.get('club_accounts', {})
            club_account_ids = list(club_accounts.values()) if club_accounts else []

            self.product_commands = ProductCommands(
                self.product_manager,
                self.admin_manager,
                self.owner_id,
                shift_manager=None,  # Будет установлен позже
                club_account_id=club_account_ids  # Передаем список ID
            )
            logger.info("✅ ProductCommands инициализированы")
        except Exception as e:
            logger.error(f"❌ Ошибка при инициализации ProductCommands: {e}")
            raise
        
        # 2. Создание Application
        application = Application.builder().token(self.config['telegram_token']).build()
        logger.info("✅ Application создан")
        
        # 3. Инициализируем IssueCommands (требует application)
        club_accounts = self.config.get('club_accounts', {})
        club_account_ids = list(club_accounts.values()) if club_accounts else []

        self.issue_commands = IssueCommands(
            self.issue_manager,
            self.kb,
            self.admin_manager,
            self.owner_id,
            application,
            shift_manager=None,  # Будет установлен позже
            club_account_id=club_account_ids  # Передаем список ID
        )
        logger.info("✅ IssueCommands инициализированы")
        
        application.post_init = self.post_init
        
        # 4. Регистрируем обработчики
        application.add_handler(CommandHandler("start", self.cmd_start))
        application.add_handler(CommandHandler("menu", self.cmd_start))  # Алиас для /start
        application.add_handler(CommandHandler("cancel", self.cmd_cancel_general))  # Общая отмена
        application.add_handler(CommandHandler("help", self.cmd_help))
        application.add_handler(CommandHandler("stats", self.cmd_stats))
        application.add_handler(CommandHandler("id", self.cmd_id))
        application.add_handler(CommandHandler("admin", self.cmd_admin))
        application.add_handler(CommandHandler("learn", self.cmd_learn))
        application.add_handler(CommandHandler("cleanup", self.cmd_cleanup))
        application.add_handler(CommandHandler("fixdb", self.cmd_fixdb))
        application.add_handler(CommandHandler("deletetrash", self.cmd_deletetrash))
        application.add_handler(CommandHandler("viewrecord", self.cmd_viewrecord))
        application.add_handler(CommandHandler("fixjson", self.cmd_fixjson))
        application.add_handler(CommandHandler("import", self.cmd_import))
        application.add_handler(CommandHandler("addadmin", self.cmd_addadmin))
        application.add_handler(CommandHandler("savecreds", self.cmd_savecreds))
        application.add_handler(CommandHandler("getcreds", self.cmd_getcreds))
        application.add_handler(CommandHandler("update", self.cmd_update))
        
        # Owner-only admin monitoring commands
        application.add_handler(CommandHandler("setname", self.cmd_setname))
        application.add_handler(CommandHandler("adminchats", self.cmd_adminchats))
        application.add_handler(CommandHandler("adminstats", self.cmd_adminstats))
        application.add_handler(CommandHandler("adminmonitor", self.cmd_adminmonitor))
        
        # Content generation commands
        application.add_handler(CommandHandler("image", self.cmd_image))
        if self.video_generator:
            application.add_handler(CommandHandler("video", self.cmd_video))

        # Message summarizer commands
        if self.message_summarizer:
            application.add_handler(CommandHandler("summary", self.cmd_summary))
        
        # === BUTTON HANDLERS ===
        # Note: Button handlers for "Закрыть смену", "Списать с кассы", "Взять зарплату"
        # are now registered as entry_points in their respective ConversationHandlers below

        # Keep only the "Открыть смену" button handler since it doesn't use ConversationHandler
        async def handle_open_shift_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle open shift button"""
            logger.info(f"🔓 HANDLER: Open shift button pressed by user {update.effective_user.id}")
            await self.shift_wizard.cmd_open_shift(update, context)

        application.add_handler(MessageHandler(
            filters.TEXT & filters.Regex("^🔓 Открыть смену$"),
            handle_open_shift_button
        ), group=-1)
        
        # === CONVERSATION HANDLERS (must be registered BEFORE CallbackQueryHandler) ===
        
        # ConversationHandler для финансового мониторинга
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
        
        # ConversationHandler для установки никнейма админа
        product_nickname_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.product_commands.start_set_nickname, pattern="^product_set_nickname$")
            ],
            states={
                PRODUCT_SET_NICKNAME: [
                    CallbackQueryHandler(self.product_commands.select_admin_for_nickname, pattern="^product_nickname_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.product_commands.enter_nickname)
                ]
            },
            fallbacks=[CallbackQueryHandler(self.product_commands.cancel, pattern="^product_menu$")]
        )
        application.add_handler(product_nickname_handler)
        
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

        # ConversationHandler для чек-листа приема смены
        try:
            checklist_handler = create_checklist_conversation_handler()
            application.add_handler(checklist_handler)
            logger.info("✅ Shift checklist ConversationHandler registered")
        except Exception as e:
            logger.error(f"❌ Failed to register checklist handler: {e}")
            import traceback
            traceback.print_exc()

        # Callback handler для уведомления контролера о проблемах
        try:
            from modules.shift_checklist import notify_controller
            application.add_handler(CallbackQueryHandler(notify_controller, pattern="^checklist_notify_controller$"))
            logger.info("✅ Checklist notify controller handler registered")
        except Exception as e:
            logger.error(f"❌ Failed to register notify controller handler: {e}")

        # === END CONVERSATION HANDLERS ===
        
        # Admin Management module (MUST be registered BEFORE general CallbackQueryHandler)
        try:
            admin_db, admin_wizard = register_admins(application, self.config, DB_PATH, self.bot_username)
            # Store admin_db for use in commands
            self.admin_db = admin_db
            # Store the admin invite interceptor
            if 'admin_invite_interceptor' in application.bot_data:
                self.admin_invite_interceptor = application.bot_data['admin_invite_interceptor']
            logger.info("✅ Admin Management module registered")
        except Exception as e:
            logger.error(f"❌ Admin Management module registration failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Backup and Migration commands module
        try:
            backup_config = {
                'db_path': DB_PATH,
                'backup_dir': os.getenv('BACKUP_DIR', './backups'),
                'owner_ids': os.getenv('OWNER_TG_IDS', ''),
                'backup_interval_days': os.getenv('BACKUP_INTERVAL_DAYS', '14')
            }
            register_backup_commands(application, backup_config)
            logger.info("✅ Backup commands module registered")
        except Exception as e:
            logger.error(f"❌ Backup commands module registration failed: {e}")
            import traceback
            traceback.print_exc()
        
        # FinMon Simple module - Financial Monitoring (JSON/CSV based, no DB)
        self.shift_wizard = None  # Initialize to None first
        try:
            from modules.finmon_simple import FinMonSimple
            from modules.finmon_schedule import FinMonSchedule
            from modules.shift_manager import ShiftManager
            from modules.schedule_parser import ScheduleParser
            from modules.finmon_shift_wizard import (
                ShiftWizard, SELECT_CLUB, CONFIRM_IDENTITY,
                ENTER_FACT_CASH, ENTER_FACT_CARD, ENTER_QR, ENTER_CARD2,
                ENTER_SAFE, ENTER_ACTUAL_CASH, ENTER_BOX, ENTER_TOVARKA,
                ENTER_GAMEPADS, ENTER_REPAIR, ENTER_NEED_REPAIR, ENTER_GAMES,
                UPLOAD_Z_CASH, UPLOAD_Z_CARD, UPLOAD_Z_QR, UPLOAD_Z_CARD2,
                CONFIRM_SHIFT,
                EXPENSE_SELECT_CASH_SOURCE, EXPENSE_ENTER_AMOUNT, EXPENSE_ENTER_REASON, EXPENSE_CONFIRM,
                WITHDRAWAL_SELECT_CASH_SOURCE, WITHDRAWAL_ENTER_AMOUNT, WITHDRAWAL_CONFIRM
            )
            
            # Get owner IDs
            owner_ids_str = os.getenv('OWNER_TG_IDS', '')
            owner_ids = []
            if owner_ids_str:
                try:
                    owner_ids = [int(id.strip()) for id in owner_ids_str.split(',') if id.strip()]
                except ValueError:
                    logger.error("❌ Invalid OWNER_TG_IDS format")
            
            # If no owner IDs from env, use config
            if not owner_ids and hasattr(self, 'owner_id'):
                owner_ids = [self.owner_id]
            
            if not owner_ids:
                logger.warning("⚠️ No OWNER_TG_IDS configured, using fallback from config")
            
            # Initialize FinMon Simple components
            finmon_simple = FinMonSimple()
            
            # Initialize shift manager
            shift_manager = ShiftManager(DB_PATH)
            self.shift_manager = shift_manager  # Store for keyboard updates

            # Установить shift_manager в product_commands и issue_commands
            if hasattr(self, 'product_commands'):
                self.product_commands.shift_manager = shift_manager
            if hasattr(self, 'issue_commands'):
                self.issue_commands.shift_manager = shift_manager

            # Initialize schedule parser with Google Sheets support
            google_sa_json = os.getenv('GOOGLE_SA_JSON')
            google_sheet_id = os.getenv('GOOGLE_SHEET_ID', '19ILASe6UH7-j1okxg9mvz_GrkQAkCJLXA1mxwocLcV8')
            
            schedule_parser = None
            finmon_schedule = None
            
            if google_sa_json:
                try:
                    # Get admin_db instance if available
                    admin_db_instance = admin_db if hasattr(self, 'admin_db') else None
                    
                    # Create schedule parser with Google Sheets
                    schedule_parser = ScheduleParser(
                        shift_manager=shift_manager,
                        admin_db=admin_db_instance,
                        spreadsheet_id=google_sheet_id,
                        credentials_path=google_sa_json
                    )
                    logger.info(f"✅ Google Sheets schedule parser enabled (Sheet: {google_sheet_id[:15]}...)")
                    
                    # Legacy schedule support (for compatibility)
                    try:
                        finmon_schedule = FinMonSchedule(google_sa_json)
                        logger.info("✅ Legacy FinMonSchedule also enabled")
                    except Exception as e:
                        logger.info(f"ℹ️ Legacy FinMonSchedule disabled: {e}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Google Sheets parser disabled: {e}")
                    # Fallback to basic parser
                    schedule_parser = ScheduleParser(shift_manager)
            else:
                logger.info("ℹ️ Google Sheets parser disabled (no GOOGLE_SA_JSON)")
                # Create basic parser without Google Sheets
                schedule_parser = ScheduleParser(shift_manager)
            
            # Initialize shift wizard with managers
            shift_wizard = ShiftWizard(
                finmon_simple=finmon_simple,
                schedule=finmon_schedule,
                shift_manager=shift_manager,
                schedule_parser=schedule_parser,
                owner_ids=owner_ids,
                bot_instance=self,
                admin_db=admin_db,
                db_path=DB_PATH,
                openai_key=self.config.get('openai_api_key'),
                controller_id=self.config.get('controller_id')
            )
            self.shift_wizard = shift_wizard  # Store for button handler
            
            # Initialize salary system
            from modules.salary_calculator import SalaryCalculator
            from modules.salary_commands import SalaryCommands
            
            salary_calculator = SalaryCalculator(DB_PATH, shift_manager)
            salary_commands = SalaryCommands(salary_calculator, admin_db, owner_ids)
            
            # Register salary commands
            application.add_handler(CommandHandler("salary", salary_commands.cmd_salary))
            application.add_handler(CallbackQueryHandler(salary_commands.handle_callback, pattern="^salary_"))
            
            # Register /balances and /movements commands
            application.add_handler(CommandHandler("balances", shift_wizard.cmd_balances))
            application.add_handler(CommandHandler("movements", shift_wizard.cmd_movements))
            application.add_handler(CommandHandler("shiftstatus", shift_wizard.cmd_shift_status))

            # Register /shift conversation handler (CLOSE shift)
            shift_handler = ConversationHandler(
                entry_points=[
                    CommandHandler("shift", shift_wizard.cmd_shift),
                    MessageHandler(filters.TEXT & filters.Regex("^🔒 Закрыть смену$"), shift_wizard.cmd_shift),
                    CallbackQueryHandler(shift_wizard.start_close_shift, pattern="^shift_close$")
                ],
                states={
                    ENTER_FACT_CASH: [
                        CallbackQueryHandler(shift_wizard.handle_cash_no_change, pattern="^cash_no_change$"),
                        CallbackQueryHandler(shift_wizard.handle_cash_disabled, pattern="^cash_disabled$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_fact_cash)
                    ],
                    ENTER_FACT_CARD: [
                        CallbackQueryHandler(shift_wizard.handle_card_no_change, pattern="^card_no_change$"),
                        CallbackQueryHandler(shift_wizard.handle_card_disabled, pattern="^card_disabled$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_fact_card)
                    ],
                    ENTER_QR: [
                        CallbackQueryHandler(shift_wizard.handle_qr_no_change, pattern="^qr_no_change$"),
                        CallbackQueryHandler(shift_wizard.handle_qr_disabled, pattern="^qr_disabled$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_qr)
                    ],
                    ENTER_CARD2: [
                        CallbackQueryHandler(shift_wizard.handle_card2_no_change, pattern="^card2_no_change$"),
                        CallbackQueryHandler(shift_wizard.handle_card2_disabled, pattern="^card2_disabled$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_card2)
                    ],
                    UPLOAD_Z_CASH: [
                        CallbackQueryHandler(shift_wizard.handle_skip_z_cash, pattern="^skip_z_cash$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.PHOTO, shift_wizard.upload_z_cash)
                    ],
                    UPLOAD_Z_CARD: [
                        CallbackQueryHandler(shift_wizard.handle_skip_z_card, pattern="^skip_z_card$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.PHOTO, shift_wizard.upload_z_card)
                    ],
                    UPLOAD_Z_QR: [
                        CallbackQueryHandler(shift_wizard.handle_skip_z_qr, pattern="^skip_z_qr$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.PHOTO, shift_wizard.upload_z_qr)
                    ],
                    UPLOAD_Z_CARD2: [
                        CallbackQueryHandler(shift_wizard.handle_skip_z_card2, pattern="^skip_z_card2$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.PHOTO, shift_wizard.upload_z_card2)
                    ],
                    ENTER_SAFE: [
                        CallbackQueryHandler(shift_wizard.handle_safe_no_change, pattern="^safe_no_change$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_safe)
                    ],
                    ENTER_ACTUAL_CASH: [
                        CallbackQueryHandler(shift_wizard.handle_actual_cash_matches, pattern="^actual_cash_matches$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_actual_cash)
                    ],
                    ENTER_BOX: [
                        CallbackQueryHandler(shift_wizard.handle_box_no_change, pattern="^box_no_change$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$"),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_box)
                    ],
                    CONFIRM_SHIFT: [
                        CallbackQueryHandler(shift_wizard.confirm_shift, pattern="^shift_confirm$"),
                        CallbackQueryHandler(shift_wizard.edit_shift, pattern="^shift_edit$"),
                        CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$")
                    ]
                },
                fallbacks=[
                    CommandHandler("cancel", shift_wizard.cancel_command),
                    CallbackQueryHandler(shift_wizard.cancel_shift, pattern="^shift_cancel$")
                ]
            )
            application.add_handler(shift_handler)
            
            # Register expense tracking conversation handler
            expense_handler = ConversationHandler(
                entry_points=[
                    CommandHandler("expense", shift_wizard.cmd_expense),
                    MessageHandler(filters.TEXT & filters.Regex("^💸 Списать с кассы$"), shift_wizard.cmd_expense),
                    CallbackQueryHandler(shift_wizard.start_expense, pattern="^shift_expense$")
                ],
                states={
                    EXPENSE_SELECT_CASH_SOURCE: [
                        CallbackQueryHandler(shift_wizard.expense_select_cash_source, pattern="^expense_")
                    ],
                    EXPENSE_ENTER_AMOUNT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.expense_receive_amount)
                    ],
                    EXPENSE_ENTER_REASON: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.expense_receive_reason)
                    ],
                    EXPENSE_CONFIRM: [
                        CallbackQueryHandler(shift_wizard.expense_confirm, pattern="^expense_")
                    ]
                },
                fallbacks=[
                    CommandHandler("cancel", shift_wizard.cancel_command)
                ]
            )
            application.add_handler(expense_handler)
            
            # Register cash withdrawal conversation handler
            withdrawal_handler = ConversationHandler(
                entry_points=[
                    CommandHandler("withdrawal", shift_wizard.start_cash_withdrawal),
                    MessageHandler(filters.TEXT & filters.Regex("^💰 Взять зарплату$"), shift_wizard.start_cash_withdrawal),
                    CallbackQueryHandler(shift_wizard.start_cash_withdrawal, pattern="^shift_salary$")
                ],
                states={
                    WITHDRAWAL_SELECT_CASH_SOURCE: [
                        CallbackQueryHandler(shift_wizard.withdrawal_select_cash_source, pattern="^withdrawal_")
                    ],
                    WITHDRAWAL_ENTER_AMOUNT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_withdrawal_amount)
                    ],
                    WITHDRAWAL_CONFIRM: [
                        CallbackQueryHandler(shift_wizard.handle_withdrawal_confirmation, pattern="^withdrawal_")
                    ]
                },
                fallbacks=[
                    CommandHandler("cancel", shift_wizard.cancel_command)
                ]
            )
            application.add_handler(withdrawal_handler)

            # Register withdrawal revert handler (only for controller)
            application.add_handler(CallbackQueryHandler(
                shift_wizard.handle_revert_withdrawal,
                pattern="^revert_withdrawal_"
            ))
            
            # Register callback handlers for shift opening (not in conversation)
            application.add_handler(CallbackQueryHandler(shift_wizard.handle_open_club_selection, pattern="^open_"))
            application.add_handler(CallbackQueryHandler(shift_wizard.handle_confirm_scheduled, pattern="^confirm_scheduled_"))
            application.add_handler(CallbackQueryHandler(shift_wizard.handle_select_replacement, pattern="^select_replacement_"))
            application.add_handler(CallbackQueryHandler(shift_wizard.handle_admin_selected, pattern="^admin_selected_"))
            
            # Register /finmon command for analytics
            application.add_handler(CommandHandler("finmon", shift_wizard.cmd_finmon))
            
            # Register finmon callbacks (must be BEFORE general callback handler)
            application.add_handler(CallbackQueryHandler(
                shift_wizard.handle_finmon_callback, 
                pattern="^finmon_"
            ))
            
            # Register schedule integration callbacks
            application.add_handler(CallbackQueryHandler(
                shift_wizard.handle_duty_replacement_response,
                pattern="^duty_(confirm|reject)_"
            ))
            application.add_handler(CallbackQueryHandler(
                shift_wizard.handle_owner_schedule_update,
                pattern="^owner_schedule_(yes|no)_"
            ))
            
            # Register schedule management commands
            from modules.schedule_commands import ScheduleCommands
            schedule_commands = ScheduleCommands(
                shift_manager=shift_manager,
                owner_ids=owner_ids,
                schedule_parser=schedule_parser,
                admin_db=admin_db_instance
            )
            application.add_handler(CommandHandler("schedule", schedule_commands.cmd_schedule))
            application.add_handler(CommandHandler("my_shifts", schedule_commands.cmd_my_shifts))
            application.add_handler(MessageHandler(
                filters.TEXT & filters.Regex("^📅 Мои смены$"),
                schedule_commands.cmd_my_shifts
            ))
            self.schedule_commands = schedule_commands  # Store for button handler

            logger.info("✅ Shift wizard registered")
            logger.info("   Commands: /shift, /balances, /movements, /finmon, /schedule, /my_shifts")
            logger.info("   Buttons: 💰 Сдать смену, 📅 Мои смены")

            # ================================================
            # Finance Analytics Module
            # ================================================
            try:
                from modules.finance_analytics import FinanceAnalytics, register_analytics_commands

                analytics = FinanceAnalytics(
                    db_path="club_assistant.db",
                    sheets_parser=schedule_parser if schedule_parser else None
                )

                # Регистрация команд аналитики
                register_analytics_commands(application, analytics, self.admin_manager)

                logger.info("✅ Finance Analytics registered")
                logger.info("   Commands: /salaries, /movements, /performance")

            except Exception as e:
                logger.warning(f"⚠️ Finance Analytics module registration failed: {e}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            logger.warning(f"⚠️ FinMon Simple module registration failed: {e}")
            import traceback
            traceback.print_exc()

        # Controller panel - обрабатывается в главном handle_callback
        # Store database path and controller_id in bot_data for controller panel
        application.bot_data['db_path'] = DB_PATH  # Use the same DB_PATH as the main bot
        application.bot_data['controller_id'] = self.config.get('controller_id')
        application.bot_data['owner_id'] = self.owner_id
        application.bot_data['schedule_parser'] = schedule_parser  # Для использования в maintenance_manager
        logger.info("✅ Controller panel data stored in bot_data")

        # Duty shift handlers
        try:
            duty_handlers = create_duty_shift_handlers()
            for handler in duty_handlers:
                application.add_handler(handler)
            logger.info("✅ Duty shift handlers registered")
        except Exception as e:
            logger.error(f"❌ Failed to register duty shift handlers: {e}")
            import traceback
            traceback.print_exc()

        # Maintenance task handlers
        try:
            maintenance_handlers = create_maintenance_handlers()
            for handler in maintenance_handlers:
                application.add_handler(handler)
            logger.info("✅ Maintenance task handlers registered")
        except Exception as e:
            logger.error(f"❌ Failed to register maintenance task handlers: {e}")
            import traceback
            traceback.print_exc()

        # New shift checklist handlers (cleaning rating, service reviews, inventory)
        try:
            # Cleaning rating handlers
            cleaning_rating_handlers = create_cleaning_rating_handlers()
            for handler in cleaning_rating_handlers:
                application.add_handler(handler)
            logger.info("✅ Shift cleaning rating handlers registered")

            # Cleaning service review handlers
            cleaning_review_handlers = create_cleaning_review_handlers()
            for handler in cleaning_review_handlers:
                application.add_handler(handler)
            logger.info("✅ Cleaning service review handlers registered")

            # Inventory checklist handlers
            inventory_handlers = create_inventory_handlers()
            for handler in inventory_handlers:
                application.add_handler(handler)
            logger.info("✅ Inventory checklist handlers registered")

            # Store shift_manager in bot_data for checklist access
            if hasattr(self, 'shift_wizard') and self.shift_wizard:
                application.bot_data['shift_manager'] = self.shift_wizard.shift_manager

        except Exception as e:
            logger.error(f"❌ Failed to register shift checklist handlers: {e}")
            import traceback
            traceback.print_exc()

        # Setup JobQueue for shift reminders
        try:
            # Store club accounts in bot_data for reminders
            application.bot_data['club_accounts'] = self.config.get('club_accounts', {})

            # Setup all reminder jobs
            setup_reminder_jobs(application)
            logger.info("✅ Shift reminder jobs scheduled")
            logger.info("   Jobs: unopened shifts, inventory deadlines, cleaning rating deadlines, system health")
        except Exception as e:
            logger.error(f"❌ Failed to setup reminder jobs: {e}")
            import traceback
            traceback.print_exc()

        # Обработчик inline-кнопок (must be AFTER ConversationHandlers and module registrations)
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
        
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Log registered commands summary
        logger.info("=" * 60)
        logger.info("📋 Registered commands summary:")
        logger.info("   Core: /start, /help, /stats")
        logger.info("   Content: /image, /video")
        logger.info("   FinMon: /shift, /balances, /movements, /finmon")
        logger.info("   Schedule: /schedule (add, week, today, remove, clear)")
        logger.info("   Owner: /apply_migrations, /migration, /backup")
        logger.info("   Admin: /admins, /v2ray")
        logger.info("   Reply keyboard: 🔓 Открыть смену / 🔒 Закрыть смену, 💸 Списать с кассы, 💰 Взять зарплату (динамическая)")
        logger.info("   Salary system: /salary command enabled")
        logger.info("=" * 60)

        logger.info(f"🤖 Бот v{VERSION} запущен!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"Ошибка: {CONFIG_PATH}")
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
    
    # Admin chat logs table for monitoring
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        full_name TEXT,
        message_text TEXT,
        chat_id INTEGER,
        chat_type TEXT,
        is_command BOOLEAN DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES admins(user_id))''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_chat_logs_user ON admin_chat_logs(user_id, timestamp DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_chat_logs_timestamp ON admin_chat_logs(timestamp DESC)')
    
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
