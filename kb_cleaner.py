#!/usr/bin/env python3
"""
Knowledge Base Cleaner & Importer v4.0
Очистка, нормализация и импорт базы знаний в v4.0
"""

import json
import re
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class KBCleaner:
    """Очистка и нормализация базы знаний"""
    
    # Паттерны мусора для удаления
    NOISE_PATTERNS = [
        r'Главная\s+',
        r'Была ли эта статья полезной\?.*?$',
        r'Да\s+Нет\s+Пользователи.*?$',
        r'Просмотров:\s*\d+',
        r'Colizeum\s*\|?\s*HelpDeskEddy',
        r'(?:считающие|которые считают) этот материал полезным:\s*\d+\s*из\s*\d+',
        r'\s+-\s+Colizeum\s*\|.*?$',
        r'support\.colizeumarena\.ru.*?html',
        r'Colizeum_KB/.*?\.html',
    ]
    
    # Навигационные паттерны
    NAVIGATION_PATTERNS = [
        r'^(?:Web версия CRM|Административная консоль|Клиентская оболочка|Планшет)\s*',
        r'^(?:FAQ|Настройки|Проблемы|Сервисы|Обслуживание)\s*-?\s*',
    ]
    
    # Паттерны для разделения вопроса и ответа
    QUESTION_ANSWER_SEPARATORS = [
        'Как это работает?',
        'Инструкция:',
        'Для того',
        'Необходимо',
        'Перейдите',
        'Откройте',
        'Нажмите',
        'Зайдите',
    ]
    
    def clean_text(self, text: str) -> str:
        """Основная очистка текста"""
        if not text:
            return ""
        
        # Убираем лишние пробелы и переносы
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Убираем мусорные паттерны
        for pattern in self.NOISE_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Убираем повторяющиеся названия категорий
        text = re.sub(r'([\w\s]+)\s+\1+', r'\1', text)
        
        # Убираем множественные пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_clean_question(self, raw_question: str) -> str:
        """Извлечение чистого вопроса"""
        # Убираем суффиксы
        question = re.sub(r'\s*-\s*Colizeum.*$', '', raw_question, flags=re.IGNORECASE)
        question = re.sub(r'\s*\|\s*HelpDeskEddy.*$', '', question, flags=re.IGNORECASE)
        
        # Если это просто название категории - делаем вопросом
        if not question.strip().endswith('?'):
            # Проверяем есть ли смысл
            if len(question.split()) <= 8 and not any(sep in question for sep in ['Как', 'Что', 'Где', 'Почему']):
                question = f"Что такое {question}?"
        
        return self.clean_text(question)
    
    def extract_meaningful_answer(self, raw_answer: str, question: str) -> str:
        """Извлечение осмысленного ответа"""
        answer = self.clean_text(raw_answer)
        
        # Удаляем повторение вопроса в начале ответа
        question_base = question.replace('?', '').strip()
        if answer.startswith(question_base):
            answer = answer[len(question_base):].strip()
        
        # Убираем длинные списки навигации (больше 5 элементов подряд)
        # Пример: "FAQ Настройки Проблемы Сервисы Обслуживание"
        words = answer.split()
        if len(words) > 10:
            # Ищем участок из коротких заглавных слов
            nav_end = 0
            for i in range(min(30, len(words))):
                word = words[i]
                # Если слово короткое и заглавное - это навигация
                if len(word) <= 15 and (word[0].isupper() or word.isupper()):
                    nav_end = i + 1
                else:
                    # Встретили нормальное предложение
                    if len(word) > 4:
                        break
            
            if nav_end > 5:  # Удаляем если > 5 навигационных слов
                answer = ' '.join(words[nav_end:])
        
        # Если ответ начинается с навигации - находим начало содержательной части
        for separator in self.QUESTION_ANSWER_SEPARATORS:
            if separator in answer:
                # Берём с этого места
                idx = answer.find(separator)
                answer = answer[idx:].strip()
                break
        
        # Убираем навигационные блоки из начала
        for pattern in self.NAVIGATION_PATTERNS:
            answer = re.sub(f'^{pattern}', '', answer, flags=re.IGNORECASE)
        
        # Убираем типичные навигационные конструкции
        nav_prefixes = [
            r'^[А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+\s+',
            r'^FAQ\s+',
            r'^Web версия CRM\s+',
            r'^Административная консоль\s+',
        ]
        for prefix in nav_prefixes:
            answer = re.sub(prefix, '', answer)
        
        # Разбиваем длинный текст на параграфы
        answer = self.format_paragraphs(answer)
        
        return answer.strip()
    
    def format_paragraphs(self, text: str) -> str:
        """Форматирование в параграфы"""
        # Разбиваем по ключевым словам начала предложений
        split_markers = [
            'Для того чтобы',
            'Необходимо',
            'Инструкция:',
            'Шаг',
            'Пример:',
            'Внимание:',
            'Важно:',
        ]
        
        for marker in split_markers:
            text = text.replace(f' {marker}', f'\n\n{marker}')
        
        # Нумерованные списки
        text = re.sub(r'(\d+)\)', r'\n\n\1)', text)
        
        # Убираем множественные переносы
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def extract_steps(self, text: str) -> List[str]:
        """Извлечение шагов из инструкции"""
        steps = []
        
        # Ищем нумерованные пункты
        matches = re.finditer(r'(\d+)[).]\s*([^0-9]+?)(?=\d+[).]|\Z)', text, re.DOTALL)
        for match in matches:
            step_num = match.group(1)
            step_text = self.clean_text(match.group(2))
            if step_text:
                steps.append(f"{step_num}. {step_text}")
        
        return steps
    
    def improve_question(self, question: str, answer: str, category: str) -> str:
        """Улучшение вопроса на основе контекста"""
        # Если вопрос слишком общий - улучшаем
        if question.startswith("Что такое") and len(question.split()) <= 5:
            # Извлекаем ключевые слова из ответа
            answer_lower = answer.lower()
            
            if 'как' in answer_lower[:50]:
                # Инструкция
                return question.replace("Что такое", "Как работает")
            elif 'настройка' in answer_lower[:50]:
                return question.replace("Что такое", "Как настроить")
            elif 'установ' in answer_lower[:50]:
                return question.replace("Что такое", "Как установить")
        
        return question
    
    def clean_record(self, record: Dict) -> Dict:
        """Очистка одной записи"""
        try:
            # Извлекаем поля
            raw_question = record.get('question', '')
            raw_answer = record.get('answer', '')
            category = record.get('category', 'general')
            tags = record.get('tags', [])
            source = record.get('source', '')
            
            # Очищаем вопрос
            question = self.extract_clean_question(raw_question)
            
            # Очищаем ответ
            answer = self.extract_meaningful_answer(raw_answer, question)
            
            # Улучшаем вопрос
            question = self.improve_question(question, answer, category)
            
            # Проверяем качество
            if not question or not answer:
                return None
            
            if len(answer) < 20:  # Слишком короткий ответ
                return None
            
            # Формируем теги
            if isinstance(tags, list):
                tags_str = ','.join(tags)
            else:
                tags_str = str(tags)
            
            # Добавляем автоматические теги из категории
            if category and category not in tags_str:
                if tags_str:
                    tags_str += f',{category}'
                else:
                    tags_str = category
            
            return {
                'question': question,
                'answer': answer,
                'category': category,
                'tags': tags_str.lower(),
                'source': 'colizeum_kb_cleaned',
                'confidence': 0.8  # Средняя уверенность для импорта
            }
            
        except Exception as e:
            logger.error(f"Ошибка очистки записи: {e}")
            return None


