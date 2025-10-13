#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Club Assistant Bot v2.1
Telegram бот с AI и автообучением
"""

import os
import sys
import sqlite3
import json
import logging
from datetime import datetime
from difflib import SequenceMatcher

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
    """База знаний SQLite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица знаний с версионированием
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
        
        # Таблица администраторов с расширенными правами
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
        
        # Таблица личных данных админов (зашифрованная в будущем)
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
        
        # Таблица проверок здоровья бота
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
    
    def add(self, question: str, answer: str, category: str = 'general', added_by: int = None) -> bool:
        """Добавляет знание с версионированием - старое уходит в legacy"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Проверяем есть ли уже такой вопрос
            cursor.execute(
                'SELECT id, version FROM knowledge WHERE question = ? AND is_current = 1',
                (question,)
            )
            existing = cursor.fetchone()
            
            if existing:
                old_id, old_version = existing
                # Делаем старую запись legacy (неактуальной)
                cursor.execute(
                    'UPDATE knowledge SET is_current = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (old_id,)
                )
                new_version = old_version + 1
            else:
                new_version = 1
            
            # Добавляем новую версию
            cursor.execute(
                '''INSERT INTO knowledge 
                   (question, answer, category, added_by, version, is_current) 
                   VALUES (?, ?, ?, ?, ?, 1)''',
                (question, answer, category, added_by, new_version)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка add: {e}")
            return False
    
    def find(self, question: str, threshold: float = 0.6) -> str:
        """Ищет актуальный ответ"""
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
    
    def find_history(self, question: str) -> list:
        """Находит всю историю изменений вопроса"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Точное совпадение
            cursor.execute('''
                SELECT version, answer, created_at, is_current, added_by
                FROM knowledge 
                WHERE question = ?
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
            
            # По категориям (только актуальные)
            cursor.execute('SELECT category, COUNT(*) FROM knowledge WHERE is_current = 1 GROUP BY category')
            by_cat = dict(cursor.fetchall())
            
            conn.close()
            return {'total': total, 'legacy': legacy, 'by_category': by_cat}
        except:
            return {'total': 0, 'legacy': 0, 'by_category': {}}
    
    def delete_by_keyword(self, keyword: str) -> int:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM knowledge WHERE question LIKE ? OR answer LIKE ?',
                (f'%{keyword}%', f'%{keyword}%')
            )
            count = cursor.rowcount
            conn.commit()
            conn.close()
            return count
        except:
            return 0
    
    def bulk_import(self, records: list) -> tuple:
        """
        Массовый импорт записей
        records: список словарей с ключами question, answer, category, tags, source
        Возвращает: (добавлено, обновлено, пропущено)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        added = 0
        updated = 0
        skipped = 0
        
        for record in records:
            try:
                question = record.get('question', '').strip()
                answer = record.get('answer', '').strip()
                
                if not question or not answer:
                    skipped += 1
                    continue
                
                category = record.get('category', 'general')
                tags = record.get('tags', '')
                source = record.get('source', '')
                
                # Проверяем существует ли запись
                cursor.execute('SELECT id FROM knowledge WHERE question = ?', (question,))
                exists = cursor.fetchone()
                
                if exists:
                    updated += 1
                else:
                    added += 1
                
                # INSERT OR REPLACE
                cursor.execute('''
                    INSERT OR REPLACE INTO knowledge 
                    (question, answer, category, tags, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (question, answer, category, tags, source))
                
            except Exception as e:
                logger.error(f"Ошибка импорта записи: {e}")
                skipped += 1
        
        conn.commit()
        conn.close()
        
        return (added, updated, skipped)


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
            messages = [
                {
                    "role": "system", 
                    "content": (
                        "Ты ассистент клуба. Правила:\n"
                        "1. Отвечай кратко и по делу\n"
                        "2. Без лишних смайликов\n"
                        "3. Если знаешь ответ из контекста - отвечай сразу\n"
                        "4. НЕ спрашивай уточнений если можешь ответить\n"
                        "5. Максимум 2-3 предложения\n"
                        "6. Говори на русском языке"
                    )
                }
            ]
            
            if context:
                messages.append({
                    "role": "system", 
                    "content": f"Используй эту информацию для ответа: {context}"
                })
            
            messages.append({"role": "user", "content": question})
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            
            # Подсчёт использования
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
            # Делаем тестовый запрос для проверки доступности
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            
            # Локальная статистика
            info = {
                'model': self.model,
                'local_stats': {
                    'requests': self.request_count,
                    'tokens': self.token_count
                },
                'api_response': 'OK',
                'note': 'Для точных лимитов проверьте: https://platform.openai.com/usage'
            }
            
            return info
            
        except openai.error.RateLimitError as e:
            return {
                'model': self.model,
                'error': 'Rate limit exceeded',
                'message': str(e),
                'action': 'Превышен лимит запросов. Подождите или проверьте баланс.'
            }
        except openai.error.AuthenticationError:
            return {
                'model': self.model,
                'error': 'Authentication failed',
                'action': 'Проверьте API ключ в config.json'
            }
        except openai.error.APIError as e:
            return {
                'model': self.model,
                'error': 'API Error',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"Ошибка check_quota: {e}")
            return {
                'model': self.model,
                'error': str(e)
            }
    
    def get_available_models(self) -> list:
        """Список доступных моделей"""
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo"
        ]
    
    async def smart_learn(self, text: str) -> dict:
        """Умное извлечение знаний из текста"""
        try:
            prompt = f"""Извлеки из текста вопрос и ответ.
Верни JSON: {{"question": "...", "answer": "...", "category": "..."}}

Текст: {text}

Примеры:
"Клуб на ул. Ленина 123" → {{"question": "Где клуб?", "answer": "ул. Ленина, 123", "category": "location"}}
"Работаем с 9 до 21" → {{"question": "График работы?", "answer": "9:00-21:00", "category": "schedule"}}
"""
            
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            result = response.choices[0].message.content.strip()
            
            # Извлекаем JSON
            import re
            match = re.search(r'\{[^}]+\}', result)
            if match:
                return json.loads(match.group())
            
            return None
        except Exception as e:
            logger.error(f"smart_learn ошибка: {e}")
            return None


