#!/usr/bin/env python3
"""
Embeddings module - работа с векторными представлениями
Поддержка OpenAI embeddings с батчингом и кэшированием
"""

import openai
import hashlib
import json
import os
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

CACHE_DIR = '.embedding_cache'
EMBEDDING_MODEL = 'text-embedding-3-small'  # 1536 dimensions, дёшево
BATCH_SIZE = 100  # OpenAI лимит


class EmbeddingService:
    """Сервис для создания и кэширования эмбеддингов"""
    
    def __init__(self, api_key: str, model: str = EMBEDDING_MODEL):
        openai.api_key = api_key
        self.model = model
        self.dimension = 1536  # для text-embedding-3-small
        
        # Создаём директорию для кэша
        os.makedirs(CACHE_DIR, exist_ok=True)
        
        logger.info(f"EmbeddingService initialized: {model}")
    
    def _cache_key(self, text: str) -> str:
        """Генерация ключа кэша"""
        return hashlib.md5(f"{self.model}:{text}".encode()).hexdigest()
    
    def _get_cached(self, text: str) -> Optional[List[float]]:
        """Получить из кэша"""
        cache_file = os.path.join(CACHE_DIR, self._cache_key(text) + '.json')
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return None
    
    def _save_cache(self, text: str, embedding: List[float]):
        """Сохранить в кэш"""
        cache_file = os.path.join(CACHE_DIR, self._cache_key(text) + '.json')
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(embedding, f)
        except Exception as e:
            logger.error(f"Ошибка кэша: {e}")
    
    def embed(self, text: str) -> List[float]:
        """Создать эмбеддинг для одного текста"""
        # Проверяем кэш
        cached = self._get_cached(text)
        if cached:
            return cached
        
        try:
            # Очищаем текст
            text = text.strip()
            if not text:
                return [0.0] * self.dimension
            
            # Запрос к API
            response = openai.Embedding.create(
                model=self.model,
                input=text
            )
            
            embedding = response['data'][0]['embedding']
            
            # Кэшируем
            self._save_cache(text, embedding)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Ошибка embed: {e}")
            # Возвращаем нулевой вектор
            return [0.0] * self.dimension
    
    def embed_batch(self, texts: List[str], show_progress: bool = False) -> List[List[float]]:
        """Батч-создание эмбеддингов"""
        results = []
        
        # Разбиваем на батчи
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i+BATCH_SIZE]
            
            if show_progress:
                print(f"Эмбеддинг батч {i//BATCH_SIZE + 1}/{(len(texts)-1)//BATCH_SIZE + 1}...")
            
            # Проверяем кэш для каждого
            batch_embeddings = []
            to_embed = []
            to_embed_indices = []
            
            for j, text in enumerate(batch):
                cached = self._get_cached(text)
                if cached:
                    batch_embeddings.append(cached)
                else:
                    batch_embeddings.append(None)
                    to_embed.append(text)
                    to_embed_indices.append(j)
            
            # Эмбеддим только не закэшированные
            if to_embed:
                try:
                    response = openai.Embedding.create(
                        model=self.model,
                        input=to_embed
                    )
                    
                    # Сохраняем результаты
                    for idx, data in zip(to_embed_indices, response['data']):
                        embedding = data['embedding']
                        batch_embeddings[idx] = embedding
                        
                        # Кэшируем
                        self._save_cache(batch[idx], embedding)
                        
                except Exception as e:
                    logger.error(f"Ошибка batch embed: {e}")
                    # Заполняем нулями
                    for idx in to_embed_indices:
                        if batch_embeddings[idx] is None:
                            batch_embeddings[idx] = [0.0] * self.dimension
            
            results.extend(batch_embeddings)
        
        return results
    
    def combine_qa(self, question: str, answer: str) -> str:
        """Комбинирование вопроса и ответа для эмбеддинга"""
        return f"Вопрос: {question}\n\nОтвет: {answer}"
    
    def normalize_query(self, query: str) -> str:
        """Нормализация запроса для поиска"""
        # Убираем лишние пробелы
        query = ' '.join(query.split())
        
        # Приводим к нижнему регистру
        query = query.lower()
        
        return query.strip()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Косинусное сходство между векторами"""
    import math
    
    if len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


# Пример использования
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Использование: python embeddings.py 'текст для эмбеддинга'")
        sys.exit(1)
    
    # Загружаем конфиг
    with open('config.json') as f:
        config = json.load(f)
    
    service = EmbeddingService(config['openai_api_key'])
    
    text = sys.argv[1]
    embedding = service.embed(text)
    
    print(f"Текст: {text}")
    print(f"Размерность: {len(embedding)}")
    print(f"Первые 10 значений: {embedding[:10]}")