def load_jsonl(filepath: str) -> List[Dict]:
    """Загрузка JSONL файла"""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                logger.warning(f"Строка {line_num}: ошибка JSON - {e}")
    
    return records


def save_jsonl(records: List[Dict], filepath: str):
    """Сохранение в JSONL"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Использование: python3 kb_cleaner.py <input.jsonl> [output.jsonl]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'knowledge_cleaned.jsonl'
    
    print("=" * 60)
    print("  Knowledge Base Cleaner v4.0")
    print("=" * 60)
    print()
    
    # Загружаем
    print(f"📖 Загрузка: {input_file}")
    records = load_jsonl(input_file)
    print(f"✅ Загружено: {len(records)} записей")
    
    # Очищаем
    print(f"\n🧹 Очистка записей...")
    cleaner = KBCleaner()
    
    cleaned_records = []
    skipped = 0
    
    for i, record in enumerate(records, 1):
        if i % 50 == 0:
            print(f"  Обработано: {i}/{len(records)}")
        
        cleaned = cleaner.clean_record(record)
        
        if cleaned:
            cleaned_records.append(cleaned)
        else:
            skipped += 1
    
    print(f"✅ Очищено: {len(cleaned_records)} записей")
    print(f"⚠️  Пропущено: {skipped} записей")
    
    # Дедупликация
    print(f"\n🔍 Дедупликация...")
    unique_records = []
    seen_questions = set()
    
    for record in cleaned_records:
        q_normalized = record['question'].lower().strip()
        if q_normalized not in seen_questions:
            unique_records.append(record)
            seen_questions.add(q_normalized)
    
    duplicates = len(cleaned_records) - len(unique_records)
    print(f"✅ Уникальных: {len(unique_records)} записей")
    if duplicates > 0:
        print(f"⚠️  Дубликатов: {duplicates} записей")
    
    # Сохраняем
    print(f"\n💾 Сохранение: {output_file}")
    save_jsonl(unique_records, output_file)
    print(f"✅ Сохранено!")
    
    # Примеры
    print("\n" + "=" * 60)
    print("📝 Примеры очищенных записей:")
    print("=" * 60)
    
    for i, record in enumerate(unique_records[:3], 1):
        print(f"\nЗапись #{i}:")
        print(f"  Вопрос: {record['question']}")
        print(f"  Ответ: {record['answer'][:150]}...")
        print(f"  Категория: {record['category']}")
        print(f"  Теги: {record['tags']}")
    
    print("\n" + "=" * 60)
    print("🎉 Готово!")
    print("=" * 60)
    print()
    print(f"Следующий шаг: импорт в v4.0")
    print(f"  python3 kb_importer.py {output_file}")


if __name__ == '__main__':
    main()
