#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Issue Manager - Система отслеживания проблем клуба
Запись проблем, уведомления, база знаний, управление
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class IssueManager:
    """Менеджер системы отслеживания проблем клуба"""
    
    def __init__(self, db_path: str = 'knowledge.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица проблем клуба
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS club_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_by INTEGER NOT NULL,
                created_by_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Issue Manager database initialized")
    
    def create_issue(self, club: str, description: str, 
                    created_by: int, created_by_name: str) -> int:
        """
        Создать новую проблему
        
        Args:
            club: 'rio' или 'michurinskaya'
            description: описание проблемы
            created_by: ID пользователя
            created_by_name: имя пользователя
            
        Returns:
            ID созданной проблемы или 0 при ошибке
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO club_issues (club, description, created_by, created_by_name)
                VALUES (?, ?, ?, ?)
            ''', (club, description, created_by, created_by_name))
            
            issue_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Issue created: #{issue_id} in {club} by {created_by_name}")
            return issue_id
            
        except Exception as e:
            logger.error(f"❌ Error creating issue: {e}")
            return 0
    
    def get_issue(self, issue_id: int) -> Optional[Dict]:
        """Получить проблему по ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM club_issues WHERE id = ?', (issue_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"❌ Error getting issue: {e}")
            return None
    
    def list_issues(self, club: str = None, status: str = 'active') -> List[Dict]:
        """
        Получить список проблем
        
        Args:
            club: фильтр по клубу (None = все клубы)
            status: фильтр по статусу ('active', 'resolved', None = все)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM club_issues WHERE 1=1'
            params = []
            
            if club:
                query += ' AND club = ?'
                params.append(club)
            
            if status:
                query += ' AND status = ?'
                params.append(status)
            
            query += ' ORDER BY created_at DESC'
            
            cursor.execute(query, params)
            
            issues = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return issues
            
        except Exception as e:
            logger.error(f"❌ Error listing issues: {e}")
            return []
    
    def update_issue(self, issue_id: int, description: str) -> bool:
        """Обновить описание проблемы"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE club_issues 
                SET description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (description, issue_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Issue #{issue_id} updated")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating issue: {e}")
            return False
    
    def resolve_issue(self, issue_id: int) -> bool:
        """Пометить проблему как решённую"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE club_issues 
                SET status = 'resolved', 
                    resolved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (issue_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Issue #{issue_id} resolved")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error resolving issue: {e}")
            return False
    
    def delete_issue(self, issue_id: int) -> bool:
        """Удалить проблему"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM club_issues WHERE id = ?', (issue_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Issue #{issue_id} deleted")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting issue: {e}")
            return False
    
    def get_active_count(self, club: str = None) -> int:
        """Получить количество активных проблем"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if club:
                cursor.execute('''
                    SELECT COUNT(*) FROM club_issues 
                    WHERE status = 'active' AND club = ?
                ''', (club,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) FROM club_issues 
                    WHERE status = 'active'
                ''')
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count
            
        except Exception as e:
            logger.error(f"❌ Error getting active count: {e}")
            return 0
    
    def format_issue(self, issue: Dict) -> str:
        """Форматирование одной проблемы"""
        club_names = {
            'rio': '🏢 Рио',
            'michurinskaya': '🏢 Мичуринская/Север'
        }
        
        status_emoji = {
            'active': '🔴',
            'resolved': '✅'
        }
        
        club = club_names.get(issue['club'], issue['club'])
        status = status_emoji.get(issue['status'], '❓')
        
        text = f"{status} Проблема #{issue['id']}\n"
        text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"{club}\n\n"
        text += f"📝 {issue['description']}\n\n"
        text += f"👤 Автор: {issue['created_by_name']}\n"
        text += f"📅 Создана: {issue['created_at'][:16]}\n"
        
        if issue['status'] == 'resolved' and issue.get('resolved_at'):
            text += f"✅ Решена: {issue['resolved_at'][:16]}\n"
        
        return text
    
    def format_issues_list(self, issues: List[Dict], title: str = "ПРОБЛЕМЫ") -> str:
        """Форматирование списка проблем"""
        if not issues:
            return "✅ Нет проблем"
        
        text = f"📋 {title}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        club_names = {
            'rio': 'Рио',
            'michurinskaya': 'Мичур.'
        }
        
        for issue in issues:
            status = "🔴" if issue['status'] == 'active' else "✅"
            club = club_names.get(issue['club'], issue['club'])
            
            text += f"{status} #{issue['id']} | {club}\n"
            
            # Обрезаем длинное описание
            description = issue['description']
            if len(description) > 100:
                description = description[:97] + "..."
            
            text += f"{description}\n"
            text += f"👤 {issue['created_by_name']} | {issue['created_at'][:10]}\n\n"
        
        return text
    
    def format_notification(self, issue_id: int) -> str:
        """Форматирование уведомления о новой проблеме"""
        issue = self.get_issue(issue_id)
        
        if not issue:
            return "❌ Проблема не найдена"
        
        club_names = {
            'rio': 'Рио',
            'michurinskaya': 'Мичуринская/Север'
        }
        
        text = f"🔴 НОВАЯ ПРОБЛЕМА В КЛУБЕ {club_names.get(issue['club'], issue['club']).upper()}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        text += f"📝 {issue['description']}\n\n"
        text += f"👤 Сообщил: {issue['created_by_name']}\n"
        text += f"📅 Время: {issue['created_at'][:16]}\n"
        text += f"🆔 Проблема #{issue['id']}"
        
        return text
    
    def search_similar(self, description: str, club: str = None) -> List[Dict]:
        """
        Простой поиск похожих проблем (по ключевым словам)
        Для более умного поиска используется векторная БД через KnowledgeBase
        """
        try:
            # Извлекаем ключевые слова из описания
            keywords = [word.lower() for word in description.split() 
                       if len(word) > 3]
            
            if not keywords:
                return []
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Ищем проблемы содержащие хотя бы одно ключевое слово
            query = 'SELECT * FROM club_issues WHERE '
            conditions = []
            params = []
            
            for keyword in keywords[:5]:  # Берём первые 5 ключевых слов
                conditions.append('LOWER(description) LIKE ?')
                params.append(f'%{keyword}%')
            
            query += '(' + ' OR '.join(conditions) + ')'
            
            if club:
                query += ' AND club = ?'
                params.append(club)
            
            query += ' ORDER BY created_at DESC LIMIT 10'
            
            cursor.execute(query, params)
            
            issues = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return issues
            
        except Exception as e:
            logger.error(f"❌ Error searching similar issues: {e}")
            return []
