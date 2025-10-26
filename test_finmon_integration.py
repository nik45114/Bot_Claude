#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration Test for FinMon Simple
Tests the complete flow including shift wizard
"""

import os
import sys
import tempfile
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finmon_simple import FinMonSimple
from modules.finmon_schedule import FinMonSchedule
from modules.finmon_shift_wizard import ShiftWizard


def test_shift_wizard_integration():
    """Test the complete shift submission flow"""
    print("Testing shift wizard integration...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        # Initialize components
        finmon = FinMonSimple(balances_file, log_file)
        schedule = None  # No Google Sheets for this test
        owner_ids = [123456789]
        
        wizard = ShiftWizard(finmon, schedule, owner_ids)
        
        # Test owner check
        assert wizard.is_owner(123456789), "Owner check failed"
        assert not wizard.is_owner(999999999), "Non-owner should not be owner"
        
        print("✅ Wizard initialization and owner check passed")
        
        # Simulate receiving shift data
        paste_text = """Факт нал: 3 440
Факт карта: 12 345
QR: 0
Карта2: не работает
Сейф: 5 000
Коробка: 2 000"""
        
        # Parse data (simulating what wizard does)
        data = finmon.parse_shift_paste(paste_text, club="Рио")
        
        assert data is not None, "Failed to parse shift data"
        print("✅ Shift data parsed successfully")
        
        # Submit shift (simulating confirmation)
        success = finmon.submit_shift(
            data,
            admin_tg_id=123456789,
            admin_username="testuser",
            shift_date=date.today(),
            shift_time="evening",
            duty_name=""
        )
        
        assert success, "Shift submission failed"
        print("✅ Shift submitted successfully")
        
        # Verify balances updated
        balances = finmon.get_balances()
        assert balances["Рио"]["official"] == 5000.0, "Balances not updated correctly"
        
        print("✅ Balances updated correctly")
        
        # Verify movements logged
        movements = finmon.get_recent_movements("Рио", limit=1)
        assert len(movements) == 1, "Movement not logged"
        
        print("✅ Movement logged correctly")
        
        # Test formatting functions
        summary = finmon.format_shift_summary(data, "")
        assert "Рио" in summary, "Club not in summary"
        assert "3,440" in summary or "3 440" in summary, "Numbers not formatted"
        
        balances_text = finmon.format_balances()
        assert "5,000" in balances_text or "5 000" in balances_text, "Balances not formatted"
        
        movements_text = finmon.format_movements("Рио", limit=5)
        assert "Рио" in movements_text, "Club not in movements"
        
        print("✅ Formatting functions work correctly")


def test_chat_club_mapping():
    """Test automatic club detection from chat ID"""
    print("Testing chat-club mapping...")
    
    finmon = FinMonSimple("/tmp/test_bal.json", "/tmp/test_log.csv")
    
    # Test hardcoded mappings
    assert finmon.get_club_from_chat(5329834944) == "Рио", "Rio mapping incorrect"
    assert finmon.get_club_from_chat(5992731922) == "Север", "Sever mapping incorrect"
    assert finmon.get_club_from_chat(99999999) is None, "Unknown chat should return None"
    
    print("✅ Chat-club mapping works correctly")


def test_time_detection():
    """Test shift time window detection"""
    print("Testing time detection...")
    
    from modules.finmon_shift_wizard import get_current_shift_window, now_msk
    import pytz
    
    # Get current time in MSK
    current = now_msk()
    print(f"  Current MSK time: {current.strftime('%H:%M')}")
    
    # Get detected shift window
    window = get_current_shift_window()
    
    if window:
        print(f"  Detected shift: {window['shift_time']} ({window['reason']})")
        print(f"  Shift date: {window['shift_date']}")
    else:
        print("  No shift window detected (outside windows)")
    
    # This is expected behavior - window may or may not be detected depending on time
    print("✅ Time detection function runs without errors")


def test_owner_only_restrictions():
    """Test that owner IDs are properly enforced"""
    print("Testing owner-only restrictions...")
    
    finmon = FinMonSimple("/tmp/test_bal.json", "/tmp/test_log.csv")
    schedule = None
    owner_ids = [111111111, 222222222]  # Multiple owners
    
    wizard = ShiftWizard(finmon, schedule, owner_ids)
    
    # Test multiple owner IDs
    assert wizard.is_owner(111111111), "First owner not recognized"
    assert wizard.is_owner(222222222), "Second owner not recognized"
    assert not wizard.is_owner(333333333), "Non-owner incorrectly recognized"
    
    print("✅ Multiple owner IDs work correctly")


def test_shift_variations():
    """Test various shift paste formats"""
    print("Testing shift paste variations...")
    
    finmon = FinMonSimple("/tmp/test_bal.json", "/tmp/test_log.csv")
    
    # Test 1: Standard format
    paste1 = """Факт нал: 3 440
Факт карта: 12 345
QR: 0
Карта2: 0
Сейф: 5 000
Коробка: 2 000"""
    
    data1 = finmon.parse_shift_paste(paste1, "Рио")
    assert data1 is not None, "Standard format failed"
    print("  ✓ Standard format")
    
    # Test 2: With club name in text
    paste2 = """Север
Факт нал: 1000
Факт карта: 2000
QR: не работает
Карта2: нет
Сейф: 3000
Коробка: 1000"""
    
    data2 = finmon.parse_shift_paste(paste2)
    assert data2 is not None, "Club in text format failed"
    assert data2['club'] == "Север", "Club not extracted from text"
    print("  ✓ Club name in text")
    
    # Test 3: Different number formats
    paste3 = """Факт нал: 3,440
Факт карта: 12 345
QR: 0
Карта2: не работает
Сейф: 5 000
Коробка: 2,000"""
    
    data3 = finmon.parse_shift_paste(paste3, "Рио")
    assert data3 is not None, "Mixed number format failed"
    assert data3['fact_cash'] == 3440.0, "Comma parsing failed"
    print("  ✓ Mixed number formats")
    
    print("✅ All shift paste variations work correctly")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("FinMon Simple Integration Tests")
    print("=" * 60 + "\n")
    
    try:
        test_shift_wizard_integration()
        test_chat_club_mapping()
        test_time_detection()
        test_owner_only_restrictions()
        test_shift_variations()
        
        print("\n" + "=" * 60)
        print("✅ All integration tests passed!")
        print("=" * 60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
