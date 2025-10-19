#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Content Generation Manager
Handles AI content generation (text, images, video)
"""

import logging
import sqlite3
from datetime import datetime
from typing import Optional, Dict
import openai

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Manages AI content generation"""
    
    def __init__(self, db_path: str, openai_api_key: str, gpt_model: str = 'gpt-4o-mini'):
        self.db_path = db_path
        self.gpt_model = gpt_model
        openai.api_key = openai_api_key
        self._init_tables()
    
    def _init_tables(self):
        """Initialize database tables for content generation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS content_generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                request_text TEXT NOT NULL,
                content_type TEXT NOT NULL,
                generated_content TEXT,
                image_url TEXT,
                video_url TEXT,
                model_used TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS gpt_settings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                active_model TEXT DEFAULT 'gpt-4o-mini',
                updated_by INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Initialize default GPT model if not exists
            cursor.execute('INSERT OR IGNORE INTO gpt_settings (id, active_model) VALUES (1, ?)', 
                         (self.gpt_model,))
            
            conn.commit()
            conn.close()
            logger.info("✅ Content generation tables initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing content generation tables: {e}")
    

    
    def generate_text(self, prompt: str, user_id: int) -> Dict:
        """Generate text content using GPT"""
        try:
            # Get current active model
            active_model = self.get_active_model()
            
            generation_id = self._log_generation(user_id, prompt, 'text', active_model)
            
            response = openai.ChatCompletion.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": "Ты - творческий AI помощник. Создавай качественный контент по запросу пользователя."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            content = response['choices'][0]['message']['content'].strip()
            
            self._update_generation(generation_id, 'completed', generated_content=content)
            
            return {
                'success': True,
                'type': 'text',
                'content': content,
                'model': active_model
            }
        except Exception as e:
            logger.error(f"❌ Text generation error: {e}")
            if 'generation_id' in locals():
                self._update_generation(generation_id, 'failed', error_message=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_image(self, prompt: str, user_id: int) -> Dict:
        """Generate image using DALL-E 3"""
        try:
            generation_id = self._log_generation(user_id, prompt, 'image', 'dall-e-3')
            
            response = openai.Image.create(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality="standard"
            )
            
            image_url = response['data'][0]['url']
            
            self._update_generation(generation_id, 'completed', image_url=image_url)
            
            return {
                'success': True,
                'type': 'image',
                'url': image_url,
                'model': 'dall-e-3'
            }
        except Exception as e:
            logger.error(f"❌ Image generation error: {e}")
            if 'generation_id' in locals():
                self._update_generation(generation_id, 'failed', error_message=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_video(self, prompt: str, user_id: int, video_url: str = None, duration: int = 5, resolution: str = "1080p") -> Dict:
        """
        Log video generation to database
        Note: Actual video generation is now handled by VideoGenerator class
        """
        try:
            generation_id = self._log_generation(user_id, prompt, 'video', 'openai-sora')
            
            if video_url:
                self._update_generation(generation_id, 'completed', video_url=video_url)
                return {
                    'success': True,
                    'type': 'video',
                    'url': video_url,
                    'model': 'openai-sora',
                    'duration': duration,
                    'resolution': resolution
                }
            else:
                self._update_generation(generation_id, 'failed', error_message='No video URL provided')
                return {
                    'success': False,
                    'error': 'No video URL provided'
                }
        except Exception as e:
            logger.error(f"❌ Video generation logging error: {e}")
            if 'generation_id' in locals():
                self._update_generation(generation_id, 'failed', error_message=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    

    
    def _log_generation(self, user_id: int, request_text: str, content_type: str, model_used: str) -> int:
        """Log a generation request to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO content_generations 
                (user_id, request_text, content_type, model_used, status)
                VALUES (?, ?, ?, ?, 'processing')
            ''', (user_id, request_text, content_type, model_used))
            
            generation_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return generation_id
        except Exception as e:
            logger.error(f"❌ Error logging generation: {e}")
            return 0
    
    def _update_generation(self, generation_id: int, status: str, 
                          generated_content: str = None, 
                          image_url: str = None,
                          video_url: str = None,
                          error_message: str = None):
        """Update generation status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            update_fields = ['status = ?']
            values = [status]
            
            if generated_content:
                update_fields.append('generated_content = ?')
                values.append(generated_content)
            
            if image_url:
                update_fields.append('image_url = ?')
                values.append(image_url)
            
            if video_url:
                update_fields.append('video_url = ?')
                values.append(video_url)
            
            if error_message:
                update_fields.append('error_message = ?')
                values.append(error_message)
            
            if status in ['completed', 'failed']:
                update_fields.append('completed_at = CURRENT_TIMESTAMP')
            
            values.append(generation_id)
            
            query = f"UPDATE content_generations SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ Error updating generation: {e}")
    
    def get_active_model(self) -> str:
        """Get the currently active GPT model"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT active_model FROM gpt_settings WHERE id = 1')
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0]
            return self.gpt_model
        except Exception as e:
            logger.error(f"❌ Error getting active model: {e}")
            return self.gpt_model
    
    def set_active_model(self, model: str, user_id: int) -> bool:
        """Set the active GPT model"""
        valid_models = ['gpt-4o-mini', 'gpt-4o', 'gpt-4', 'gpt-3.5-turbo', 'gpt-4-turbo']
        
        if model not in valid_models:
            logger.error(f"❌ Invalid model: {model}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE gpt_settings 
                SET active_model = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = 1
            ''', (model, user_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Active model changed to: {model}")
            return True
        except Exception as e:
            logger.error(f"❌ Error setting active model: {e}")
            return False
    
    def get_generation_history(self, user_id: int = None, limit: int = 10) -> list:
        """Get generation history"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute('''
                    SELECT id, request_text, content_type, status, model_used, created_at
                    FROM content_generations
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (user_id, limit))
            else:
                cursor.execute('''
                    SELECT id, user_id, request_text, content_type, status, model_used, created_at
                    FROM content_generations
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return rows
        except Exception as e:
            logger.error(f"❌ Error getting generation history: {e}")
            return []
