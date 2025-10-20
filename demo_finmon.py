#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Module Usage Demo
Demonstrates how to use the Financial Monitoring module
"""

import os
from datetime import date
from modules.finmon.db import FinMonDB
from modules.finmon.models import Shift
from modules.finmon.wizard import FinMonWizard

print("=" * 60)
print("FinMon Module - Usage Demo")
print("=" * 60)

# Initialize database
db_path = "demo_finmon.db"
if os.path.exists(db_path):
    os.remove(db_path)

print("\n1. Initializing FinMon database...")
db = FinMonDB(db_path)
print("✅ Database initialized with 4 clubs")

# Show available clubs
print("\n2. Available clubs:")
clubs = db.get_clubs()
for club in clubs:
    display_name = db.get_club_display_name(club['id'])
    print(f"   ID {club['id']}: {display_name}")

# Create example shifts for different clubs
print("\n3. Creating example shifts...")

shifts_data = [
    {
        "club_id": 1,  # Рио official
        "shift_time": "morning",
        "admin": "Алексей",
        "fact_cash": 2640.0,
        "fact_card": 5547.0,
        "qr": 1680.0,
        "joysticks_total": 153,
        "notes": "Все ОК, сломан один стул"
    },
    {
        "club_id": 3,  # Мичуринская official  
        "shift_time": "evening",
        "admin": "Мария",
        "fact_cash": 3200.0,
        "fact_card": 4800.0,
        "qr": 2100.0,
        "joysticks_total": 147,
        "notes": "Замена картриджа в принтере"
    },
    {
        "club_id": 2,  # Рио box
        "shift_time": "morning",
        "admin": "Дмитрий",
        "fact_cash": 1800.0,
        "fact_card": 3200.0,
        "qr": 900.0,
        "joysticks_total": 80,
        "notes": None
    }
]

for i, shift_info in enumerate(shifts_data, 1):
    shift = Shift(
        club_id=shift_info["club_id"],
        shift_date=date.today(),
        shift_time=shift_info["shift_time"],
        admin_tg_id=100000 + i,
        admin_username=shift_info["admin"],
        fact_cash=shift_info["fact_cash"],
        fact_card=shift_info["fact_card"],
        qr=shift_info["qr"],
        card2=0.0,
        safe_cash_end=shift_info["fact_cash"] * 0.3,
        box_cash_end=shift_info["fact_cash"] * 0.7,
        goods_cash=500.0,
        compensations=0.0,
        salary_payouts=0.0,
        other_expenses=0.0,
        joysticks_total=shift_info["joysticks_total"],
        joysticks_in_repair=3,
        joysticks_need_repair=2,
        games_count=30,
        toilet_paper=True,
        paper_towels=True,
        notes=shift_info["notes"]
    )
    
    shift_id = db.save_shift(shift)
    club_name = db.get_club_display_name(shift_info["club_id"])
    print(f"   ✅ Shift #{shift_id}: {club_name}, {shift_info['admin']}")

# Show recent shifts
print("\n4. Recent shifts (owner view - all shifts):")
owner_shifts = db.get_shifts(limit=10, admin_id=999999, owner_ids=[999999])
for shift in owner_shifts:
    club_name = db.get_club_display_name(shift['club_id'])
    time_label = "Утро" if shift['shift_time'] == 'morning' else "Вечер"
    total_revenue = shift['fact_cash'] + shift['fact_card'] + shift['qr']
    print(f"   [{club_name}] {time_label}")
    print(f"      Админ: {shift['admin_username']}")
    print(f"      Выручка: {total_revenue:,.0f} ₽ (нал: {shift['fact_cash']:,.0f}, б/н: {shift['fact_card']:,.0f}, QR: {shift['qr']:,.0f})")
    if shift['notes']:
        print(f"      Примечание: {shift['notes']}")

# Show admin-specific shifts
print("\n5. Shifts for admin 'Алексей' (admin view - only own shifts):")
admin_shifts = db.get_shifts(limit=10, admin_id=100001, owner_ids=[])
for shift in admin_shifts:
    club_name = db.get_club_display_name(shift['club_id'])
    time_label = "Утро" if shift['shift_time'] == 'morning' else "Вечер"
    print(f"   [{club_name}] {time_label} - {shift['fact_cash']:,.0f} ₽ наличными")

# Show balances
print("\n6. Current cash balances:")
balances = db.get_balances()
for balance in balances:
    club_name = db.get_club_display_name(balance['club_id'])
    print(f"   {club_name}: {balance['balance']:,.2f} ₽")

# Demonstrate shift summary formatting
print("\n7. Example shift summary:")
print("-" * 60)

# Create dummy sheets object for wizard
from modules.finmon.sheets import GoogleSheetsSync
sheets = GoogleSheetsSync.__new__(GoogleSheetsSync)
sheets.credentials_path = None
sheets.sheet_name = "Demo"
sheets.client = None
sheets.spreadsheet = None

wizard = FinMonWizard(db, sheets, [999999])

shift_data = {
    'club_id': 1,
    'shift_time': 'morning',
    'shift_date': date.today(),
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
    'notes': 'Все ОК'
}

summary = wizard._format_shift_summary(shift_data)
print(summary)
print("-" * 60)

print("\n" + "=" * 60)
print("Demo completed!")
print("=" * 60)

print("\n📋 How to use in Telegram bot:")
print("   /shift     - Start shift submission wizard")
print("   /balances  - Show current cash balances")
print("   /shifts    - Show last 10 shifts")

print("\n🔧 Configuration (.env file):")
print("   FINMON_DB_PATH=knowledge.db")
print("   FINMON_SHEET_NAME=ClubFinance")
print("   GOOGLE_SA_JSON=/path/to/service-account.json")
print("   OWNER_TG_IDS=123456789,987654321")

print("\n📊 Database tables:")
print("   - finmon_clubs (4 records)")
print("   - finmon_shifts (shift records)")
print("   - finmon_cashes (cash balances)")

# Cleanup
os.remove(db_path)
print("\n✅ Demo database cleaned up")
