#!/usr/bin/env python3
"""
Draft Queue - очередь кандидатов знаний на ревью
Контролируемое самообучение с кнопками одобрения
"""

import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DraftQueue:
    """Управление черновиками знаний"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация таблицы черновиков"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_draft_status ON knowledge_drafts(status)')
        
        conn.commit()
        conn.close()
        
        logger.info("Draft queue initialized")
    
    def add_draft(self, question: str, answer: str, 
                  category: str = 'general', tags: str = '',
                  source: str = 'auto', confidence: float = 0.5,
                  added_by: int = None) -> int:
        """Добавить черновик"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO knowledge_drafts 
                (question, answer, category, tags, source, confidence, added_by, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', (question, answer, category, tags, source, confidence, added_by))
            
            draft_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            logger.info(f"Draft added: id={draft_id}, confidence={confidence:.2f}")
            return draft_id
            
        except Exception as e:
            logger.error(f"Ошибка add_draft: {e}")
            return 0
    
    def get_pending(self, limit: int = 10) -> List[Dict]:
        """Получить черновики на ревью"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, question, answer, category, tags, source, confidence, added_by, created_at
                FROM knowledge_drafts
                WHERE status = 'pending'
                ORDER BY confidence ASC, created_at ASC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            drafts = []
            for row in rows:
                drafts.append({
                    'id': row[0],
                    'question': row[1],
                    'answer': row[2],
                    'category': row[3],
                    'tags': row[4],
                    'source': row[5],
                    'confidence': row[6],
                    'added_by': row[7],
                    'created_at': row[8]
                })
            
            return drafts
            
        except Exception as e:
            logger.error(f"Ошибка get_pending: {e}")
            return []
    
    def get_draft(self, draft_id: int) -> Optional[Dict]:
        """Получить конкретный черновик"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, question, answer, category, tags, source, confidence, 
                       added_by, status, created_at
                FROM knowledge_drafts
                WHERE id = ?
            ''', (draft_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'question': row[1],
                    'answer': row[2],
                    'category': row[3],
                    'tags': row[4],
                    'source': row[5],
                    'confidence': row[6],
                    'added_by': row[7],
                    'status': row[8],
                    'created_at': row[9]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка get_draft: {e}")
            return None
    
    def approve(self, draft_id: int, reviewed_by: int) -> bool:
        """Одобрить черновик"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE knowledge_drafts
                SET status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (reviewed_by, draft_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Draft approved: id={draft_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка approve: {e}")
            return False
    
    def reject(self, draft_id: int, reviewed_by: int) -> bool:
        """Отклонить черновик"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE knowledge_drafts
                SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (reviewed_by, draft_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Draft rejected: id={draft_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка reject: {e}")
            return False
    
    def update_draft(self, draft_id: int, question: str = None, 
                    answer: str = None, category: str = None,
                    tags: str = None) -> bool:
        """Обновить черновик перед одобрением"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updates = []
            values = []
            
            if question is not None:
                updates.append("question = ?")
                values.append(question)
            
            if answer is not None:
                updates.append("answer = ?")
                values.append(answer)
            
            if category is not None:
                updates.append("category = ?")
                values.append(category)
            
            if tags is not None:
                updates.append("tags = ?")
                values.append(tags)
            
            if not updates:
                return False
            
            values.append(draft_id)
            
            sql = f"UPDATE knowledge_drafts SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, values)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Draft updated: id={draft_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка update_draft: {e}")
            return False
    
    def stats(self) -> Dict:
        """Статистика очереди"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Всего по статусам
            cursor.execute('''
                SELECT status, COUNT(*) 
                FROM knowledge_drafts 
                GROUP BY status
            ''')
            by_status = dict(cursor.fetchall())
            
            # Средняя confidence ожидающих
            cursor.execute('''
                SELECT AVG(confidence)
                FROM knowledge_drafts
                WHERE status = 'pending'
            ''')
            avg_conf = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'pending': by_status.get('pending', 0),
                'approved': by_status.get('approved', 0),
                'rejected': by_status.get('rejected', 0),
                'avg_confidence': round(avg_conf, 3)
            }
            
        except Exception as e:
            logger.error(f"Ошибка stats: {e}")
            return {}
    
    def cleanup_old(self, days: int = 30) -> int:
        """Удалить старые отклонённые черновики"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM knowledge_drafts
                WHERE status = 'rejected' 
                AND reviewed_at < datetime('now', '-' || ? || ' days')
            ''', (days,))
            
            deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted} old drafts")
            return deleted
            
        except Exception as e:
            logger.error(f"Ошибка cleanup: {e}")
            return 0


# Тестирование
if __name__ == '__main__':
    queue = DraftQueue('knowledge.db')
    
    # Добавляем тестовый черновик
    draft_id = queue.add_draft(
        question="Тестовый вопрос?",
        answer="Тестовый ответ",
        category="test",
        tags="test,draft",
        confidence=0.7,
        added_by=123
    )
    
    print(f"Добавлен draft_id: {draft_id}")
    
    # Получаем ожидающие
    pending = queue.get_pending()
    print(f"\nОжидают ревью: {len(pending)}")
    for d in pending:
        print(f"  #{d['id']}: {d['question'][:50]} (conf: {d['confidence']:.2f})")
    
    # Статистика
    stats = queue.stats()
    print(f"\nСтатистика: {stats}")
