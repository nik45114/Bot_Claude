#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Assistant Bot v3.0
Умное обучение, авто-теги, дедупликация
"""

import os
import sys
import sqlite3
import json
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher

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

# Настройки
CONFIG_PATH = 'config.json'
DB_PATH = 'knowledge.db'

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class AdminManager:
    """Управление администраторами"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.pending_admins = {}  # Временное хранилище для подтверждений
    
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
    
    def get_admin(self, user_id: int) -> dict:
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
    
    def list_admins(self) -> list:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, username, full_name, can_teach, can_import, can_manage_admins FROM admins WHERE is_active = 1')
            admins = cursor.fetchall()
            conn.close()
            return admins
        except:
            return []
    
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
    
    def save_credentials(self, user_id: int, service: str, login: str, password: str, notes: str = '') -> bool:
        """Сохранение личных данных админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admin_credentials (user_id, service, login, password, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, service, login, password, notes))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка save_credentials: {e}")
            return False
    
    def get_credentials(self, user_id: int, service: str = None) -> list:
        """Получение личных данных админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if service:
                cursor.execute('''
                    SELECT service, login, password, notes, created_at 
                    FROM admin_credentials 
                    WHERE user_id = ? AND service = ?
                    ORDER BY created_at DESC
                ''', (user_id, service))
            else:
                cursor.execute('''
                    SELECT service, login, password, notes, created_at 
                    FROM admin_credentials 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
            
            creds = cursor.fetchall()
            conn.close()
            return creds
        except:
            return []


class KnowledgeBase:
    """База знаний с умным поиском и дедупликацией"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица знаний
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '',
                source TEXT DEFAULT '',
                added_by INTEGER,
                version INTEGER DEFAULT 1,
                is_current BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_question ON knowledge(question)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_current ON knowledge(is_current)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags ON knowledge(tags)')
        
        # Таблица администраторов
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
        
        # Таблица личных данных админов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service TEXT NOT NULL,
                login TEXT,
                password TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES admins(user_id)
            )
        ''')
        
        # Таблица проверок здоровья
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_type TEXT,
                status TEXT,
                details TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных готова")
    
    def add(self, question: str, answer: str, category: str = 'general', 
            tags: str = '', source: str = '', added_by: int = None) -> bool:
        """Добавляет вопрос-ответ в базу"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Проверяем есть ли уже такой вопрос
            cursor.execute(
                'SELECT id, version FROM knowledge WHERE LOWER(question) = LOWER(?) AND is_current = 1',
                (question,)
            )
            existing = cursor.fetchone()
            
            if existing:
                old_id, old_version = existing
                # Делаем старую запись legacy
                cursor.execute(
                    'UPDATE knowledge SET is_current = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (old_id,)
                )
                new_version = old_version + 1
            else:
                new_version = 1
            
            # Добавляем новую версию
            cursor.execute('''
                INSERT INTO knowledge 
                (question, answer, category, tags, source, added_by, version, is_current)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ''', (question, answer, category, tags, source, added_by, new_version))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Добавлено: {question[:50]}... [категория: {category}, теги: {tags}]")
            return True
        except Exception as e:
            logger.error(f"Ошибка add: {e}")
            return False
    
    async def smart_add(self, question: str, answer: str, gpt_client, added_by: int = None) -> dict:
        """Умное добавление с авто-тегами, категорией и поиском дублей"""
        try:
            # 1. Генерируем теги и категорию через GPT
            analysis = await self._analyze_content(question, answer, gpt_client)
            
            # 2. Проверяем дубликаты
            duplicates = self.find_duplicates(question, answer)
            
            if duplicates:
                logger.info(f"Найдено {len(duplicates)} похожих записей")
                # Объединяем теги
                all_tags = set(filter(None, analysis['tags'].split(',')))
                for dup in duplicates:
                    if dup.get('tags'):
                        all_tags.update(filter(None, dup['tags'].split(',')))
                
                analysis['tags'] = ','.join(sorted(all_tags))
                
                # Помечаем старые как неактуальные
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                for dup in duplicates:
                    cursor.execute(
                        'UPDATE knowledge SET is_current = 0 WHERE id = ?',
                        (dup['id'],)
                    )
                conn.commit()
                conn.close()
            
            # 3. Добавляем в базу
            success = self.add(
                question=question,
                answer=answer,
                category=analysis['category'],
                tags=analysis['tags'],
                source='smart_learn',
                added_by=added_by
            )
            
            return {
                'success': success,
                'category': analysis['category'],
                'tags': analysis['tags'],
                'duplicates_merged': len(duplicates) if duplicates else 0
            }
            
        except Exception as e:
            logger.error(f"Ошибка smart_add: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _analyze_content(self, question: str, answer: str, gpt_client) -> dict:
        """Анализ контента через GPT для получения тегов и категории"""
        try:
            prompt = f"""Проанализируй вопрос и ответ. Верни ТОЛЬКО JSON без лишнего текста:

Вопрос: {question}
Ответ: {answer}

Формат (СТРОГО JSON):
{{
  "category": "одна_категория",
  "tags": "тег1,тег2,тег3"
}}

Категории (выбери одну):
- hardware (железо, ПК, периферия)
- software (программы, ОС, утилиты)
- games (игры, Steam, лаунчеры)
- service (услуги клуба, цены, время)
- admin (администрирование, управление)
- billing (оплата, счета, абонементы)
- schedule (расписание, время работы)
- general (остальное)

