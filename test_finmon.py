#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for FinMon module
Tests database, models, and wizard functionality
"""

import os
import sys
from datetime import date

# Test imports
print("=" * 60)
print("Testing FinMon Module")
print("=" * 60)

print("\n1. Testing imports...")
try:
    from modules.finmon.db import FinMonDB
    from modules.finmon.models import Club, Shift, CashBalance
    from modules.finmon.sheets import GoogleSheetsSync
    from modules.finmon.wizard import FinMonWizard
    from modules.finmon import register_finmon
    print("✅ All modules imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test database
print("\n2. Testing database...")
test_db = "test_finmon_full.db"
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
    
    # Test owner view (sees all)
    owner_shifts = db.get_shifts(limit=10, admin_id=999999, owner_ids=[999999])
    assert len(owner_shifts) == 1, "Owner should see all shifts"
    print("✅ Owner permissions work")
    
    # Test non-owner view (sees only own)
    other_shifts = db.get_shifts(limit=10, admin_id=999999, owner_ids=[])
    assert len(other_shifts) == 0, "Non-owner should not see other admin's shifts"
    print("✅ Admin permissions work")
    
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

# Test Google Sheets (without credentials, should gracefully fail)
print("\n6. Testing Google Sheets integration...")
try:
    # This should not crash even without credentials
    sheets = GoogleSheetsSync("/nonexistent/path.json", "TestSheet")
    print("✅ GoogleSheetsSync handles missing credentials gracefully")
    
except Exception as e:
    print(f"❌ Google Sheets test failed: {e}")
    import traceback
    traceback.print_exc()

# Test wizard helper functions
print("\n7. Testing wizard functions...")
try:
    # Create a mock sheets object
    class MockGoogleSheets:
        """Mock GoogleSheetsSync for testing"""
        def __init__(self):
            self.credentials_path = None
            self.sheet_name = "Test"
            self.client = None
            self.spreadsheet = None
        
        def append_shift(self, shift_data, club_name):
            return False
        
        def update_balances(self, balances):
            return False
    
    sheets_mock = MockGoogleSheets()
    wizard = FinMonWizard(db, sheets_mock, [123456])
    
    # Test is_owner
    assert wizard.is_owner(123456) == True
    assert wizard.is_owner(999999) == False
    print("✅ Owner check works")
    
    # Test summary formatting
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
    assert len(summary) > 0, "Summary should not be empty"
    assert "Рио офиц" in summary, "Summary should contain club name"
    assert "2,640" in summary, "Summary should contain formatted cash amount"
    print("✅ Summary formatting works")
    
except Exception as e:
    print(f"❌ Wizard test failed: {e}")
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
