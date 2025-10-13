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


class KnowledgeBase:
    """База знаний SQLite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '',
                source TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(question)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_question ON knowledge(question)')
        conn.commit()
        conn.close()
        logger.info("База данных готова")
    
    def add(self, question: str, answer: str, category: str = 'general') -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM knowledge WHERE question = ?', (question,))
            if cursor.fetchone():
                cursor.execute(
                    'UPDATE knowledge SET answer=?, category=?, updated_at=CURRENT_TIMESTAMP WHERE question=?',
                    (answer, category, question)
                )
            else:
                cursor.execute(
                    'INSERT INTO knowledge (question, answer, category) VALUES (?, ?, ?)',
                    (question, answer, category)
                )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка add: {e}")
            return False
    
    def find(self, question: str, threshold: float = 0.6) -> str:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT question, answer FROM knowledge')
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
    
    def stats(self) -> dict:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM knowledge')
            total = cursor.fetchone()[0]
            cursor.execute('SELECT category, COUNT(*) FROM knowledge GROUP BY category')
            by_cat = dict(cursor.fetchall())
            conn.close()
            return {'total': total, 'by_category': by_cat}
        except:
            return {'total': 0, 'by_category': {}}
    
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
    
    def __init__(self, api_key: str):
        openai.api_key = api_key
    
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
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"GPT ошибка: {e}")
            return f"Извините, ошибка GPT: {str(e)}"
    
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
        self.gpt = GPTClient(self.config['openai_api_key'])
        self.admin_ids = self.config['admin_ids']
    
    def load_config(self) -> dict:
        if not os.path.exists(CONFIG_PATH):
            logger.error("❌ config.json не найден!")
            sys.exit(1)
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        logger.info("✅ Конфигурация загружена")
        return config
    
    def is_admin(self, user_id: int) -> bool:
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
            text += (
                "\nАдмин:\n"
                "/learn текст - умное обучение\n"
                "/import - импорт из CSV/JSONL\n"
                "/forget слово - удалить\n"
                "/update - обновить бота\n"
            )
        
        await update.message.reply_text(text)
    
    async def cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
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
        
        logger.info(f"/learn: {text[:50]}")
        
        result = await self.gpt.smart_learn(text)
        
        if result and 'question' in result and 'answer' in result:
            self.kb.add(
                result['question'],
                result['answer'],
                result.get('category', 'general')
            )
            
            await update.message.reply_text(
                f"Запомнил!\n\n"
                f"Вопрос: {result['question']}\n"
                f"Ответ: {result['answer']}\n"
                f"Категория: {result.get('category', 'general')}"
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
        
        text = f"📊 Статистика\n\n📚 Всего: {stats['total']}\n\n"
        
        if stats['by_category']:
            text += "📁 По категориям:\n"
            for cat, count in stats['by_category'].items():
                text += f"  • {cat}: {count}\n"
        
        await update.message.reply_text(text)
    
    async def cmd_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return
        
        github_repo = self.config.get('github_repo', '')
        
        if not github_repo:
            await update.message.reply_text(
                "⚠️ GitHub репозиторий не настроен!\n"
                "Добавьте 'github_repo' в config.json"
            )
            return
        
        await update.message.reply_text("Обновляю с GitHub...")
        
        try:
            import subprocess
            
            # Git pull
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            if result.returncode == 0:
                auto_restart = self.config.get('auto_restart', False)
                
                if auto_restart:
                    await update.message.reply_text(
                        "✅ Обновление загружено!\n"
                        "Перезапускаю бота..."
                    )
                    
                    # Перезапуск через systemd
                    subprocess.run(['systemctl', 'restart', 'club_assistant'])
                else:
                    await update.message.reply_text(
                        "✅ Обновление загружено!\n\n"
                        "Перезапустите бота:\n"
                        "systemctl restart club_assistant"
                    )
            else:
                await update.message.reply_text(f"❌ Ошибка: {result.stderr}")
        
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка обновления: {e}")
    
    async def cmd_import(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /import - активирует режим ожидания файла"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Только для администраторов")
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
        logger.info("Запуск Club Assistant Bot v2.2...")
        
        app = Application.builder().token(self.config['telegram_token']).build()
        
        # Команды
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("learn", self.cmd_learn))
        app.add_handler(CommandHandler("forget", self.cmd_forget))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("update", self.cmd_update))
        app.add_handler(CommandHandler("import", self.cmd_import))
        
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
