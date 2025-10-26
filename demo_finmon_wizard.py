#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo: FinMon Button-Based Shift Wizard
Demonstrates the new button-based wizard flow
"""

import os
import sys
import tempfile
from datetime import date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finmon_simple import FinMonSimple


def demo_button_wizard():
    """Demonstrate the button-based wizard flow"""
    print("\n" + "=" * 70)
    print("FinMon Button-Based Shift Wizard Demo")
    print("=" * 70 + "\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "demo_balances.json")
        log_file = os.path.join(tmpdir, "demo_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        
        print("📋 Wizard Flow:")
        print("-" * 70)
        
        # Step 1: Club selection
        print("\n1️⃣ STEP 1: Club Selection")
        print("   User opens /shift in chat")
        print("   - If chat ID is 5329834944 → Auto-detected: Рио ✓")
        print("   - If chat ID is 5992731922 → Auto-detected: Север ✓")
        print("   - Otherwise → Shows buttons: [🏢 Рио] [🏢 Север]")
        
        club = "Рио"
        print(f"\n   ✅ Selected club: {club}")
        
        # Step 2: Shift time selection
        print("\n2️⃣ STEP 2: Shift Time Selection")
        print("   Shows buttons:")
        print("   - [☀️ Утро] (ночная смена)")
        print("   - [🌙 Вечер] (дневная смена)")
        
        shift_time = "evening"
        print(f"\n   ✅ Selected: 🌙 Вечер (дневная смена)")
        
        # Step 3: Show previous balances
        print("\n3️⃣ STEP 3: Previous Balances Display")
        prev_balances = finmon.get_club_balances(club)
        prev_official = prev_balances.get('official', 0) if prev_balances else 0
        prev_box = prev_balances.get('box', 0) if prev_balances else 0
        
        print(f"   📊 Прошлый раз:")
        print(f"      • Основная: {prev_official:,.0f} ₽")
        print(f"      • Коробка: {prev_box:,.0f} ₽")
        
        # Step 4: Data entry
        print("\n4️⃣ STEP 4: Data Entry (Button-Prompted)")
        print("   Each field prompts:")
        print("   - [Ввести вручную] button")
        print("   - User types number")
        print("   - Moves to next field automatically")
        
        data = {
            'club': club,
            'fact_cash': 3440.0,
            'fact_card': 12345.0,
            'qr': 500.0,
            'card2': 0.0,
            'safe_cash_end': 5500.0,
            'box_cash_end': 2300.0
        }
        
        print("\n   Entered values:")
        print(f"   💰 Выручка:")
        print(f"      • Наличка факт: {data['fact_cash']:,.0f} ₽")
        print(f"      • Карта факт: {data['fact_card']:,.0f} ₽")
        print(f"      • QR: {data['qr']:,.0f} ₽")
        print(f"      • Новая касса: {data['card2']:,.0f} ₽")
        print(f"   🔐 Остатки:")
        print(f"      • Сейф (офиц): {data['safe_cash_end']:,.0f} ₽")
        print(f"      • Коробка: {data['box_cash_end']:,.0f} ₽")
        
        # Step 5: Summary with deltas
        print("\n5️⃣ STEP 5: Summary with Deltas")
        
        new_official = data['safe_cash_end']
        new_box = data['box_cash_end']
        delta_official = new_official - prev_official
        delta_box = new_box - prev_box
        
        print("   📊 Сводка смены:")
        print(f"   🏢 Клуб: {club}")
        print(f"   ⏰ Время: 🌙 Вечер (дневная смена)")
        print()
        print("   💰 Выручка:")
        print(f"      • Наличка факт: {data['fact_cash']:,.0f} ₽")
        print(f"      • Карта факт: {data['fact_card']:,.0f} ₽")
        print(f"      • QR: {data['qr']:,.0f} ₽")
        print(f"      • Новая касса: {data['card2']:,.0f} ₽")
        print()
        print("   🔐 Остатки:")
        print(f"      • Сейф (офиц): {new_official:,.0f} ₽")
        print(f"      • Коробка: {new_box:,.0f} ₽")
        print()
        print("   📈 Прошлый раз:")
        print(f"      • Основная: {prev_official:,.0f} ₽")
        print(f"      • Коробка: {prev_box:,.0f} ₽")
        print()
        print("   📊 Движение:")
        print(f"      • Основная: {delta_official:+,.0f} ₽")
        print(f"      • Коробка: {delta_box:+,.0f} ₽")
        print()
        print("   Buttons: [✅ Подтвердить] [✏️ Изменить] [❌ Отменить]")
        
        # Step 6: Confirmation
        print("\n6️⃣ STEP 6: Confirmation")
        print("   User clicks [✅ Подтвердить]")
        
        # Submit shift
        success = finmon.submit_shift(
            data,
            admin_tg_id=123456789,
            admin_username="demo_user",
            shift_date=date.today(),
            shift_time=shift_time,
            duty_name="Иван Иванов"
        )
        
        if success:
            print("\n   ✅ Смена успешно сдана!")
            
            # Show updated balances
            balances = finmon.get_club_balances(club)
            print(f"\n   💰 Новые остатки:")
            print(f"      • Офиц (сейф): {balances['official']:,.0f} ₽")
            print(f"      • Коробка: {balances['box']:,.0f} ₽")
            
            # Show CSV log entry
            movements = finmon.get_recent_movements(club, limit=1)
            if movements:
                mov = movements[0]
                print(f"\n   📝 Запись в CSV:")
                print(f"      • Клуб: {mov['club']}")
                print(f"      • Дата смены: {mov['shift_date']}")
                print(f"      • Время: {mov['shift_time']}")
                print(f"      • Дежурный: {mov['duty_name']}")
                print(f"      • Δ Офиц: {float(mov['delta_official']):+,.0f} ₽")
                print(f"      • Δ Коробка: {float(mov['delta_box']):+,.0f} ₽")
        else:
            print("\n   ❌ Ошибка при сохранении")
        
        print("\n" + "=" * 70)
        print("✅ Demo completed successfully!")
        print("=" * 70 + "\n")


def show_key_features():
    """Show key features of the new wizard"""
    print("\n" + "=" * 70)
    print("Key Features of Button-Based Wizard")
    print("=" * 70 + "\n")
    
    features = [
        "✅ No text parsing required - all input via buttons and prompts",
        "✅ Step-by-step guided flow prevents errors",
        "✅ Previous balances shown before data entry",
        "✅ Automatic delta calculation (new - previous)",
        "✅ Club auto-detection from chat ID",
        "✅ Clear summary with all data before confirmation",
        "✅ Edit option to restart if needed",
        "✅ CSV logging includes deltas automatically",
        "✅ Works in club chats (Рио: 5329834944, Север: 5992731922)",
        "✅ Clean UX with emoji and Russian text"
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print("\n" + "=" * 70 + "\n")


def show_commands():
    """Show available commands"""
    print("\n" + "=" * 70)
    print("Available Commands")
    print("=" * 70 + "\n")
    
    commands = [
        ("/shift", "Сдать смену (кнопочный мастер)"),
        ("/balances", "Текущие остатки по всем клубам"),
        ("/movements", "Последние движения"),
        ("/cancel", "Отменить текущую сдачу смены")
    ]
    
    for cmd, desc in commands:
        print(f"  {cmd:15} - {desc}")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == '__main__':
    show_key_features()
    show_commands()
    demo_button_wizard()
