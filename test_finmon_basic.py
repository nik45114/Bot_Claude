#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic test for FinMon module without telegram dependencies
Tests database operations and formatters
"""

import os
import sys
from datetime import date

# Test database and models
print("=" * 60)
print("Testing FinMon Module - Basic Functionality")
print("=" * 60)

print("\n1. Testing imports...")
try:
    # Add the project root to path
    sys.path.insert(0, '/home/runner/work/Bot_Claude/Bot_Claude')
    
    # Import directly from module files to avoid __init__.py which requires telegram
    import importlib.util
    
    # Create a fake parent package to allow relative imports
    import types
    finmon_package = types.ModuleType('modules.finmon')
    sys.modules['modules.finmon'] = finmon_package
    
    # Load models first
    spec = importlib.util.spec_from_file_location("modules.finmon.models", 
                                                   "/home/runner/work/Bot_Claude/Bot_Claude/modules/finmon/models.py",
                                                   submodule_search_locations=[])
    models_module = importlib.util.module_from_spec(spec)
    sys.modules['modules.finmon.models'] = models_module
    spec.loader.exec_module(models_module)
    Club = models_module.Club
    Shift = models_module.Shift
    CashBalance = models_module.CashBalance
    
    # Load db
    spec = importlib.util.spec_from_file_location("modules.finmon.db", 
                                                   "/home/runner/work/Bot_Claude/Bot_Claude/modules/finmon/db.py",
                                                   submodule_search_locations=[])
    db_module = importlib.util.module_from_spec(spec)
    sys.modules['modules.finmon.db'] = db_module
    spec.loader.exec_module(db_module)
    FinMonDB = db_module.FinMonDB
    
    # Load formatters
    spec = importlib.util.spec_from_file_location("modules.finmon.formatters", 
                                                   "/home/runner/work/Bot_Claude/Bot_Claude/modules/finmon/formatters.py",
                                                   submodule_search_locations=[])
    formatters = importlib.util.module_from_spec(spec)
    sys.modules['modules.finmon.formatters'] = formatters
    spec.loader.exec_module(formatters)
    
    print("✅ Core modules imported successfully")
    print("   (Bypassing __init__.py which requires telegram)")
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test database
print("\n2. Testing database...")
test_db = "test_finmon_basic.db"
if os.path.exists(test_db):
    os.remove(test_db)

try:
    db = FinMonDB(test_db)
    
    # Test clubs
    clubs = db.get_clubs()
    assert len(clubs) == 4, f"Expected 4 clubs, got {len(clubs)}"
    print(f"✅ Loaded {len(clubs)} clubs")
    
    # Test balances
    balances = db.get_balances()
    assert len(balances) == 4, f"Expected 4 balances, got {len(balances)}"
    print(f"✅ Loaded {len(balances)} balances")
    
    # Test club display names
    for club in clubs:
        name = db.get_club_display_name(club['id'])
        assert name, "Club name should not be empty"
        print(f"   Club {club['id']}: {name}")
    print("✅ Club display names work")
    
except Exception as e:
    print(f"❌ Database test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test models
print("\n3. Testing Pydantic models...")
try:
    # Club model
    club = Club(name="Test", type="official")
    assert club.name == "Test"
    assert club.type == "official"
    print("✅ Club model works")
    
    # Shift model
    shift = Shift(
        club_id=1,
        shift_date=date.today(),
        shift_time="morning",
        admin_tg_id=12345,
        fact_cash=1000.0,
        joysticks_total=100
    )
    assert shift.club_id == 1
    assert shift.fact_cash == 1000.0
    print("✅ Shift model works")
    
    # CashBalance model
    balance = CashBalance(club_id=1, cash_type="official", balance=500.0)
    assert balance.balance == 500.0
    print("✅ CashBalance model works")
    
except Exception as e:
    print(f"❌ Model test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test shift operations
print("\n4. Testing shift operations...")
try:
    # Save a shift
    shift = Shift(
        club_id=1,
        shift_date=date.today(),
        shift_time="evening",
        admin_tg_id=123456,
        admin_username="testuser",
        fact_cash=2500.0,
        fact_card=3000.0,
        qr=500.0,
        card2=100.0,
        safe_cash_end=1000.0,
        box_cash_end=2000.0,
        goods_cash=500.0,
        compensations=200.0,
        salary_payouts=1000.0,
        other_expenses=50.0,
        joysticks_total=150,
        joysticks_in_repair=5,
        joysticks_need_repair=2,
        games_count=30,
        toilet_paper=True,
        paper_towels=False,
        notes="Test shift"
    )
    
    shift_id = db.save_shift(shift)
    assert shift_id is not None, "Shift ID should not be None"
    print(f"✅ Shift saved with ID: {shift_id}")
    
    # Retrieve shifts
    shifts = db.get_shifts(limit=10, admin_id=123456, owner_ids=[])
    assert len(shifts) == 1, f"Expected 1 shift, got {len(shifts)}"
    print(f"✅ Retrieved {len(shifts)} shift(s)")
    
    # Verify shift data
    s = shifts[0]
    assert s['fact_cash'] == 2500.0
    assert s['joysticks_total'] == 150
    assert s['notes'] == "Test shift"
    print("✅ Shift data verified")
    
except Exception as e:
    print(f"❌ Shift operations test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test balance operations
print("\n5. Testing balance operations...")
try:
    # Update balance
    success = db.update_cash_balance(1, "official", 100.0)
    assert success, "Balance update should succeed"
    print("✅ Balance updated")
    
    # Verify balance
    balances = db.get_balances()
    rio_official = [b for b in balances if b['club_id'] == 1 and b['cash_type'] == 'official'][0]
    assert rio_official['balance'] == 100.0, f"Expected 100.0, got {rio_official['balance']}"
    print("✅ Balance verified")
    
except Exception as e:
    print(f"❌ Balance operations test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test formatters
print("\n6. Testing formatters...")
try:
    # Test shift report formatting
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
        'notes': 'Новая касса не работает'
    }
    
    report = formatters.format_shift_report(shift_data, "Рио офиц")
    assert len(report) > 0, "Report should not be empty"
    assert "Рио офиц" in report, "Report should contain club name"
    assert "2,640" in report, "Report should contain formatted cash amount"
    print("✅ Shift report formatting works")
    print("\nSample shift report:")
    print("-" * 60)
    print(report)
    print("-" * 60)
    
    # Test balance report formatting
    balance_report = formatters.format_balance_report(balances)
    assert len(balance_report) > 0, "Balance report should not be empty"
    print("✅ Balance report formatting works")
    
    # Test shifts list formatting
    shifts_report = formatters.format_shifts_list(shifts, db.get_club_display_name)
    assert len(shifts_report) > 0, "Shifts report should not be empty"
    print("✅ Shifts list formatting works")
    
except Exception as e:
    print(f"❌ Formatters test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test summary
print("\n7. Testing summary operations...")
try:
    # Get summary
    summary = db.get_summary('all')
    assert 'clubs' in summary, "Summary should have 'clubs' key"
    assert 'total' in summary, "Summary should have 'total' key"
    print(f"✅ Summary retrieved")
    
    # Format summary
    summary_report = formatters.format_summary(summary, "за всё время")
    assert len(summary_report) > 0, "Summary report should not be empty"
    print("✅ Summary formatting works")
    print("\nSample summary report:")
    print("-" * 60)
    print(summary_report)
    print("-" * 60)
    
except Exception as e:
    print(f"❌ Summary test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Cleanup
print("\n8. Cleaning up...")
try:
    os.remove(test_db)
    print("✅ Test database removed")
except:
    pass

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nFinMon module is ready to use!")
print("\nCommands:")
print("  /shift     - Start shift submission wizard")
print("  /balances  - Show current cash balances")
print("  /shifts    - Show last 10 shifts")
print("  /summary   - Show financial summary (owner only)")
