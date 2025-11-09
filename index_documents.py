#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Index Documents - Индексация .md файлов в векторную БД
Запускать вручную для обновления базы знаний
"""

import sys
import json
import logging

from embeddings import EmbeddingService
from vector_store import VectorStore
from bot import KnowledgeBase
from smart_assistant import SmartAssistant

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def load_config():
    """Загрузить конфигурацию"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Error loading config: {e}")
        sys.exit(1)


def main():
    """Основная функция индексации"""
    print("\n" + "="*60)
    print("📚 ИНДЕКСАЦИЯ ДОКУМЕНТОВ")
    print("="*60 + "\n")

    # Загружаем конфиг
    config = load_config()
    api_key = config.get('openai_api_key')

    if not api_key:
        print("❌ OpenAI API key not found in config.json")
        sys.exit(1)

    print(f"✅ Config loaded")
    print(f"🔑 API Key: {api_key[:20]}...\n")

    # Инициализация сервисов
    print("⚙️ Initializing services...")
    embedding_service = EmbeddingService(api_key)
    vector_store = VectorStore()
    vector_store.load()

    kb = KnowledgeBase(
        db_path='knowledge.db',
        embedding_service=embedding_service,
        vector_store=vector_store
    )

    assistant = SmartAssistant(
        kb=kb,
        embedding_service=embedding_service,
        vector_store=vector_store,
        db_path='knowledge.db',
        gpt_model='gpt-4o-mini'
    )

    print("✅ Services initialized\n")

    # Статистика до индексации
    stats_before = assistant.get_stats()
    print("📊 Before indexing:")
    print(f"   Vector store size: {stats_before['vector_store_size']}")
    print(f"   KB size: {stats_before['kb_size']}\n")

    # Индексация
    print("🔄 Starting indexing...")
    print("-" * 60)

    indexed_count = assistant.index_markdown_files(docs_dir='.')

    print("-" * 60)
    print(f"\n✅ Indexing complete!")
    print(f"   Indexed: {indexed_count} document chunks\n")

    # Статистика после индексации
    stats_after = assistant.get_stats()
    print("📊 After indexing:")
    print(f"   Vector store size: {stats_after['vector_store_size']}")
    print(f"   KB size: {stats_after['kb_size']}")
    print(f"   Added: {stats_after['vector_store_size'] - stats_before['vector_store_size']} vectors\n")

    print("="*60)
    print("✅ ИНДЕКСАЦИЯ ЗАВЕРШЕНА")
    print("="*60 + "\n")

    print("💡 Tip: Перезапустите бота для использования обновлённой базы")
    print("   systemctl restart club_assistant\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
