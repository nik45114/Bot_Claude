#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo script showing FinMon formatted reports
Run this to see what the actual bot output looks like
"""

import sys
from datetime import date

# Setup imports
sys.path.insert(0, '/home/runner/work/Bot_Claude/Bot_Claude')
import importlib.util
import types

# Create fake parent package
finmon_package = types.ModuleType('modules.finmon')
sys.modules['modules.finmon'] = finmon_package

# Load formatters
spec = importlib.util.spec_from_file_location("modules.finmon.formatters", 
                                               "/home/runner/work/Bot_Claude/Bot_Claude/modules/finmon/formatters.py")
formatters = importlib.util.module_from_spec(spec)
sys.modules['modules.finmon.formatters'] = formatters
spec.loader.exec_module(formatters)

print("=" * 70)
print("📊 FINMON MODULE - REPORT DEMONSTRATIONS")
print("=" * 70)

# 1. Shift Report Example
print("\n" + "=" * 70)
print("1️⃣  SHIFT REPORT EXAMPLE")
print("=" * 70)

shift_data = {
    'club_id': 1,
    'shift_time': 'morning',
    'shift_date': date(2025, 10, 20),
    'fact_cash': 2640.0,
    'fact_card': 5547.0,
    'qr': 1680.0,
    'card2': 0.0,
    'safe_cash_end': 927.0,
    'box_cash_end': 5124.0,
    'goods_cash': 1000.0,
    'compensations': 650.0,
    'salary_payouts': 3000.0,
    'other_expenses': 0.0,
    'joysticks_total': 153,
    'joysticks_in_repair': 3,
    'joysticks_need_repair': 3,
    'games_count': 31,
    'toilet_paper': True,
    'paper_towels': False,
    'notes': 'Новая касса не работает'
}

report = formatters.format_shift_report(shift_data, "Рио офиц")
print(report)

# 2. Balance Report Example
print("\n" + "=" * 70)
print("2️⃣  BALANCE REPORT EXAMPLE")
print("=" * 70)

balances = [
    {'club_name': 'Рио', 'cash_type': 'official', 'balance': 15234.50},
    {'club_name': 'Рио', 'cash_type': 'box', 'balance': 8456.00},
    {'club_name': 'Мичуринская', 'cash_type': 'official', 'balance': 12890.75},
    {'club_name': 'Мичуринская', 'cash_type': 'box', 'balance': 5432.25},
]

balance_report = formatters.format_balance_report(balances)
print(balance_report)

# 3. Shifts List Example
print("\n" + "=" * 70)
print("3️⃣  RECENT SHIFTS LIST EXAMPLE")
print("=" * 70)

def mock_get_club_name(club_id):
    names = {1: "Рио офиц", 2: "Рио коробка", 3: "Мичуринская офиц", 4: "Мичуринская коробка"}
    return names.get(club_id, "Unknown")

shifts = [
    {
        'club_id': 1,
        'shift_time': 'evening',
        'shift_date': '2025-10-20',
        'admin_username': 'admin1',
        'fact_cash': 3200.0,
        'fact_card': 4500.0,
        'qr': 800.0,
        'card2': 0.0,
        'compensations': 500.0,
        'salary_payouts': 2000.0,
        'other_expenses': 100.0
    },
    {
        'club_id': 1,
        'shift_time': 'morning',
        'shift_date': '2025-10-20',
        'admin_username': 'admin2',
        'fact_cash': 2640.0,
        'fact_card': 5547.0,
        'qr': 1680.0,
        'card2': 0.0,
        'compensations': 650.0,
        'salary_payouts': 3000.0,
        'other_expenses': 0.0
    },
    {
        'club_id': 3,
        'shift_time': 'evening',
        'shift_date': '2025-10-19',
        'admin_username': 'admin3',
        'fact_cash': 2100.0,
        'fact_card': 3800.0,
        'qr': 600.0,
        'card2': 0.0,
        'compensations': 300.0,
        'salary_payouts': 1500.0,
        'other_expenses': 50.0
    }
]

shifts_report = formatters.format_shifts_list(shifts, mock_get_club_name)
print(shifts_report)

# 4. Summary Report Example
print("\n" + "=" * 70)
print("4️⃣  FINANCIAL SUMMARY EXAMPLE")
print("=" * 70)

summary_data = {
    'clubs': {
        'Рио офиц': {
            'shift_count': 2,
            'total_cash': 5840.0,
            'total_card': 10047.0,
            'total_qr': 2480.0,
            'total_card2': 0.0,
            'total_compensations': 1150.0,
            'total_salary': 5000.0,
            'total_other_expenses': 100.0
        },
        'Мичуринская офиц': {
            'shift_count': 1,
            'total_cash': 2100.0,
            'total_card': 3800.0,
            'total_qr': 600.0,
            'total_card2': 0.0,
            'total_compensations': 300.0,
            'total_salary': 1500.0,
            'total_other_expenses': 50.0
        }
    },
    'total': {
        'shift_count': 3,
        'total_cash': 7940.0,
        'total_card': 13847.0,
        'total_qr': 3080.0,
        'total_card2': 0.0,
        'total_compensations': 1450.0,
        'total_salary': 6500.0,
        'total_other_expenses': 150.0
    }
}

summary_report = formatters.format_summary(summary_data, "за последние 7 дней")
print(summary_report)

# Summary
print("\n" + "=" * 70)
print("✅ DEMO COMPLETE")
print("=" * 70)
print("\n📌 Key Features Demonstrated:")
print("   • Beautiful emoji-rich formatting")
print("   • Clear financial breakdown")
print("   • Multiple report types")
print("   • Easy-to-read structure")
print("\n🚀 The FinMon module is ready for production use!")
print("=" * 70)