Теги: 3-5 ключевых слов через запятую (на русском, без пробелов после запятых)"""

            response = await gpt_client.ask(prompt)
            
            # Парсим JSON
            try:
                # Ищем JSON в ответе
                start = response.find('{')
                end = response.rfind('}') + 1
                
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    analysis = json.loads(json_str)
                    
                    # Валидация
                    valid_categories = ['hardware', 'software', 'games', 'service', 'admin', 'billing', 'schedule', 'general']
                    if analysis.get('category') not in valid_categories:
                        analysis['category'] = 'general'
                    
                    # Очистка тегов
                    tags = analysis.get('tags', '')
                    tags = re.sub(r'\s+', '', tags)  # Убираем все пробелы
                    tags = ','.join(filter(None, tags.split(',')))  # Убираем пустые
                    analysis['tags'] = tags[:200]  # Максимум 200 символов
                    
                    return analysis
            except:
                pass
            
            # Если не удалось распарсить - дефолт
            return {
                'category': 'general',
                'tags': ''
            }
            
        except Exception as e:
            logger.error(f"Ошибка _analyze_content: {e}")
            return {
                'category': 'general',
                'tags': ''
            }
    
    def find_duplicates(self, question: str, answer: str = None, threshold: float = 0.80) -> list:
        """Находит похожие вопросы (потенциальные дубликаты)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, question, answer, tags, category
                FROM knowledge 
                WHERE is_current = 1
            ''')
            records = cursor.fetchall()
            conn.close()
            
            duplicates = []
            q_lower = question.lower().strip()
            
            for id, db_q, db_a, tags, category in records:
                # Сходство вопросов
                q_ratio = SequenceMatcher(None, q_lower, db_q.lower()).ratio()
                
                # Если есть ответ - учитываем его
                if answer:
                    a_lower = answer.lower().strip()
                    a_ratio = SequenceMatcher(None, a_lower, db_a.lower()).ratio()
                    similarity = (q_ratio * 0.7 + a_ratio * 0.3)  # Вопрос важнее
                else:
                    similarity = q_ratio
                
                if similarity >= threshold:
                    duplicates.append({
                        'id': id,
                        'question': db_q,
                        'answer': db_a,
                        'tags': tags,
                        'category': category,
                        'similarity': round(similarity * 100, 1)
                    })
            
            # Сортируем по схожести
            duplicates.sort(key=lambda x: x['similarity'], reverse=True)
            
            return duplicates
            
        except Exception as e:
            logger.error(f"Ошибка find_duplicates: {e}")
            return []
    
    def find(self, question: str, threshold: float = 0.6) -> str:
        """Ищет точный ответ"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT question, answer FROM knowledge WHERE is_current = 1')
            records = cursor.fetchall()
            conn.close()
            
            if not records:
                return None
            
            q_lower = question.lower().strip()
            best_answer = None
            best_ratio = 0
            
            for db_q, db_a in records:
                if db_q.lower() == q_lower:
                    return db_a
                
                ratio = SequenceMatcher(None, q_lower, db_q.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_answer = db_a
            
            return best_answer if best_ratio >= threshold else None
        except Exception as e:
            logger.error(f"Ошибка find: {e}")
            return None
    
    def smart_search(self, question: str, limit: int = 5) -> list:
        """Умный поиск с продвинутым ранжированием"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, question, answer, category, tags 
                FROM knowledge 
                WHERE is_current = 1
            ''')
            records = cursor.fetchall()
            conn.close()
            
            if not records:
                return []
            
            # Извлекаем ключевые слова
            q_lower = question.lower().strip()
            keywords = set(re.findall(r'\w+', q_lower))
            
            # Стоп-слова
            stop_words = {
                'что', 'как', 'где', 'когда', 'почему', 'какой', 'какая', 'какие', 'какое',
                'это', 'этот', 'эта', 'эти', 'тот', 'та', 'те',
                'the', 'is', 'are', 'was', 'were', 'a', 'an', 'в', 'на', 'с', 'у', 'о', 'и', 'или'
            }
            keywords = keywords - stop_words
            
            results = []
            
            for id, db_q, db_a, category, tags in records:
                score = 0
                
                # 1. Точное совпадение
                if db_q.lower() == q_lower:
                    score = 1000
                # 2. Один содержится в другом
                elif q_lower in db_q.lower():
                    score = 500
                elif db_q.lower() in q_lower:
                    score = 400
                else:
                    # 3. Ключевые слова в вопросе
                    db_q_words = set(re.findall(r'\w+', db_q.lower()))
                    q_matches = len(keywords & db_q_words)
                    score += q_matches * 50
                    
                    # 4. Ключевые слова в ответе (меньший вес)
                    db_a_words = set(re.findall(r'\w+', db_a.lower()))
                    a_matches = len(keywords & db_a_words)
                    score += a_matches * 20
                    
                    # 5. Ключевые слова в тегах (больший вес)
                    if tags:
                        tag_words = set(re.findall(r'\w+', tags.lower()))
                        t_matches = len(keywords & tag_words)
                        score += t_matches * 70
                    
                    # 6. Частичное совпадение строк
                    ratio = SequenceMatcher(None, q_lower, db_q.lower()).ratio()
                    score += ratio * 100
                
                if score > 30:  # Минимальный порог
                    results.append({
                        'id': id,
                        'question': db_q,
                        'answer': db_a,
                        'category': category,
                        'tags': tags,
                        'score': round(score, 1)
                    })
            
            # Сортируем по релевантности
            results.sort(key=lambda x: x['score'], reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка smart_search: {e}")
            return []
    
    def find_history(self, question: str) -> list:
        """История изменений вопроса"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT version, answer, created_at, is_current, added_by
                FROM knowledge 
                WHERE LOWER(question) = LOWER(?)
                ORDER BY version DESC
            ''', (question,))
            history = cursor.fetchall()
            conn.close()
            return history
        except Exception as e:
            logger.error(f"Ошибка find_history: {e}")
            return []
    
    def stats(self) -> dict:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Актуальные
            cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 1')
            total = cursor.fetchone()[0]
            
            # Legacy
            cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 0')
            legacy = cursor.fetchone()[0]
            
            # По категориям
            cursor.execute('SELECT category, COUNT(*) FROM knowledge WHERE is_current = 1 GROUP BY category')
            by_cat = dict(cursor.fetchall())
            
            # С тегами
            cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 1 AND tags != ""')
            with_tags = cursor.fetchone()[0]
            
            conn.close()
            return {
                'total': total,
                'legacy': legacy,
                'by_category': by_cat,
                'with_tags': with_tags
            }
        except:
            return {'total': 0, 'legacy': 0, 'by_category': {}, 'with_tags': 0}
    
    def delete(self, keyword: str) -> int:
        """Удаляет записи по ключевому слову"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM knowledge 
                WHERE question LIKE ? OR answer LIKE ?
            ''', (f'%{keyword}%', f'%{keyword}%'))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"Ошибка delete: {e}")
            return 0


class GPTClient:
    """OpenAI GPT клиент"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        openai.api_key = api_key
        self.model = model
        self.request_count = 0
        self.token_count = 0
    
    def set_model(self, model: str):
        """Смена модели"""
        self.model = model
        logger.info(f"Модель изменена на: {model}")
    
    async def ask(self, question: str, context: str = None) -> str:
        try:
            system_prompt = (
                "Ты ассистент клуба. Правила:\n"
                "1. ПРИОРИТЕТ: используй информацию из базы знаний если она есть в контексте\n"
                "2. Если в контексте есть похожий вопрос - адаптируй ответ из базы\n"
                "3. Отвечай кратко и по делу (2-3 предложения)\n"
                "4. Без лишних смайликов\n"
                "5. НЕ спрашивай уточнений если можешь ответить\n"
                "6. Говори на русском языке"
            )
            
            messages = [{"role": "system", "content": system_prompt}]
            
            if context:
                messages.append({
                    "role": "system", 
                    "content": f"БАЗА ЗНАНИЙ:\n{context}\n\nИспользуй эту информацию для ответа."
                })
            
            messages.append({"role": "user", "content": question})
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            
            # Подсчёт
            self.request_count += 1
            if hasattr(response, 'usage'):
                self.token_count += response.usage.total_tokens
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"GPT ошибка: {e}")
            return f"Извините, ошибка GPT: {str(e)}"
    
    async def check_quota(self) -> dict:
        """Проверка использования API"""
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            
            return {
                'model': self.model,
                'local_stats': {
                    'requests': self.request_count,
                    'tokens': self.token_count
                },
                'api_response': 'OK'
            }
        except openai.error.RateLimitError as e:
            return {'error': 'Rate limit exceeded', 'message': str(e)}
        except openai.error.AuthenticationError:
            return {'error': 'Authentication failed'}
        except Exception as e:
            return {'error': str(e)}
    
    def get_available_models(self) -> list:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]


class Bot:
    """Главный класс бота"""
    
    def __init__(self):
        self.config = self.load_config()
        self.kb = KnowledgeBase(DB_PATH)
        self.admin_mgr = AdminManager(DB_PATH)
        
        gpt_model = self.config.get('gpt_model', 'gpt-4o-mini')
        self.gpt = GPTClient(self.config['openai_api_key'], model=gpt_model)
        
        self.admin_ids = self.config['admin_ids']
        
        # Инициализируем главного админа
        if self.admin_ids:
            main_admin = self.admin_ids[0]
            self.admin_mgr.add_admin(
                user_id=main_admin,
                username="main_admin",
                full_name="Главный администратор",
                added_by=main_admin,
                can_teach=True,
                can_import=True,
                can_manage_admins=True
            )
    
    def load_config(self) -> dict:
        """Загрузка конфига"""
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("Конфиг загружен")
                return config
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            sys.exit(1)
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка прав администратора"""
        if user_id in self.admin_ids:
            return True
        admin = self.admin_mgr.get_admin(user_id)
        return admin is not None
    
    def can_teach(self, user_id: int) -> bool:
        """Может ли обучать бота"""
        if user_id in self.admin_ids:
            return True
        admin = self.admin_mgr.get_admin(user_id)
        return admin and admin['can_teach']
    
    def can_import(self, user_id: int) -> bool:
        """Может ли импортировать"""
        if user_id in self.admin_ids:
            return True
        admin = self.admin_mgr.get_admin(user_id)
        return admin and admin['can_import']
    
    def can_manage_admins(self, user_id: int) -> bool:
        """Может ли управлять админами"""
        return user_id in self.admin_ids
    
    # === КОМАНДЫ ===
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "👋 Привет! Я Club Assistant v3.0\n\n"
            "Задавай любые вопросы о клубе!\n\n"
            "Команды:\n"
            "/help - подробная справка"
        )
        
        if self.is_admin(update.effective_user.id):
            text += "\n/help - все команды админа"
        
        await update.message.reply_text(text)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подробная справка"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            text = (
                "📖 Справка Club Assistant\n\n"
                "Просто напиши любой вопрос о клубе!\n\n"
                "/help - эта справка\n"
                "/stats - статистика базы\n\n"
                "Примеры:\n"
                "• Где находится клуб?\n"
                "• Какие цены на игры?\n"
                "• Есть ли парковка?"
            )
            await update.message.reply_text(text)
            return
        
        # Для админов
        can_teach = self.can_teach(user_id)
        can_import = self.can_import(user_id)
        can_manage = self.can_manage_admins(user_id)
        
        text = "📖 Справка для администраторов\n\n"
        
        text += "🔷 Основные:\n"
        text += "/help - справка\n"
        text += "/stats - статистика\n"
        text += "/health - здоровье бота\n"
        text += "/quota - использование API\n\n"
        
        if can_teach:
            text += "🔷 Обучение (УМНОЕ):\n"
            text += "/learn текст\n"
            text += "  → авто-теги, категория, поиск дублей\n\n"
            text += "/search вопрос - тест поиска\n"
            text += "/history вопрос - история\n"
            text += "/forget слово - удалить\n\n"
        
        if can_import:
            text += "🔷 Импорт:\n"
            text += "/import - массовый импорт CSV/JSONL\n\n"
        
        text += "🔷 Личные данные:\n"
        text += "/savecreds сервис логин пароль\n"
        text += "/getcreds [сервис]\n\n"
        
        if can_manage:
            text += "🔷 Управление:\n"
            text += "/addadmin - добавить админа\n"
            text += "/listadmins - список\n"
            text += "/rmadmin ID - удалить\n\n"
            
            text += "🔷 GPT:\n"
            text += "/model - модели\n"
            text += "/resetstats - сброс счётчиков\n\n"
        
        text += "🔷 Обновление:\n"
        text += "/update - с GitHub\n\n"
        
        text += "💡 v3.0:\n"
        text += "• Авто-теги через GPT\n"
        text += "• Умный поиск дублей\n"
        text += "• Продвинутое ранжирование"
        
        await update.message.reply_text(text)
    
    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Умное обучение с авто-тегами"""
        if not self.can_teach(update.effective_user.id):
            await update.message.reply_text("Нет прав на обучение")
            return
        
        text = update.message.text.replace('/learn', '').strip()
        
        if not text:
            await update.message.reply_text(
                "Использование: /learn текст\n\n"
                "Бот автоматически:\n"
                "• Определит категорию\n"
                "• Создаст теги\n"
                "• Найдёт дубликаты\n\n"
                "Пример:\n"
                "/learn Клуб работает с 10:00 до 23:00 каждый день"
            )
            return
        
        # Парсим текст
        if '\n' in text or ' - ' in text or ': ' in text:
            # Пытаемся разделить на вопрос и ответ
            if '\n' in text:
                parts = text.split('\n', 1)
            elif ' - ' in text:
                parts = text.split(' - ', 1)
            elif ': ' in text:
                parts = text.split(': ', 1)
            else:
                parts = [text]
            
            if len(parts) == 2:
                question = parts[0].strip()
                answer = parts[1].strip()
            else:
                # Генерируем вопрос через GPT
                question_prompt = f"Сформулируй короткий вопрос (3-7 слов) для этой информации: {text}"
                question = await self.gpt.ask(question_prompt)
                question = question.strip('?"')
                answer = text
        else:
            # Короткий текст - генерируем вопрос
            question_prompt = f"Сформулируй короткий вопрос (3-7 слов) для этой информации: {text}"
            question = await self.gpt.ask(question_prompt)
            question = question.strip('?"')
            answer = text
        
        # Умное добавление
        msg = await update.message.reply_text("⏳ Анализирую...")
        
        result = await self.kb.smart_add(
            question=question,
            answer=answer,
            gpt_client=self.gpt,
            added_by=update.effective_user.id
        )
        
        if result['success']:
            response = f"✅ Добавлено!\n\n"
            response += f"❓ {question}\n"
            response += f"💬 {answer[:100]}...\n\n"
            response += f"📂 Категория: {result['category']}\n"
            
            if result['tags']:
                response += f"🏷 Теги: {result['tags']}\n"
            
            if result['duplicates_merged'] > 0:
                response += f"\n🔗 Объединено дубликатов: {result['duplicates_merged']}"
            
            await msg.edit_text(response)
        else:
            error = result.get('error', 'Неизвестная ошибка')
            await msg.edit_text(f"❌ Ошибка: {error}")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика базы"""
        stats = self.kb.stats()
        
        text = f"📊 Статистика базы знаний\n\n"
        text += f"Всего: {stats['total']}\n"
        text += f"Legacy: {stats['legacy']}\n"
        text += f"С тегами: {stats['with_tags']}\n\n"
        
        if stats['by_category']:
            text += "По категориям:\n"
            for cat, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                text += f"• {cat}: {count}\n"
        
        await update.message.reply_text(text)
    
    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестирование умного поиска"""
        if not self.is_admin(update.effective_user.id):
            return
        
        question = update.message.text.replace('/search', '').strip()
        
        if not question:
            await update.message.reply_text("Использование: /search вопрос")
            return
        
        results = self.kb.smart_search(question, limit=5)
        
        if not results:
            await update.message.reply_text("❌ Ничего не найдено")
            return
        
        text = f"🔍 Результаты: '{question}'\n\n"
        
        for i, r in enumerate(results, 1):
            text += f"{i}. [Score: {r['score']}]\n"
            text += f"❓ {r['question']}\n"
            text += f"💬 {r['answer']}\n"
            text += f"📂 {r['category']}"
            
            if r['tags']:
                text += f" | 🏷 {r['tags']}"
            
            text += "\n\n"
        
        # Разбиваем на части если длинно
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(text)
    
    async def cmd_forget(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление по ключевому слову"""
        if not self.can_teach(update.effective_user.id):
            return
        
        keyword = update.message.text.replace('/forget', '').strip()
        
        if not keyword:
            await update.message.reply_text("Использование: /forget ключевое_слово")
            return
        
        deleted = self.kb.delete(keyword)
        
        if deleted > 0:
            await update.message.reply_text(f"✅ Удалено записей: {deleted}")
        else:
            await update.message.reply_text("❌ Ничего не найдено")
    
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """История изменений"""
        if not self.is_admin(update.effective_user.id):
            return
        
        question = update.message.text.replace('/history', '').strip()
        
        if not question:
            await update.message.reply_text("Использование: /history вопрос")
            return
        
        history = self.kb.find_history(question)
        
        if not history:
            await update.message.reply_text("❌ История не найдена")
            return
        
        text = f"📜 История: '{question}'\n\n"
        
        for ver, ans, created, is_cur, added_by in history:
            status = "🟢 актуальная" if is_cur else "⚫ legacy"
            text += f"v{ver} {status}\n"
            text += f"{ans[:100]}...\n"
            text += f"📅 {created}\n\n"
        
        await update.message.reply_text(text)
    
    async def cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка здоровья"""
        if not self.is_admin(update.effective_user.id):
            return
        
        text = "🏥 Проверка здоровья\n\n"
        
        # База данных
        try:
            stats = self.kb.stats()
            text += f"✅ База данных: {stats['total']} записей\n"
        except:
            text += "❌ База данных: ошибка\n"
        
        # GPT API
        try:
            quota = await self.gpt.check_quota()
            if 'error' not in quota:
                text += f"✅ GPT API: OK ({self.gpt.model})\n"
            else:
                text += f"❌ GPT API: {quota['error']}\n"
        except:
            text += "❌ GPT API: ошибка\n"
        
        # Статистика
        text += f"\n📊 Использование:\n"
        text += f"Запросов: {self.gpt.request_count}\n"
        text += f"Токенов: {self.gpt.token_count}"
        
        await update.message.reply_text(text)
    
    async def cmd_quota(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Квоты API"""
        if not self.is_admin(update.effective_user.id):
            return
        
        quota_info = await self.gpt.check_quota()
        
        if 'error' not in quota_info:
            stats = quota_info['local_stats']
            text = f"📊 Использование API\n\n"
            text += f"Модель: {quota_info['model']}\n\n"
            text += f"Запросов: {stats['requests']}\n"
            text += f"Токенов: {stats['tokens']}\n\n"
            text += f"Статус: {quota_info['api_response']}\n\n"
            text += "Полная статистика:\nplatform.openai.com/usage"
        else:
            text = f"❌ Ошибка: {quota_info['error']}"
            if 'message' in quota_info:
                text += f"\n{quota_info['message']}"
        
        await update.message.reply_text(text)
    
    async def cmd_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Управление моделью GPT"""
        if not self.can_manage_admins(update.effective_user.id):
            return
        
        args = update.message.text.split()
        
        if len(args) == 1:
            # Показываем текущую
            models = self.gpt.get_available_models()
            text = f"Текущая: {self.gpt.model}\n\nДоступные:\n"
            for m in models:
                mark = "→" if m == self.gpt.model else "  "
                text += f"{mark} {m}\n"
            text += "\nСменить: /model название"
            await update.message.reply_text(text)
        else:
            # Меняем
            new_model = args[1]
            if new_model in self.gpt.get_available_models():
                old = self.gpt.model
                self.gpt.set_model(new_model)
                
                # Сохраняем
                self.config['gpt_model'] = new_model
                with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
                
                await update.message.reply_text(f"✅ {old} → {new_model}")
            else:
                await update.message.reply_text("❌ Неизвестная модель")
    
    async def cmd_resetstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сброс счётчиков"""
        if not self.can_manage_admins(update.effective_user.id):
            return
        
        old_r = self.gpt.request_count
        old_t = self.gpt.token_count
        
        self.gpt.request_count = 0
        self.gpt.token_count = 0
        
        await update.message.reply_text(
            f"✅ Сброшено\n\n"
            f"Было: {old_r} запросов, {old_t} токенов"
        )
    
    async def cmd_import(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Режим импорта"""
        if not self.can_import(update.effective_user.id):
            await update.message.reply_text("Нет прав на импорт")
            return
        
        await update.message.reply_text(
            "📥 Режим импорта\n\n"
            "Отправьте файл:\n"
            "• CSV (question,answer,category)\n"
            "• JSONL (по строке JSON)\n\n"
            "Файл будет обработан автоматически"
        )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка файлов для импорта"""
        if not self.can_import(update.effective_user.id):
            return
        
        document = update.message.document
        file_name = document.file_name
        
        if not (file_name.endswith('.csv') or file_name.endswith('.jsonl')):
            await update.message.reply_text("❌ Поддерживаются только CSV и JSONL")
            return
        
        # Скачиваем файл
        msg = await update.message.reply_text("⏳ Загружаю файл...")
        
        try:
            file = await context.bot.get_file(document.file_id)
            file_path = f"/tmp/{file_name}"
            await file.download_to_drive(file_path)
            
            await msg.edit_text("⏳ Обрабатываю...")
            
            # Импорт
            imported = 0
            errors = 0
            
            if file_name.endswith('.csv'):
                import csv
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    
                    for row in reader:
                        question = row.get('question', '').strip()
                        answer = row.get('answer', '').strip()
                        category = row.get('category', 'general').strip()
                        
                        if question and answer:
                            # Умное добавление
                            result = await self.kb.smart_add(
                                question=question,
                                answer=answer,
                                gpt_client=self.gpt,
                                added_by=update.effective_user.id
                            )
                            
                            if result['success']:
                                imported += 1
                            else:
                                errors += 1
            
            elif file_name.endswith('.jsonl'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            question = data.get('question', '').strip()
                            answer = data.get('answer', '').strip()
                            
                            if question and answer:
                                result = await self.kb.smart_add(
                                    question=question,
                                    answer=answer,
                                    gpt_client=self.gpt,
                                    added_by=update.effective_user.id
                                )
                                
                                if result['success']:
                                    imported += 1
                                else:
                                    errors += 1
                        except:
                            errors += 1
            
            # Удаляем временный файл
            import os
            os.remove(file_path)
            
            # Результат
            text = f"✅ Импорт завершён!\n\n"
            text += f"Добавлено: {imported}\n"
            if errors > 0:
                text += f"Ошибок: {errors}"
            
            await msg.edit_text(text)
            
        except Exception as e:
            logger.error(f"Ошибка импорта: {e}")
            await msg.edit_text(f"❌ Ошибка импорта: {e}")
    
    async def cmd_addadmin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление админа через кнопки"""
        if not self.can_manage_admins(update.effective_user.id):
            await update.message.reply_text("Только для главного администратора")
            return
        
        # Проверяем аргументы
        args = update.message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await update.message.reply_text(
                "Использование:\n\n"
                "1️⃣ По username:\n"
                "/addadmin @username\n\n"
                "2️⃣ По ID:\n"
                "/addadmin 123456789\n\n"
                "После этого выберешь права через кнопки"
            )
            return
        
        # Парсим username или ID
        user_input = args[1].strip()
        
        if user_input.startswith('@'):
            username = user_input[1:]
            user_id = None
        else:
            try:
                user_id = int(user_input)
                username = f"user_{user_id}"
            except:
                await update.message.reply_text("❌ Неверный формат. Используй @username или ID")
                return
        
        # Сохраняем в ожидание
        if user_id:
            context.user_data['pending_admin'] = {
                'user_id': user_id,
                'username': username,
                'full_name': username
            }
        else:
            # Для username сохраняем временно
            context.user_data['pending_admin'] = {
                'username': username,
                'full_name': username
            }
        
        # Показываем кнопки выбора прав
        keyboard = [
            [
                InlineKeyboardButton("✅ Обучение", callback_data="admin_perm_teach_yes"),
                InlineKeyboardButton("❌ Обучение", callback_data="admin_perm_teach_no")
            ],
            [
                InlineKeyboardButton("✅ Импорт", callback_data="admin_perm_import_yes"),
                InlineKeyboardButton("❌ Импорт", callback_data="admin_perm_import_no")
            ],
            [
                InlineKeyboardButton("✅ Управление админами", callback_data="admin_perm_manage_yes"),
                InlineKeyboardButton("❌ Управление админами", callback_data="admin_perm_manage_no")
            ],
            [
                InlineKeyboardButton("✅ Сохранить", callback_data="admin_save"),
                InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"👤 Добавление админа\n\n"
        if user_id:
            text += f"ID: {user_id}\n"
        text += f"Username: @{username}\n\n"
        text += "Выбери права:"
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопок добавления админа"""
        query = update.callback_query
        await query.answer()
        
        if 'pending_admin' not in context.user_data:
            await query.edit_message_text("❌ Сессия истекла. Начни заново с /addadmin")
            return
        
        data = query.data
        pending = context.user_data['pending_admin']
        
        # Инициализируем права если их нет
        if 'permissions' not in pending:
            pending['permissions'] = {
                'teach': True,
                'import': False,
                'manage': False
            }
        
        # Обрабатываем выбор
        if data.startswith('admin_perm_'):
            parts = data.split('_')
            perm_type = parts[2]  # teach, import, manage
            value = parts[3] == 'yes'  # yes/no
            
            pending['permissions'][perm_type] = value
            
            # Обновляем сообщение
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Обучение" if pending['permissions']['teach'] else "❌ Обучение",
                        callback_data="admin_perm_teach_yes" if not pending['permissions']['teach'] else "admin_perm_teach_no"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✅ Импорт" if pending['permissions']['import'] else "❌ Импорт",
                        callback_data="admin_perm_import_yes" if not pending['permissions']['import'] else "admin_perm_import_no"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✅ Управление админами" if pending['permissions']['manage'] else "❌ Управление админами",
                        callback_data="admin_perm_manage_yes" if not pending['permissions']['manage'] else "admin_perm_manage_no"
                    )
                ],
                [
                    InlineKeyboardButton("💾 Сохранить", callback_data="admin_save"),
                    InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            text = f"👤 Добавление админа\n\n"
            if pending.get('user_id'):
                text += f"ID: {pending['user_id']}\n"
            text += f"Username: @{pending['username']}\n\n"
            text += "Права:\n"
            text += f"{'✅' if pending['permissions']['teach'] else '❌'} Обучение\n"
            text += f"{'✅' if pending['permissions']['import'] else '❌'} Импорт\n"
            text += f"{'✅' if pending['permissions']['manage'] else '❌'} Управление админами"
            
            await query.edit_message_text(text, reply_markup=reply_markup)
        
        elif data == 'admin_save':
            # Сохраняем админа
            perms = pending['permissions']
            
            # Если user_id есть - сохраняем сразу
            if pending.get('user_id'):
                success = self.admin_mgr.add_admin(
                    user_id=pending['user_id'],
                    username=pending['username'],
                    full_name=pending['full_name'],
                    added_by=update.effective_user.id,
                    can_teach=perms['teach'],
                    can_import=perms['import'],
                    can_manage_admins=perms['manage']
                )
                
                if success:
                    text = f"✅ Админ добавлен!\n\n"
                    text += f"ID: {pending['user_id']}\n"
                    text += f"Username: @{pending['username']}\n\n"
                    text += f"Права:\n"
                    text += f"{'✅' if perms['teach'] else '❌'} Обучение\n"
                    text += f"{'✅' if perms['import'] else '❌'} Импорт\n"
                    text += f"{'✅' if perms['manage'] else '❌'} Управление"
                    
                    await query.edit_message_text(text)
                else:
                    await query.edit_message_text("❌ Ошибка сохранения")
                
                # Очищаем
                del context.user_data['pending_admin']
            else:
                # Для username - сохраняем в ожидание подтверждения
                self.admin_mgr.pending_admins[pending['username']] = {
                    'added_by': update.effective_user.id,
                    'permissions': perms
                }
                
                text = f"✅ Настройки сохранены!\n\n"
                text += f"Теперь пользователь @{pending['username']}\n"
                text += f"должен написать боту команду:\n"
                text += f"/confirmadmin\n\n"
                text += f"После этого он станет админом"
                
                await query.edit_message_text(text)
                del context.user_data['pending_admin']
        
        elif data == 'admin_cancel':
            await query.edit_message_text("❌ Отменено")
            if 'pending_admin' in context.user_data:
                del context.user_data['pending_admin']
    
    async def cmd_confirmadmin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение админа"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        if not username:
            await update.message.reply_text(
                "❌ У тебя нет username в Telegram.\n"
                "Установи его в настройках и попробуй снова."
            )
            return
        
        # Проверяем есть ли в ожидании
        if username not in self.admin_mgr.pending_admins:
            await update.message.reply_text(
                "❌ Тебя не добавляли в админы.\n"
                "Попроси главного админа добавить тебя через /addadmin"
            )
            return
        
        # Получаем права
        pending = self.admin_mgr.pending_admins[username]
        perms = pending['permissions']
        
        # Добавляем
        success = self.admin_mgr.add_admin(
            user_id=user_id,
            username=username,
            full_name=update.effective_user.full_name or username,
            added_by=pending['added_by'],
            can_teach=perms['teach'],
            can_import=perms['import'],
            can_manage_admins=perms['manage']
        )
        
        if success:
            text = f"✅ Ты стал администратором!\n\n"
            text += f"Твои права:\n"
            text += f"{'✅' if perms['teach'] else '❌'} Обучение бота\n"
            text += f"{'✅' if perms['import'] else '❌'} Импорт данных\n"
            text += f"{'✅' if perms['manage'] else '❌'} Управление админами\n\n"
            text += f"Используй /help для справки"
            
            await update.message.reply_text(text)
            
            # Удаляем из ожидания
            del self.admin_mgr.pending_admins[username]
            
            # Уведомляем главного админа
            try:
                await context.bot.send_message(
                    pending['added_by'],
                    f"✅ Пользователь @{username} (ID: {user_id}) подтвердил права администратора"
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Ошибка добавления")
        """Список админов"""
        if not self.is_admin(update.effective_user.id):
            return
        
        admins = self.admin_mgr.list_admins()
        
        if not admins:
            await update.message.reply_text("Нет администраторов")
            return
        
        text = "👥 Администраторы:\n\n"
        
        for uid, uname, fname, teach, imp, manage in admins:
            text += f"• @{uname} ({fname})\n"
            text += f"  ID: {uid}\n"
            
            rights = []
            if teach: rights.append("обучение")
            if imp: rights.append("импорт")
            if manage: rights.append("управление")
            
            text += f"  Права: {', '.join(rights)}\n\n"
        
        await update.message.reply_text(text)
    
    async def cmd_listadmins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список админов с кнопками управления"""
        if not self.is_admin(update.effective_user.id):
            return
        
        admins = self.admin_mgr.list_admins()
        
        if not admins:
            await update.message.reply_text("Нет администраторов")
            return
        
        can_manage = self.can_manage_admins(update.effective_user.id)
        
        text = "👥 Администраторы:\n\n"
        
        keyboard = []
        
        for uid, uname, fname, teach, imp, manage in admins:
            text += f"• @{uname} ({fname})\n"
            text += f"  ID: {uid}\n"
            
            rights = []
            if teach: rights.append("обучение")
            if imp: rights.append("импорт")
            if manage: rights.append("управление")
            
            text += f"  Права: {', '.join(rights)}\n\n"
            
            # Кнопка удаления (только для главного админа)
            if can_manage and uid not in self.admin_ids:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🗑 Удалить {uname}",
                        callback_data=f"rmadmin_{uid}"
                    )
                ])
        
        if keyboard and can_manage:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text)
    
    async def handle_rmadmin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка удаления админа через кнопку"""
        query = update.callback_query
        await query.answer()
        
        if not self.can_manage_admins(update.effective_user.id):
            await query.edit_message_text("❌ Нет прав")
            return
        
        # Получаем ID
        user_id = int(query.data.split('_')[1])
        
        if user_id in self.admin_ids:
            await query.answer("❌ Нельзя удалить главного админа", show_alert=True)
            return
        
        # Подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"rmadmin_confirm_{user_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data="rmadmin_cancel")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⚠️ Удалить админа ID: {user_id}?\n\n"
            f"Это действие нельзя отменить.",
            reply_markup=reply_markup
        )
    
    async def handle_rmadmin_confirm_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение удаления админа"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "rmadmin_cancel":
            await query.edit_message_text("❌ Отменено")
            return
        
        # Получаем ID
        user_id = int(query.data.split('_')[2])
        
        if self.admin_mgr.remove_admin(user_id):
            await query.edit_message_text(f"✅ Админ {user_id} удалён")
        else:
            await query.edit_message_text("❌ Ошибка удаления")
        """Удаление админа"""
        if not self.can_manage_admins(update.effective_user.id):
            return
        
        args = update.message.text.split()
        
        if len(args) < 2:
            await update.message.reply_text("Использование: /rmadmin ID")
            return
        
        try:
            user_id = int(args[1])
            
            if user_id in self.admin_ids:
                await update.message.reply_text("❌ Нельзя удалить главного админа")
                return
            
            if self.admin_mgr.remove_admin(user_id):
                await update.message.reply_text(f"✅ Админ {user_id} удалён")
            else:
                await update.message.reply_text("❌ Ошибка")
        except:
            await update.message.reply_text("❌ Неверный ID")
    
    async def cmd_savecreds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранение данных"""
        if not self.is_admin(update.effective_user.id):
            return
        
        parts = update.message.text.split(maxsplit=4)
        
        if len(parts) < 4:
            await update.message.reply_text(
                "Использование: /savecreds сервис логин пароль [заметки]"
            )
            return
        
        service = parts[1]
        login = parts[2]
        password = parts[3]
        notes = parts[4] if len(parts) > 4 else ''
        
        if self.admin_mgr.save_credentials(
            update.effective_user.id, service, login, password, notes
        ):
            # Удаляем сообщение с паролем
            await update.message.delete()
            await context.bot.send_message(
                update.effective_chat.id,
                f"✅ Данные для '{service}' сохранены"
            )
        else:
            await update.message.reply_text("❌ Ошибка")
    
    async def cmd_getcreds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение данных"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = update.message.text.split()
        service = args[1] if len(args) > 1 else None
        
        creds = self.admin_mgr.get_credentials(update.effective_user.id, service)
        
        if not creds:
            await update.message.reply_text("❌ Данных нет")
            return
        
        text = "🔐 Ваши данные:\n\n"
        
        for srv, login, pwd, notes, created in creds:
            text += f"• {srv}\n"
            text += f"  Логин: {login}\n"
            text += f"  Пароль: {pwd}\n"
            if notes:
                text += f"  Заметки: {notes}\n"
            text += "\n"
        
        # Отправляем приватно
        await context.bot.send_message(update.effective_user.id, text)
        
        if update.effective_chat.type != 'private':
            await update.message.reply_text("✅ Отправил в ЛС")
    
    async def cmd_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновление с GitHub"""
        if not self.can_manage_admins(update.effective_user.id):
            return
        
        await update.message.reply_text("🔄 Обновляюсь...")
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                capture_output=True,
                text=True,
                cwd='/opt/club_assistant'
            )
            
            if result.returncode == 0:
                await update.message.reply_text(
                    f"✅ Обновлено!\n\n{result.stdout}\n\nПерезапускаюсь..."
                )
                
                # Перезапуск
                subprocess.run(['systemctl', 'restart', 'club_assistant'])
            else:
                await update.message.reply_text(f"❌ Ошибка:\n{result.stderr}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    # === ОБРАБОТЧИКИ ===
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений"""
        question = update.message.text.strip()
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        
        # В группах - только по упоминанию
        if chat_type in ['group', 'supergroup']:
            bot_username = context.bot.username
            
            is_reply = (
                update.message.reply_to_message and 
                update.message.reply_to_message.from_user.id == context.bot.id
            )
            
            is_mention = f"@{bot_username}" in question
            
            if not (is_reply or is_mention):
                return
            
            question = question.replace(f"@{bot_username}", "").strip()
        
        # 1. Точный поиск
        exact_answer = self.kb.find(question)
        
        if exact_answer:
            logger.info("Найдено точное совпадение")
            await update.message.reply_text(exact_answer)
            return
        
        # 2. Умный поиск
        smart_results = self.kb.smart_search(question, limit=3)
        
        if smart_results and smart_results[0]['score'] >= 200:
            # Высокая релевантность - отвечаем сразу
            best = smart_results[0]
            logger.info(f"Умный поиск: score {best['score']}")
            await update.message.reply_text(best['answer'])
            return
        
        # 3. GPT с контекстом
        context_text = None
        
        if smart_results:
            context_parts = []
            for r in smart_results:
                context_parts.append(f"Q: {r['question']}\nA: {r['answer']}")
            
            context_text = "Похожие из базы:\n\n" + "\n\n".join(context_parts)
            logger.info(f"Передаю {len(smart_results)} результатов в GPT")
        
        gpt_answer = await self.gpt.ask(question, context=context_text)
        
        # Сохраняем
        self.kb.add(question, gpt_answer, 'auto', added_by=user_id)
        
        await update.message.reply_text(gpt_answer)
    
    def run(self):
        """Запуск бота"""
        logger.info("Запуск Club Assistant Bot v3.0...")
        
        app = Application.builder().token(self.config['telegram_token']).build()
        
        # Команды
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("learn", self.cmd_learn))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("search", self.cmd_search))
        app.add_handler(CommandHandler("forget", self.cmd_forget))
        app.add_handler(CommandHandler("history", self.cmd_history))
        app.add_handler(CommandHandler("health", self.cmd_health))
        app.add_handler(CommandHandler("quota", self.cmd_quota))
        app.add_handler(CommandHandler("model", self.cmd_model))
        app.add_handler(CommandHandler("resetstats", self.cmd_resetstats))
        app.add_handler(CommandHandler("import", self.cmd_import))
        app.add_handler(CommandHandler("addadmin", self.cmd_addadmin))
        app.add_handler(CommandHandler("confirmadmin", self.cmd_confirmadmin))
        app.add_handler(CommandHandler("listadmins", self.cmd_listadmins))
        app.add_handler(CommandHandler("savecreds", self.cmd_savecreds))
        app.add_handler(CommandHandler("getcreds", self.cmd_getcreds))
        app.add_handler(CommandHandler("update", self.cmd_update))
        
        # Обработчики кнопок
        app.add_handler(CallbackQueryHandler(
            self.handle_admin_callback,
            pattern="^admin_(perm|save|cancel)"
        ))
        app.add_handler(CallbackQueryHandler(
            self.handle_rmadmin_callback,
            pattern="^rmadmin_\\d+$"
        ))
        app.add_handler(CallbackQueryHandler(
            self.handle_rmadmin_confirm_callback,
            pattern="^rmadmin_(confirm|cancel)"
        ))
        
        # Файлы (для импорта)
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
        # Текст
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("Бот готов к работе!")
        
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    try:
        bot = Bot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
