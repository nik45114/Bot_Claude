#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка базы знаний"""

import sqlite3

DB_PATH = 'knowledge.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Проверяем записи где вопрос = ответ
cursor.execute('''
    SELECT id, question, answer 
    FROM knowledge 
    WHERE question = answer 
    AND is_current = 1
    LIMIT 10
''')

bad_records = cursor.fetchall()

print(f"Найдено записей где вопрос = ответ: {len(bad_records)}")
print()

for rec_id, question, answer in bad_records:
    print(f"ID: {rec_id}")
    print(f"Вопрос: {question[:100]}")
    print(f"Ответ: {answer[:100]}")
    print("-" * 60)

# Общая статистика
cursor.execute('SELECT COUNT(*) FROM knowledge WHERE is_current = 1')
total = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM knowledge WHERE question = answer AND is_current = 1')
bad_total = cursor.fetchone()[0]

print(f"\nВсего записей: {total}")
print(f"Плохих записей (вопрос=ответ): {bad_total}")
print(f"Процент плохих: {bad_total/total*100:.1f}%")

conn.close()
