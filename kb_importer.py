#!/usr/bin/env python3
"""
Knowledge Base Importer v4.0
Импорт очищенной базы знаний в систему v4.0
"""

import json
import sqlite3
import sys
import os
from embeddings import EmbeddingService
from vector_store import VectorStore
from draft_queue import DraftQueue

DB_PATH = 'knowledge.db'
CONFIG_PATH = 'config.json'


def load_config():
    """Загрузка конфигурации"""
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def load_jsonl(filepath: str):
    """Загрузка JSONL файла"""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def check_duplicate(cursor, question: str) -> bool:
    """Проверка дубликата по вопросу"""
    cursor.execute('''
        SELECT COUNT(*) FROM knowledge
        WHERE LOWER(TRIM(question)) = LOWER(TRIM(?))
        AND is_current = 1
    ''', (question,))
    
    count = cursor.fetchone()[0]
    return count > 0


def import_to_kb(records, conn, embedding_service, vector_store):
    """Импорт в базу знаний с векторизацией"""
    cursor = conn.cursor()
    
    imported = 0
    skipped_duplicates = 0
    errors = 0
    
    print(f"\n📥 Импорт {len(records)} записей...")
    
    for i, record in enumerate(records, 1):
        try:
            question = record['question']
            answer = record['answer']
            category = record.get('category', 'general')
            tags = record.get('tags', '')
            source = record.get('source', 'import')
            
            # Проверяем дубликат
            if check_duplicate(cursor, question):
                skipped_duplicates += 1
                continue
            
            # Добавляем в БД
            cursor.execute('''
                INSERT INTO knowledge
                (question, answer, category, tags, source, added_by, is_current)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (question, answer, category, tags, source, 0))
            
            kb_id = cursor.lastrowid
            
            # Создаём эмбеддинг
            combined_text = embedding_service.combine_qa(question, answer)
            vector = embedding_service.embed(combined_text)
            
            # Добавляем в векторный индекс
            vector_store.upsert(kb_id, vector, {
                'category': category,
                'tags': tags,
                'question': question[:100]
            })
            
            imported += 1
            
            if i % 10 == 0:
                print(f"  Прогресс: {i}/{len(records)} ({imported} импортировано)")
                conn.commit()
                vector_store.save()
        
        except Exception as e:
            errors += 1
            print(f"  ❌ Ошибка запись #{i}: {e}")
    
    # Финальный коммит
    conn.commit()
    vector_store.save()
    
    return imported, skipped_duplicates, errors


def import_to_drafts(records, draft_queue):
    """Импорт в очередь на ревью (более безопасно)"""
    imported = 0
    errors = 0
    
    print(f"\n📝 Импорт {len(records)} записей в очередь на ревью...")
    
    for i, record in enumerate(records, 1):
        try:
            question = record['question']
            answer = record['answer']
            category = record.get('category', 'general')
            tags = record.get('tags', '')
            source = record.get('source', 'import')
            confidence = record.get('confidence', 0.75)
            
            # Добавляем в drafts
            draft_queue.add_draft(
                question=question,
                answer=answer,
                category=category,
                tags=tags,
                source=source,
                confidence=confidence,
                added_by=0  # system
            )
            
            imported += 1
            
            if i % 10 == 0:
                print(f"  Прогресс: {i}/{len(records)}")
        
        except Exception as e:
            errors += 1
            print(f"  ❌ Ошибка запись #{i}: {e}")
    
    return imported, errors


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 kb_importer.py <cleaned.jsonl> [--drafts]")
        print()
        print("Опции:")
        print("  --drafts    Импорт в очередь на ревью (безопаснее)")
        print("  (без флага) Импорт напрямую в базу знаний")
        sys.exit(1)
    
    input_file = sys.argv[1]
    use_drafts = '--drafts' in sys.argv
    
    if not os.path.exists(input_file):
        print(f"❌ Файл не найден: {input_file}")
        sys.exit(1)
    
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Конфиг не найден: {CONFIG_PATH}")
        sys.exit(1)
    
    print("=" * 60)
    print("  Knowledge Base Importer v4.0")
    print("=" * 60)
    print()
    
    # Загружаем конфиг
    print("⚙️  Загрузка конфигурации...")
    config = load_config()
    print("✅ Конфиг загружен")
    
    # Загружаем записи
    print(f"\n📖 Загрузка: {input_file}")
    records = load_jsonl(input_file)
    print(f"✅ Загружено: {len(records)} записей")
    
    if len(records) == 0:
        print("⚠️  Нет записей для импорта")
        sys.exit(0)
    
    # Инициализируем сервисы
    print("\n🚀 Инициализация сервисов...")
    
    if use_drafts:
        # Импорт в drafts
        print("📝 Режим: импорт в очередь на ревью (drafts)")
        draft_queue = DraftQueue(DB_PATH)
        
        imported, errors = import_to_drafts(records, draft_queue)
        
        print("\n" + "=" * 60)
        print("📊 Результаты импорта:")
        print("=" * 60)
        print(f"  Импортировано в drafts: {imported}")
        print(f"  Ошибок: {errors}")
        print()
        print("Следующий шаг:")
        print("  1. В боте: /review")
        print("  2. Одобрить записи")
        print("  3. После одобрения они попадут в базу + векторный индекс")
    
    else:
        # Импорт напрямую
        print("⚡ Режим: импорт напрямую в базу знаний")
        print("⚠️  ВНИМАНИЕ: Это добавит записи БЕЗ ревью!")
        print()
        confirm = input("Продолжить? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Отменено")
            sys.exit(0)
        
        embedding_service = EmbeddingService(config['openai_api_key'])
        vector_store = VectorStore()
        vector_store.load()
        
        conn = sqlite3.connect(DB_PATH)
        
        imported, skipped, errors = import_to_kb(
            records, conn, embedding_service, vector_store
        )
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("📊 Результаты импорта:")
        print("=" * 60)
        print(f"  Импортировано: {imported}")
        print(f"  Пропущено (дубликаты): {skipped}")
        print(f"  Ошибок: {errors}")
        print()
        print("✅ Записи добавлены в:")
        print("  - База знаний (knowledge)")
        print("  - Векторный индекс (vector_index.faiss)")
        print()
        print("Готово! Можно тестировать поиск.")
    
    print("\n" + "=" * 60)
    print("🎉 Импорт завершён!")
    print("=" * 60)


if __name__ == '__main__':
    main()
