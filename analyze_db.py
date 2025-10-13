#!/usr/bin/env python3
"""
Автоматический анализ и улучшение базы знаний
- Авто-тегирование через GPT
- Поиск и объединение дублей
- Категоризация
- Статистика и отчёты
"""

import sqlite3
import json
import sys
import re
from difflib import SequenceMatcher
import openai

DB_PATH = 'knowledge.db'
CONFIG_PATH = 'config.json'


def load_config():
    """Загрузка конфига"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        print("❌ Не могу загрузить config.json")
        sys.exit(1)


class DBAnalyzer:
    """Анализатор базы данных"""
    
    def __init__(self, db_path, gpt_api_key):
        self.db_path = db_path
        openai.api_key = gpt_api_key
        self.model = "gpt-4o-mini"
    
    def get_all_records(self):
        """Получить все актуальные записи"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, question, answer, category, tags 
            FROM knowledge 
            WHERE is_current = 1
        ''')
        records = cursor.fetchall()
        conn.close()
        return records
    
    def analyze_record(self, question, answer):
        """Анализ записи через GPT"""
        try:
            prompt = f"""Проанализируй вопрос и ответ. Верни ТОЛЬКО JSON:

Вопрос: {question}
Ответ: {answer}

Формат (строго JSON, без текста):
{{
  "category": "категория",
  "tags": "тег1,тег2,тег3,тег4,тег5"
}}

Категории:
- hardware (железо, компьютеры, периферия, биос, мат платы)
- software (программы, ОС, драйвера, утилиты, CLS)
- games (игры, Steam, лаунчеры, геймплей)
- service (услуги клуба, цены, время, бронирование)
- admin (администрирование, управление клубом)
- billing (оплата, счета, тарифы, абонементы)
- schedule (расписание, время работы, часы)
- general (всё остальное)

Теги: 3-5 ключевых слов на русском, строчными буквами, через запятую БЕЗ пробелов."""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            text = response.choices[0].message.content.strip()
            
            # Парсим JSON
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                
                # Валидация категории
                valid_cats = ['hardware', 'software', 'games', 'service', 'admin', 'billing', 'schedule', 'general']
                if data.get('category') not in valid_cats:
                    data['category'] = 'general'
                
                # Очистка тегов
                tags = data.get('tags', '')
                tags = re.sub(r'\s+', '', tags)  # Убираем пробелы
                tags = ','.join(filter(None, tags.lower().split(',')))
                data['tags'] = tags[:200]
                
                return data
            
        except Exception as e:
            print(f"Ошибка анализа: {e}")
        
        return {'category': 'general', 'tags': ''}
    
    def find_duplicates(self, records, threshold=0.80):
        """Поиск дубликатов"""
        duplicates = []
        
        for i, (id1, q1, a1, cat1, tags1) in enumerate(records):
            for id2, q2, a2, cat2, tags2 in records[i+1:]:
                # Сходство вопросов
                q_sim = SequenceMatcher(None, q1.lower(), q2.lower()).ratio()
                
                # Сходство ответов
                a_sim = SequenceMatcher(None, a1.lower(), a2.lower()).ratio()
                
                # Общая схожесть (вопрос важнее)
                similarity = q_sim * 0.7 + a_sim * 0.3
                
                if similarity >= threshold:
                    duplicates.append({
                        'id1': id1,
                        'id2': id2,
                        'question1': q1,
                        'question2': q2,
                        'similarity': round(similarity * 100, 1)
                    })
        
        return duplicates
    
    def update_record(self, id, category, tags):
        """Обновление записи"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE knowledge 
                SET category = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (category, tags, id))
            conn.commit()
            conn.close()
            return True
        except:
            return False
    
    def merge_duplicates(self, id_keep, id_remove):
        """Объединение дубликатов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем теги обеих записей
            cursor.execute('SELECT tags FROM knowledge WHERE id IN (?, ?)', (id_keep, id_remove))
            tags_list = cursor.fetchall()
            
            # Объединяем теги
            all_tags = set()
            for (tags,) in tags_list:
                if tags:
                    all_tags.update(tags.split(','))
            
            merged_tags = ','.join(sorted(filter(None, all_tags)))
            
            # Обновляем основную запись
            cursor.execute('''
                UPDATE knowledge 
                SET tags = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (merged_tags, id_keep))
            
            # Помечаем дубликат как неактуальный
            cursor.execute('''
                UPDATE knowledge 
                SET is_current = 0, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (id_remove,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка merge: {e}")
            return False
    
    def get_stats(self):
        """Статистика БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Всего
        cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 1')
        stats['total'] = cursor.fetchone()[0]
        
        # Без тегов
        cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 1 AND (tags = "" OR tags IS NULL)')
        stats['no_tags'] = cursor.fetchone()[0]
        
        # По категориям
        cursor.execute('SELECT category, COUNT(*) FROM knowledge WHERE is_current = 1 GROUP BY category')
        stats['by_category'] = dict(cursor.fetchall())
        
        # Legacy
        cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 0')
        stats['legacy'] = cursor.fetchone()[0]
        
        conn.close()
        return stats


def main():
    print("🔍 Анализатор базы знаний v3.0\n")
    
    # Загружаем конфиг
    config = load_config()
    analyzer = DBAnalyzer(DB_PATH, config['openai_api_key'])
    
    # Меню
    print("Выберите действие:")
    print("1. Автоматическое тегирование (через GPT)")
    print("2. Поиск дубликатов")
    print("3. Объединение дубликатов (автоматически)")
    print("4. Полный анализ (всё сразу)")
    print("5. Статистика")
    print("0. Выход")
    
    choice = input("\nВыбор: ").strip()
    
    if choice == '1':
        # Автотегирование
        print("\n⏳ Получаю записи...")
        records = analyzer.get_all_records()
        
        print(f"Найдено {len(records)} записей")
        
        # Фильтруем только те, у которых нет тегов
        no_tags = [(id, q, a, cat, tags) for id, q, a, cat, tags in records if not tags]
        
        print(f"Без тегов: {len(no_tags)}")
        
        if not no_tags:
            print("✅ Все записи уже имеют теги!")
            return
        
        confirm = input(f"\nОбработать {len(no_tags)} записей через GPT? (y/n): ")
        
        if confirm.lower() != 'y':
            print("Отменено")
            return
        
        print("\n⏳ Обрабатываю...")
        
        success = 0
        for i, (id, q, a, cat, tags) in enumerate(no_tags, 1):
            print(f"[{i}/{len(no_tags)}] {q[:50]}...")
            
            analysis = analyzer.analyze_record(q, a)
            
            if analyzer.update_record(id, analysis['category'], analysis['tags']):
                success += 1
                print(f"  → {analysis['category']} | {analysis['tags'][:50]}")
        
        print(f"\n✅ Обработано: {success}/{len(no_tags)}")
    
    elif choice == '2':
        # Поиск дубликатов
        print("\n⏳ Ищу дубликаты...")
        records = analyzer.get_all_records()
        
        duplicates = analyzer.find_duplicates(records, threshold=0.80)
        
        if not duplicates:
            print("✅ Дубликатов не найдено!")
            return
        
        print(f"\n🔍 Найдено дубликатов: {len(duplicates)}\n")
        
        for i, dup in enumerate(duplicates[:10], 1):  # Показываем топ-10
            print(f"{i}. Схожесть: {dup['similarity']}%")
            print(f"   ID1: {dup['id1']} | {dup['question1'][:60]}")
            print(f"   ID2: {dup['id2']} | {dup['question2'][:60]}")
            print()
        
        if len(duplicates) > 10:
            print(f"... и ещё {len(duplicates) - 10} пар")
    
    elif choice == '3':
        # Автоматическое объединение
        print("\n⏳ Ищу и объединяю дубликаты...")
        records = analyzer.get_all_records()
        
        duplicates = analyzer.find_duplicates(records, threshold=0.85)
        
        if not duplicates:
            print("✅ Дубликатов не найдено!")
            return
        
        print(f"Найдено пар: {len(duplicates)}")
        
        confirm = input(f"\nОбъединить автоматически? (y/n): ")
        
        if confirm.lower() != 'y':
            print("Отменено")
            return
        
        merged = 0
        for dup in duplicates:
            # Оставляем запись с меньшим ID (более старую)
            id_keep = min(dup['id1'], dup['id2'])
            id_remove = max(dup['id1'], dup['id2'])
            
            if analyzer.merge_duplicates(id_keep, id_remove):
                merged += 1
                print(f"✓ Объединил {id_remove} → {id_keep}")
        
        print(f"\n✅ Объединено: {merged} пар")
    
    elif choice == '4':
        # Полный анализ
        print("\n🚀 Полный анализ базы\n")
        
        # Шаг 1: Статистика
        print("📊 Статистика:")
        stats = analyzer.get_stats()
        print(f"  Всего записей: {stats['total']}")
        print(f"  Без тегов: {stats['no_tags']}")
        print(f"  Legacy: {stats['legacy']}\n")
        
        if stats['by_category']:
            print("  По категориям:")
            for cat, cnt in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                print(f"    • {cat}: {cnt}")
        
        print()
        
        # Шаг 2: Тегирование
        if stats['no_tags'] > 0:
            print(f"⏳ Шаг 1/2: Тегирование {stats['no_tags']} записей...")
            
            records = analyzer.get_all_records()
            no_tags = [(id, q, a, cat, tags) for id, q, a, cat, tags in records if not tags]
            
            for i, (id, q, a, cat, tags) in enumerate(no_tags, 1):
                if i % 10 == 0:
                    print(f"  Обработано: {i}/{len(no_tags)}")
                
                analysis = analyzer.analyze_record(q, a)
                analyzer.update_record(id, analysis['category'], analysis['tags'])
            
            print(f"✅ Теги добавлены: {len(no_tags)}\n")
        
        # Шаг 3: Дубликаты
        print("⏳ Шаг 2/2: Поиск дубликатов...")
        
        records = analyzer.get_all_records()
        duplicates = analyzer.find_duplicates(records, threshold=0.85)
        
        if duplicates:
            print(f"  Найдено пар: {len(duplicates)}")
            
            merged = 0
            for dup in duplicates:
                id_keep = min(dup['id1'], dup['id2'])
                id_remove = max(dup['id1'], dup['id2'])
                
                if analyzer.merge_duplicates(id_keep, id_remove):
                    merged += 1
            
            print(f"✅ Объединено: {merged}\n")
        else:
            print("✅ Дубликатов нет\n")
        
        # Итоговая статистика
        print("📊 Итоговая статистика:")
        final_stats = analyzer.get_stats()
        print(f"  Всего записей: {final_stats['total']}")
        print(f"  С тегами: {final_stats['total'] - final_stats['no_tags']}")
        print(f"  Legacy: {final_stats['legacy']}")
        
        print("\n🎉 Полный анализ завершён!")
    
    elif choice == '5':
        # Статистика
        print("\n📊 Статистика базы данных\n")
        
        stats = analyzer.get_stats()
        
        print(f"Всего записей: {stats['total']}")
        print(f"Без тегов: {stats['no_tags']}")
        print(f"Legacy: {stats['legacy']}\n")
        
        if stats['by_category']:
            print("По категориям:")
            for cat, cnt in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                pct = (cnt / stats['total'] * 100) if stats['total'] > 0 else 0
                print(f"  • {cat:12s}: {cnt:3d} ({pct:.1f}%)")
    
    else:
        print("Выход")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
