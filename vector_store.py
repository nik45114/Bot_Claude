#!/usr/bin/env python3
"""
Vector Store - векторное хранилище на FAISS
Быстрый kNN-поиск по эмбеддингам
"""

import faiss
import numpy as np
import pickle
import os
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

VECTOR_INDEX_PATH = 'vector_index.faiss'
METADATA_PATH = 'vector_metadata.pkl'


class VectorStore:
    """FAISS-based векторное хранилище"""
    
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self.index = None
        self.metadata = {}  # id -> {kb_id, category, tags, ...}
        self.id_map = []  # vector_id -> kb_id
        
        # Пытаемся загрузить существующий индекс
        self.load()
        
        # Если не удалось - создаём новый
        if self.index is None:
            self._create_index()
    
    def _create_index(self):
        """Создание нового FAISS индекса"""
        # Используем IndexFlatIP (Inner Product) для косинусного сходства
        # Векторы должны быть нормализованы
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = {}
        self.id_map = []
        
        logger.info(f"Создан новый FAISS индекс: {self.dimension}D")
    
    def _normalize_vector(self, vector: List[float]) -> np.ndarray:
        """Нормализация вектора для косинусного сходства"""
        vec = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(vec)
        
        if norm == 0:
            return vec
        
        return vec / norm
    
    def upsert(self, kb_id: int, vector: List[float], 
               metadata: Optional[Dict] = None):
        """Добавить или обновить вектор"""
        # Нормализуем вектор
        norm_vec = self._normalize_vector(vector)
        
        # Проверяем есть ли уже такой kb_id
        if kb_id in self.id_map:
            # Обновление - удаляем старый и добавляем новый
            # FAISS не поддерживает обновление напрямую, нужна переиндексация
            self.remove(kb_id)
        
        # Добавляем в индекс
        vector_id = len(self.id_map)
        self.index.add(norm_vec.reshape(1, -1))
        
        # Сохраняем маппинг и метаданные
        self.id_map.append(kb_id)
        self.metadata[kb_id] = metadata or {}
        
        logger.debug(f"Upsert: kb_id={kb_id}, vector_id={vector_id}")
    
    def remove(self, kb_id: int) -> bool:
        """Удалить вектор (через переиндексацию)"""
        if kb_id not in self.id_map:
            return False
        
        # Удаляем из маппинга
        vector_id = self.id_map.index(kb_id)
        
        # Получаем все векторы кроме удаляемого
        all_vectors = []
        new_id_map = []
        new_metadata = {}
        
        for i, mapped_kb_id in enumerate(self.id_map):
            if mapped_kb_id != kb_id:
                vec = self.index.reconstruct(i)
                all_vectors.append(vec)
                new_id_map.append(mapped_kb_id)
                new_metadata[mapped_kb_id] = self.metadata.get(mapped_kb_id, {})
        
        # Пересоздаём индекс
        self._create_index()
        
        if all_vectors:
            vectors_array = np.array(all_vectors, dtype=np.float32)
            self.index.add(vectors_array)
        
        self.id_map = new_id_map
        self.metadata = new_metadata
        
        logger.info(f"Removed kb_id={kb_id}")
        return True
    
    def search(self, query_vector: List[float], top_k: int = 5, 
               min_score: float = 0.5) -> List[Dict]:
        """Поиск похожих векторов"""
        if self.index.ntotal == 0:
            return []
        
        # Нормализуем запрос
        norm_query = self._normalize_vector(query_vector)
        
        # Ограничиваем top_k размером индекса
        k = min(top_k, self.index.ntotal)
        
        # Поиск
        scores, indices = self.index.search(norm_query.reshape(1, -1), k)
        
        # Формируем результаты
        results = []
        
        for score, idx in zip(scores[0], indices[0]):
            # Пропускаем если score ниже порога
            if score < min_score:
                continue
            
            # Пропускаем невалидные индексы
            if idx < 0 or idx >= len(self.id_map):
                continue
            
            kb_id = self.id_map[idx]
            
            results.append({
                'kb_id': kb_id,
                'score': float(score),
                'metadata': self.metadata.get(kb_id, {})
            })
        
        return results
    
    def batch_upsert(self, items: List[Tuple[int, List[float], Dict]]):
        """Батч-добавление векторов"""
        for kb_id, vector, metadata in items:
            self.upsert(kb_id, vector, metadata)
        
        logger.info(f"Batch upsert: {len(items)} items")
    
    def reindex(self, items: List[Tuple[int, List[float], Dict]]):
        """Полная переиндексация"""
        logger.info(f"Reindexing: {len(items)} items...")
        
        # Создаём новый индекс
        self._create_index()
        
        # Добавляем все векторы
        vectors = []
        
        for kb_id, vector, metadata in items:
            norm_vec = self._normalize_vector(vector)
            vectors.append(norm_vec)
            
            self.id_map.append(kb_id)
            self.metadata[kb_id] = metadata
        
        if vectors:
            vectors_array = np.array(vectors, dtype=np.float32)
            self.index.add(vectors_array)
        
        logger.info(f"Reindex complete: {self.index.ntotal} vectors")
    
    def save(self):
        """Сохранить индекс на диск"""
        try:
            # Сохраняем FAISS индекс
            faiss.write_index(self.index, VECTOR_INDEX_PATH)
            
            # Сохраняем метаданные
            with open(METADATA_PATH, 'wb') as f:
                pickle.dump({
                    'id_map': self.id_map,
                    'metadata': self.metadata,
                    'dimension': self.dimension
                }, f)
            
            logger.info(f"Vector store saved: {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    def load(self) -> bool:
        """Загрузить индекс с диска"""
        try:
            if not os.path.exists(VECTOR_INDEX_PATH):
                return False
            
            # Загружаем FAISS индекс
            self.index = faiss.read_index(VECTOR_INDEX_PATH)
            
            # Загружаем метаданные
            with open(METADATA_PATH, 'rb') as f:
                data = pickle.load(f)
                self.id_map = data['id_map']
                self.metadata = data['metadata']
                self.dimension = data['dimension']
            
            logger.info(f"Vector store loaded: {self.index.ntotal} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            return False
    
    def stats(self) -> Dict:
        """Статистика индекса"""
        return {
            'total_vectors': self.index.ntotal if self.index else 0,
            'dimension': self.dimension,
            'metadata_count': len(self.metadata)
        }


# Тестирование
if __name__ == '__main__':
    # Создаём store
    store = VectorStore(dimension=1536)
    
    # Тестовые векторы
    import random
    
    test_data = [
        (1, [random.random() for _ in range(1536)], {'category': 'test', 'tags': 'tag1,tag2'}),
        (2, [random.random() for _ in range(1536)], {'category': 'test', 'tags': 'tag3'}),
        (3, [random.random() for _ in range(1536)], {'category': 'other', 'tags': 'tag1'}),
    ]
    
    # Добавляем
    for kb_id, vec, meta in test_data:
        store.upsert(kb_id, vec, meta)
    
    # Поиск
    query_vec = [random.random() for _ in range(1536)]
    results = store.search(query_vec, top_k=2)
    
    print(f"Найдено: {len(results)}")
    for r in results:
        print(f"  kb_id={r['kb_id']}, score={r['score']:.4f}")
    
    # Сохраняем
    store.save()
    
    # Статистика
    print(f"\nСтатистика: {store.stats()}")
