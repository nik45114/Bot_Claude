#!/usr/bin/env python3
"""
Migration script v3.x → v4.0
Создание таблиц, эмбеддингов, векторного индекса
"""

import sqlite3
import json
import sys
import os
from embeddings import EmbeddingService
from vector_store import VectorStore
from draft_queue import DraftQueue

DB_PATH = 'knowledge.db'
CONFIG_PATH = 'config.json'


def load_config():
    """Загрузка конфига"""
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def create_draft_table(db_path):
    """Создание таблицы черновиков"""
    print("📋 Создание таблицы knowledge_drafts...")
    
    conn = sqlite3.connect(db_path)
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
    
    print("✅ Таблица knowledge_drafts создана")


def get_all_knowledge(db_path):
    """Получить все актуальные знания"""
    print("📚 Загружаю знания из БД...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, question, answer, category, tags
        FROM knowledge
        WHERE is_current = 1
    ''')
    
    records = cursor.fetchall()
    conn.close()
    
    print(f"✅ Загружено записей: {len(records)}")
    
    return records


def create_embeddings(records, embedding_service):
    """Создание эмбеддингов для всех записей"""
    print(f"\n🔄 Создание эмбеддингов для {len(records)} записей...")
    print("Это может занять несколько минут...")
    
    # Подготавливаем тексты для батч-эмбеддинга
    texts = []
    for id, question, answer, category, tags in records:
        combined = embedding_service.combine_qa(question, answer)
        texts.append(combined)
    
    # Батч-создание эмбеддингов
    embeddings = embedding_service.embed_batch(texts, show_progress=True)
    
    print(f"✅ Создано эмбеддингов: {len(embeddings)}")
    
    return embeddings


def build_vector_index(records, embeddings, vector_store):
    """Построение векторного индекса"""
    print("\n🏗️  Построение векторного индекса...")
    
    # Подготавливаем данные для индексации
    items = []
    
    for i, (id, question, answer, category, tags) in enumerate(records):
        items.append((
            id,  # kb_id
            embeddings[i],  # vector
            {
                'category': category,
                'tags': tags,
                'question': question[:100]  # для отладки
            }
        ))
    
    # Переиндексация
    vector_store.reindex(items)
    
    # Сохранение на диск
    vector_store.save()
    
    print(f"✅ Индекс построен: {len(items)} векторов")


def test_search(vector_store, embedding_service):
    """Тестирование поиска"""
    print("\n🔍 Тестирование векторного поиска...")
    
    test_queries = [
        "как обновить биос",
        "где находится клуб",
        "что такое cls"
    ]
    
    for query in test_queries:
        print(f"\n  Запрос: '{query}'")
        
        # Создаём эмбеддинг запроса
        query_vec = embedding_service.embed(query)
        
        # Поиск
        results = vector_store.search(query_vec, top_k=3, min_score=0.5)
        
        if results:
            print(f"  Найдено: {len(results)}")
            for r in results:
                print(f"    - kb_id={r['kb_id']}, score={r['score']:.3f}, cat={r['metadata'].get('category')}")
        else:
            print("  Ничего не найдено")


def main():
    print("=" * 60)
    print("   Migration v3.x → v4.0 RAG Architecture")
    print("=" * 60)
    print()
    
    # Проверяем наличие файлов
    if not os.path.exists(DB_PATH):
        print(f"❌ Не найден {DB_PATH}")
        sys.exit(1)
    
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Не найден {CONFIG_PATH}")
        sys.exit(1)
    
    # Загружаем конфиг
    print("⚙️  Загрузка конфигурации...")
    config = load_config()
    print("✅ Конфиг загружен")
    
    # Инициализируем сервисы
    print("\n🚀 Инициализация сервисов...")
    embedding_service = EmbeddingService(config['openai_api_key'])
    vector_store = VectorStore(dimension=1536)
    draft_queue = DraftQueue(DB_PATH)
    print("✅ Сервисы инициализированы")
    
    # Шаг 1: Создаём таблицу черновиков
    print("\n" + "=" * 60)
    print("Шаг 1: Таблица knowledge_drafts")
    print("=" * 60)
    create_draft_table(DB_PATH)
    
    # Шаг 2: Загружаем знания
    print("\n" + "=" * 60)
    print("Шаг 2: Загрузка знаний")
    print("=" * 60)
    records = get_all_knowledge(DB_PATH)
    
    if not records:
        print("⚠️  База знаний пуста. Миграция не требуется.")
        sys.exit(0)
    
    # Подтверждение
    print(f"\n⚠️  Будет создано {len(records)} эмбеддингов")
    print(f"Примерная стоимость: ${len(records) * 0.00002:.4f}")
    print(f"Время: ~{len(records) // 100 + 1} минут")
    
    confirm = input("\nПродолжить? (y/n): ")
    if confirm.lower() != 'y':
        print("❌ Отменено")
        sys.exit(0)
    
    # Шаг 3: Создание эмбеддингов
    print("\n" + "=" * 60)
    print("Шаг 3: Создание эмбеддингов")
    print("=" * 60)
    embeddings = create_embeddings(records, embedding_service)
    
    # Шаг 4: Построение индекса
    print("\n" + "=" * 60)
    print("Шаг 4: Построение векторного индекса")
    print("=" * 60)
    build_vector_index(records, embeddings, vector_store)
    
    # Шаг 5: Тестирование
    print("\n" + "=" * 60)
    print("Шаг 5: Тестирование")
    print("=" * 60)
    test_search(vector_store, embedding_service)
    
    # Итог
    print("\n" + "=" * 60)
    print("🎉 Миграция завершена успешно!")
    print("=" * 60)
    print()
    print("Создано:")
    print(f"  ✅ Таблица knowledge_drafts")
    print(f"  ✅ {len(embeddings)} эмбеддингов")
    print(f"  ✅ Векторный индекс FAISS")
    print(f"  ✅ Файлы: vector_index.faiss, vector_metadata.pkl")
    print()
    print("Следующий шаг:")
    print("  1. Обновите bot.py до v4.0")
    print("  2. Перезапустите: systemctl restart club_assistant")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