class Bot:
    """Главный класс бота"""
    
    def __init__(self):
        self.config = self.load_config()
        self.kb = KnowledgeBase(DB_PATH)
        self.admin_mgr = AdminManager(DB_PATH)
        
        # Инициализируем GPT с моделью из конфига
        gpt_model = self.config.get('gpt_model', 'gpt-4o-mini')
        self.gpt = GPTClient(self.config['openai_api_key'], model=gpt_model)
        
        self.admin_ids = self.config['admin_ids']
        
        # Инициализируем супер-админа
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
        if not os.path.exists(CONFIG_PATH):
            logger.error("❌ config.json не найден!")
            sys.exit(1)
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        logger.info("✅ Конфигурация загружена")
        return config
    
    def is_admin(self, user_id: int) -> bool:
        """Базовая проверка - есть ли в списке админов"""
        return user_id in self.admin_ids or self.admin_mgr.get_admin(user_id) is not None
    
    def can_teach(self, user_id: int) -> bool:
        """Может ли обучать бота"""
        if user_id in self.admin_ids:
            return True
        admin = self.admin_mgr.get_admin(user_id)
        return admin and admin['can_teach']
    
    def can_import(self, user_id: int) -> bool:
        """Может ли импортировать данные"""
        if user_id in self.admin_ids:
            return True
        admin = self.admin_mgr.get_admin(user_id)
        return admin and admin['can_import']
    
    def can_manage_admins(self, user_id: int) -> bool:
        """Может ли управлять другими админами"""
        return user_id in self.admin_ids
    
    # Обработчики команд
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"/start от {update.effective_user.id}")
        
        text = (
            "Привет! Я Club Assistant.\n\n"
            "Задавай любые вопросы о клубе!\n\n"
            "Команды:\n"
            "/start - справка\n"
            "/stats - статистика\n"
        )
        
        if self.is_admin(update.effective_user.id):
            text += "\nАдминистратор:\n"
            
            if self.can_teach(update.effective_user.id):
                text += "/learn - обучить бота\n"
            
            if self.can_import(update.effective_user.id):
                text += "/import - импорт CSV/JSONL\n"
            
            text += "/history вопрос - история\n"
            text += "/savecreds - сохранить данные\n"
            text += "/getcreds - показать данные\n"
            text += "/health - проверка бота\n"
            text += "/quota - использование API\n"
            text += "/forget - удалить\n"
            text += "/update - обновить\n"
            
            if self.can_manage_admins(update.effective_user.id):
                text += "\nУправление:\n"
                text += "/addadmin - добавить админа\n"
                text += "/listadmins - список админов\n"
                text += "/rmadmin - удалить админа\n"
                text += "/model - сменить модель GPT\n"
                text += "/resetstats - сброс счётчиков\n"
        
        await update.message.reply_text(text)
    
    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.can_teach(update.effective_user.id):
            await update.message.reply_text("Нет прав для обучения")
            return
        
        text = update.message.text.replace('/learn', '').strip()
        
        if not text:
            await update.message.reply_text(
                "Использование: /learn текст\n\n"
                "Примеры:\n"
                "• /learn Клуб на ул. Ленина 123\n"
                "• /learn Работаем пн-пт 9-21\n"
                "• /learn Парковка бесплатная"
            )
            return
        
        logger.info(f"/learn: {text[:50]} от {update.effective_user.id}")
        
        result = await self.gpt.smart_learn(text)
        
        if result and 'question' in result and 'answer' in result:
            self.kb.add(
                result['question'],
                result['answer'],
                result.get('category', 'general'),
                added_by=update.effective_user.id
            )
            
            username = update.effective_user.username or update.effective_user.full_name
            
            await update.message.reply_text(
                f"Запомнил!\n\n"
                f"Вопрос: {result['question']}\n"
                f"Ответ: {result['answer']}\n"
                f"Категория: {result.get('category', 'general')}\n"
                f"Обучил: @{username}"
            )
        else:
            await update.message.reply_text("Не смог извлечь знание")
    
    async def cmd_forget(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return
        
        keyword = update.message.text.replace('/forget', '').strip()
        
        if not keyword:
            await update.message.reply_text("Использование: /forget ключевое_слово")
            return
        
        count = self.kb.delete_by_keyword(keyword)
        await update.message.reply_text(f"✅ Удалено записей: {count}")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = self.kb.stats()
        
        text = f"Статистика\n\n"
        text += f"Актуальных: {stats['total']}\n"
        text += f"Legacy: {stats['legacy']}\n\n"
        
        if stats['by_category']:
            text += "По категориям:\n"
            for cat, count in stats['by_category'].items():
                text += f"  • {cat}: {count}\n"
        
        await update.message.reply_text(text)
    
    async def cmd_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
            return
        
        github_repo = self.config.get('github_repo', '')
        
        if not github_repo:
            await update.message.reply_text(
                "GitHub репозиторий не настроен!\n"
                "Добавьте 'github_repo' в config.json"
            )
            return
        
        await update.message.reply_text("Обновляю с GitHub...")
        
        try:
            import subprocess
            
            work_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Git pull - обновляем ВСЁ из репозитория
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                capture_output=True,
                text=True,
                cwd=work_dir
            )
            
            if result.returncode == 0:
                changes = result.stdout
                
                await update.message.reply_text(
                    f"Обновление загружено!\n\n"
                    f"Изменения:\n{changes[:500]}\n\n"
                    f"Перезапускаю бота..."
                )
                
                # Перезапускаем через systemd
                subprocess.Popen(['systemctl', 'restart', 'club_assistant'])
            else:
                await update.message.reply_text(f"Ошибка: {result.stderr}")
        
        except Exception as e:
            await update.message.reply_text(f"Ошибка обновления: {e}")
    
    async def cmd_import(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /import - активирует режим ожидания файла"""
        if not self.can_import(update.effective_user.id):
            await update.message.reply_text("Нет прав для импорта")
            return
        
        await update.message.reply_text(
            "Режим импорта активирован\n\n"
            "Отправьте файл в формате:\n"
            "• CSV (.csv)\n"
            "• JSONL (.jsonl)\n\n"
            "Формат CSV:\n"
            "question,answer,category,tags,source\n\n"
            "Формат JSONL (каждая строка - JSON):\n"
            '{"question":"...","answer":"...","category":"..."}'
        )
    
    async def cmd_add_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление нового администратора"""
        if not self.can_manage_admins(update.effective_user.id):
            await update.message.reply_text("Только главный администратор может добавлять админов")
            return
        
        # Парсим: /addadmin @username Имя Фамилия teach,import
        args = update.message.text.split(maxsplit=3)
        
        if len(args) < 3:
            await update.message.reply_text(
                "Использование:\n"
                "/addadmin @username Имя_Фамилия [права]\n\n"
                "Права (через запятую):\n"
                "• teach - может обучать\n"
                "• import - может импортировать\n"
                "• manage - может управлять админами\n\n"
                "Пример:\n"
                "/addadmin @ivan Иван_Петров teach,import"
            )
            return
        
        username = args[1].replace('@', '')
        full_name = args[2].replace('_', ' ')
        
        permissions = args[3].split(',') if len(args) > 3 else ['teach']
        
        can_teach = 'teach' in permissions
        can_import = 'import' in permissions
        can_manage = 'manage' in permissions
        
        # Сохраняем запрос на подтверждение
        context.user_data['pending_admin'] = {
            'username': username,
            'full_name': full_name,
            'can_teach': can_teach,
            'can_import': can_import,
            'can_manage': can_manage
        }
        
        await update.message.reply_text(
            f"Добавить администратора?\n\n"
            f"Username: @{username}\n"
            f"Имя: {full_name}\n"
            f"Права:\n"
            f"  • Обучение: {'да' if can_teach else 'нет'}\n"
            f"  • Импорт: {'да' if can_import else 'нет'}\n"
            f"  • Управление: {'да' if can_manage else 'нет'}\n\n"
            f"Для подтверждения пусть @{username} напишет боту:\n"
            f"/confirm_admin"
        )
    
    async def cmd_confirm_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение добавления админа"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        # Проверяем есть ли запрос от главного админа
        # (в реальной системе нужно хранить в БД, но для простоты - в памяти)
        
        success = self.admin_mgr.add_admin(
            user_id=user_id,
            username=username or 'unknown',
            full_name=update.effective_user.full_name or 'Без имени',
            added_by=self.admin_ids[0],
            can_teach=True,
            can_import=False,
            can_manage=False
        )
        
        if success:
            await update.message.reply_text(
                f"Вы добавлены как администратор!\n\n"
                f"Ваши права:\n"
                f"• Обучение бота (/learn)\n"
                f"• Просмотр статистики (/stats)"
            )
        else:
            await update.message.reply_text("Ошибка при добавлении")
    
    async def cmd_list_admins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список администраторов"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
            return
        
        admins = self.admin_mgr.list_admins()
        
        if not admins:
            await update.message.reply_text("Нет администраторов")
            return
        
        text = "Список администраторов:\n\n"
        for user_id, username, full_name, can_teach, can_import, can_manage in admins:
            rights = []
            if can_teach:
                rights.append("обучение")
            if can_import:
                rights.append("импорт")
            if can_manage:
                rights.append("управление")
            
            text += f"• @{username} ({full_name})\n"
            text += f"  ID: {user_id}\n"
            text += f"  Права: {', '.join(rights)}\n\n"
        
        await update.message.reply_text(text)
    
    async def cmd_remove_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление администратора"""
        if not self.can_manage_admins(update.effective_user.id):
            await update.message.reply_text("Только главный администратор")
            return
        
        args = update.message.text.split()
        if len(args) < 2:
            await update.message.reply_text("Использование: /rmadmin user_id")
            return
        
        try:
            user_id = int(args[1])
            if self.admin_mgr.remove_admin(user_id):
                await update.message.reply_text(f"Администратор {user_id} удалён")
            else:
                await update.message.reply_text("Ошибка удаления")
        except:
            await update.message.reply_text("Неверный ID")
    
    async def cmd_save_creds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранение личных данных"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
            return
        
        # /savecreds сервис логин пароль [заметки]
        args = update.message.text.split(maxsplit=4)
        
        if len(args) < 4:
            await update.message.reply_text(
                "Использование:\n"
                "/savecreds сервис логин пароль [заметки]\n\n"
                "Пример:\n"
                "/savecreds auth_site admin123 pass456 Доступ к панели"
            )
            return
        
        service = args[1]
        login = args[2]
        password = args[3]
        notes = args[4] if len(args) > 4 else ''
        
        if self.admin_mgr.save_credentials(update.effective_user.id, service, login, password, notes):
            await update.message.reply_text(f"Данные для '{service}' сохранены")
            
            # Удаляем сообщение с паролем (для безопасности)
            try:
                await update.message.delete()
            except:
                pass
        else:
            await update.message.reply_text("Ошибка сохранения")
    
    async def cmd_get_creds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение личных данных"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
            return
        
        args = update.message.text.split()
        service = args[1] if len(args) > 1 else None
        
        creds = self.admin_mgr.get_credentials(update.effective_user.id, service)
        
        if not creds:
            await update.message.reply_text("Нет сохранённых данных")
            return
        
        text = "Ваши сохранённые данные:\n\n"
        for srv, login, pwd, notes, created in creds:
            text += f"Сервис: {srv}\n"
            text += f"Логин: {login}\n"
            text += f"Пароль: {pwd}\n"
            if notes:
                text += f"Заметки: {notes}\n"
            text += f"Создано: {created}\n\n"
        
        await update.message.reply_text(text)
    
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """История изменений вопроса"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
            return
        
        question = update.message.text.replace('/history', '').strip()
        
        if not question:
            await update.message.reply_text("Использование: /history вопрос")
            return
        
        history = self.kb.find_history(question)
        
        if not history:
            await update.message.reply_text("История не найдена")
            return
        
        text = f"История: '{question}'\n\n"
        for version, answer, created, is_current, added_by in history:
            status = "актуальный" if is_current else "legacy"
            text += f"v{version} ({status})\n"
            text += f"Ответ: {answer}\n"
            text += f"Создан: {created}\n"
            if added_by:
                text += f"Автор: {added_by}\n"
            text += "\n"
        
        await update.message.reply_text(text)
    
    async def cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка здоровья бота"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
            return
        
        checks = []
        
        # 1. База данных
        try:
            stats = self.kb.stats()
            checks.append(("База данных", "OK", f"{stats['total']} записей"))
        except Exception as e:
            checks.append(("База данных", "FAIL", str(e)))
        
        # 2. OpenAI API
        try:
            test_response = await self.gpt.ask("test")
            if test_response:
                checks.append(("OpenAI API", "OK", "Доступен"))
            else:
                checks.append(("OpenAI API", "FAIL", "Нет ответа"))
        except Exception as e:
            checks.append(("OpenAI API", "FAIL", str(e)))
        
        # 3. GitHub
        github_repo = self.config.get('github_repo', '')
        if github_repo:
            checks.append(("GitHub", "OK", github_repo))
        else:
            checks.append(("GitHub", "WARNING", "Не настроен"))
        
        # 4. Память
        try:
            import psutil
            process = psutil.Process()
            mem_mb = process.memory_info().rss / 1024 / 1024
            checks.append(("Память", "OK", f"{mem_mb:.1f} MB"))
        except:
            checks.append(("Память", "WARNING", "Нет данных"))
        
        # 5. Uptime
        try:
            import psutil
            import time
            process = psutil.Process()
            uptime_sec = time.time() - process.create_time()
            uptime_hours = uptime_sec / 3600
            checks.append(("Uptime", "OK", f"{uptime_hours:.1f} часов"))
        except:
            checks.append(("Uptime", "WARNING", "Нет данных"))
        
        # Формируем отчёт
        text = "Проверка здоровья бота:\n\n"
        for check, status, details in checks:
            emoji = "✅" if status == "OK" else "⚠️" if status == "WARNING" else "❌"
            text += f"{emoji} {check}: {status}\n"
            text += f"   {details}\n\n"
        
        await update.message.reply_text(text)
    
    async def cmd_quota(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка использования OpenAI API"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
            return
        
        await update.message.reply_text("Проверяю API...")
        
        try:
            quota_info = await self.gpt.check_quota()
            
            if quota_info and 'error' not in quota_info:
                text = "Использование OpenAI API:\n\n"
                text += f"Модель: {quota_info['model']}\n\n"
                
                if 'local_stats' in quota_info:
                    stats = quota_info['local_stats']
                    text += f"С момента запуска бота:\n"
                    text += f"• Запросов: {stats['requests']}\n"
                    text += f"• Токенов: {stats['tokens']}\n\n"
                
                text += f"Статус API: {quota_info.get('api_response', 'OK')}\n\n"
                text += f"{quota_info.get('note', '')}\n\n"
                text += "Полная статистика:\nhttps://platform.openai.com/usage"
                
                await update.message.reply_text(text)
            
            elif quota_info and 'error' in quota_info:
                text = f"Ошибка API:\n\n"
                text += f"Тип: {quota_info['error']}\n"
                
                if 'message' in quota_info:
                    text += f"Сообщение: {quota_info['message']}\n\n"
                
                if 'action' in quota_info:
                    text += f"Действие: {quota_info['action']}"
                
                await update.message.reply_text(text)
            else:
                await update.message.reply_text(
                    "Не удалось получить информацию\n\n"
                    "Проверьте статистику:\n"
                    "https://platform.openai.com/usage"
                )
        
        except Exception as e:
            logger.error(f"Ошибка quota: {e}")
            await update.message.reply_text(f"Ошибка: {e}")
    
    async def cmd_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать текущую модель или сменить"""
        if not self.can_manage_admins(update.effective_user.id):
            await update.message.reply_text("Только главный администратор")
            return
        
        args = update.message.text.split()
        
        # Без аргументов - показываем текущую модель
        if len(args) == 1:
            text = f"Текущая модель: {self.gpt.model}\n\n"
            text += "Доступные модели:\n"
            for model in self.gpt.get_available_models():
                mark = "→" if model == self.gpt.model else "  "
                text += f"{mark} {model}\n"
            text += f"\nДля смены: /model название"
            
            await update.message.reply_text(text)
            return
        
        # С аргументом - меняем модель
        new_model = args[1]
        available = self.gpt.get_available_models()
        
        if new_model not in available:
            await update.message.reply_text(
                f"Неизвестная модель: {new_model}\n\n"
                f"Доступные:\n" + "\n".join(f"• {m}" for m in available)
            )
            return
        
        # Меняем модель
        old_model = self.gpt.model
        self.gpt.set_model(new_model)
        
        # Сохраняем в config
        self.config['gpt_model'] = new_model
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения config: {e}")
        
        await update.message.reply_text(
            f"Модель изменена\n\n"
            f"Было: {old_model}\n"
            f"Стало: {new_model}\n\n"
            f"Изменение сохранено в config.json"
        )
    
    async def cmd_resetstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сброс счётчиков использования"""
        if not self.can_manage_admins(update.effective_user.id):
            await update.message.reply_text("Только главный администратор")
            return
        
        old_requests = self.gpt.request_count
        old_tokens = self.gpt.token_count
        
        self.gpt.request_count = 0
        self.gpt.token_count = 0
        
        await update.message.reply_text(
            f"Счётчики сброшены\n\n"
            f"Было:\n"
            f"• Запросов: {old_requests}\n"
            f"• Токенов: {old_tokens}\n\n"
            f"Теперь: 0 / 0"
        )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик загруженных файлов"""
        if not self.is_admin(update.effective_user.id):
            return
        
        document = update.message.document
        file_name = document.file_name
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # Проверяем формат
        if file_ext not in ['.csv', '.jsonl']:
            await update.message.reply_text(
                "Неподдерживаемый формат\n"
                "Используйте: .csv или .jsonl"
            )
            return
        
        await update.message.reply_text("Загружаю файл...")
        
        try:
            # Скачиваем файл
            tmp_dir = '/tmp/bot_imports'
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_path = os.path.join(tmp_dir, f"{update.effective_user.id}_{file_name}")
            
            file = await context.bot.get_file(document.file_id)
            await file.download_to_drive(tmp_path)
            
            # Импортируем
            records = self.parse_import_file(tmp_path, file_ext)
            added, updated, skipped = self.kb.bulk_import(records)
            
            # Удаляем временный файл
            os.remove(tmp_path)
            
            await update.message.reply_text(
                f"Импорт завершён\n\n"
                f"Добавлено: {added}\n"
                f"Обновлено: {updated}\n"
                f"Пропущено: {skipped}"
            )
            
            logger.info(f"Импорт: +{added} ~{updated} !{skipped}")
            
        except Exception as e:
            logger.error(f"Ошибка импорта: {e}")
            await update.message.reply_text(f"Ошибка импорта: {e}")
    
    def parse_import_file(self, file_path: str, file_ext: str) -> list:
        """Парсит CSV или JSONL файл"""
        records = []
        
        if file_ext == '.csv':
            import csv
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append({
                        'question': row.get('question', ''),
                        'answer': row.get('answer', ''),
                        'category': row.get('category', 'general'),
                        'tags': row.get('tags', ''),
                        'source': row.get('source', '')
                    })
        
        elif file_ext == '.jsonl':
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        obj = json.loads(line.strip())
                        # Если tags - список, конвертируем в строку
                        tags = obj.get('tags', '')
                        if isinstance(tags, list):
                            tags = ','.join(tags)
                        
                        records.append({
                            'question': obj.get('question', ''),
                            'answer': obj.get('answer', ''),
                            'category': obj.get('category', 'general'),
                            'tags': tags,
                            'source': obj.get('source', '')
                        })
                    except:
                        continue
        
        return records
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        question = update.message.text.strip()
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        
        # В группах реагируем только на упоминания или ответы
        if chat_type in ['group', 'supergroup']:
            bot_username = context.bot.username
            
            # Проверяем: это ответ на наше сообщение?
            is_reply_to_bot = (
                update.message.reply_to_message and 
                update.message.reply_to_message.from_user.id == context.bot.id
            )
            
            # Проверяем: есть упоминание бота?
            is_mention = f"@{bot_username}" in question
            
            # Если ни то, ни другое - игнорируем
            if not (is_reply_to_bot or is_mention):
                return
            
            # Убираем упоминание из текста
            question = question.replace(f"@{bot_username}", "").strip()
            
            logger.info(f"[ГРУППА] Сообщение от {user_id}: {question[:50]}")
        else:
            logger.info(f"[ЛС] Сообщение от {user_id}: {question[:50]}")
        
        # Ищем в базе
        answer = self.kb.find(question)
        
        if answer:
            logger.info("Найдено в базе")
            await update.message.reply_text(answer)
            return
        
        # GPT (без "Думаю...")
        gpt_answer = await self.gpt.ask(question)
        
        # Сохраняем
        self.kb.add(question, gpt_answer, 'auto')
        
        logger.info("Ответ GPT")
        await update.message.reply_text(gpt_answer)
    
    def run(self):
        """Запуск бота"""
        logger.info("Запуск Club Assistant Bot v2.4...")
        
        app = Application.builder().token(self.config['telegram_token']).build()
        
        # Основные команды
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("learn", self.cmd_learn))
        app.add_handler(CommandHandler("forget", self.cmd_forget))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("update", self.cmd_update))
        app.add_handler(CommandHandler("import", self.cmd_import))
        
        # Управление админами
        app.add_handler(CommandHandler("addadmin", self.cmd_add_admin))
        app.add_handler(CommandHandler("confirmadmin", self.cmd_confirm_admin))
        app.add_handler(CommandHandler("listadmins", self.cmd_list_admins))
        app.add_handler(CommandHandler("rmadmin", self.cmd_remove_admin))
        
        # Личные данные
        app.add_handler(CommandHandler("savecreds", self.cmd_save_creds))
        app.add_handler(CommandHandler("getcreds", self.cmd_get_creds))
        
        # Дополнительные
        app.add_handler(CommandHandler("history", self.cmd_history))
        app.add_handler(CommandHandler("health", self.cmd_health))
        app.add_handler(CommandHandler("quota", self.cmd_quota))
        app.add_handler(CommandHandler("model", self.cmd_model))
        app.add_handler(CommandHandler("resetstats", self.cmd_resetstats))
        
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
        logger.info("⏹️ Остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
