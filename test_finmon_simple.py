#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test FinMon Simple Module
"""

import os
import sys
import tempfile
import json
import csv
from datetime import date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finmon_simple import FinMonSimple


def test_initialization():
    """Test FinMon Simple initialization"""
    print("Testing initialization...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        
        # Check files were created
        assert os.path.exists(balances_file), "Balances file not created"
        assert os.path.exists(log_file), "Log file not created"
        
        # Check initial balances
        balances = finmon.get_balances()
        assert "Рио" in balances, "Rio not in balances"
        assert "Север" in balances, "Sever not in balances"
        assert balances["Рио"]["official"] == 0, "Initial balance should be 0"
        assert balances["Рио"]["box"] == 0, "Initial box should be 0"
        
        print("✅ Initialization test passed")


def test_parse_number():
    """Test number parsing"""
    print("Testing number parsing...")
    
    finmon = FinMonSimple("/tmp/test_bal.json", "/tmp/test_log.csv")
    
    assert finmon.parse_number("3 440") == 3440.0, "Failed to parse '3 440'"
    assert finmon.parse_number("12 345") == 12345.0, "Failed to parse '12 345'"
    assert finmon.parse_number("0") == 0.0, "Failed to parse '0'"
    assert finmon.parse_number("не работает") == 0.0, "Failed to parse 'не работает'"
    assert finmon.parse_number("5,000") == 5000.0, "Failed to parse '5,000'"
    
    print("✅ Number parsing test passed")


def test_parse_shift_paste():
    """Test shift paste parsing"""
    print("Testing shift paste parsing...")
    
    finmon = FinMonSimple("/tmp/test_bal.json", "/tmp/test_log.csv")
    
    # Test with club auto-detected
    paste_text = """Факт нал: 3 440
Факт карта: 12 345
QR: 0
Карта2: не работает
Сейф: 5 000
Коробка: 2 000"""
    
    data = finmon.parse_shift_paste(paste_text, club="Рио")
    
    assert data is not None, "Failed to parse shift data"
    assert data['club'] == "Рио", "Wrong club"
    assert data['fact_cash'] == 3440.0, f"Wrong fact_cash: {data['fact_cash']}"
    assert data['fact_card'] == 12345.0, f"Wrong fact_card: {data['fact_card']}"
    assert data['qr'] == 0.0, f"Wrong qr: {data['qr']}"
    assert data['card2'] == 0.0, f"Wrong card2: {data['card2']}"
    assert data['safe_cash_end'] == 5000.0, f"Wrong safe_cash_end: {data['safe_cash_end']}"
    assert data['box_cash_end'] == 2000.0, f"Wrong box_cash_end: {data['box_cash_end']}"
    
    print("✅ Shift paste parsing test passed")
    
    # Test with club in first line
    paste_text2 = """Север
Факт нал: 1 000
Факт карта: 5 000
QR: 500
Карта2: 0
Сейф: 3 000
Коробка: 1 500"""
    
    data2 = finmon.parse_shift_paste(paste_text2)
    
    assert data2 is not None, "Failed to parse shift data with club in text"
    assert data2['club'] == "Север", "Wrong club from text"
    assert data2['fact_cash'] == 1000.0, f"Wrong fact_cash: {data2['fact_cash']}"
    
    print("✅ Shift paste parsing with club in text test passed")


def test_submit_shift():
    """Test shift submission"""
    print("Testing shift submission...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        
        # Submit a shift
        data = {
            'club': 'Рио',
            'fact_cash': 3440.0,
            'fact_card': 12345.0,
            'qr': 0.0,
            'card2': 0.0,
            'safe_cash_end': 5000.0,
            'box_cash_end': 2000.0
        }
        
        success = finmon.submit_shift(
            data,
            admin_tg_id=123456789,
            admin_username="testuser",
            shift_date=date(2024, 10, 26),
            shift_time="evening",
            duty_name="Иван Иванов"
        )
        
        assert success, "Shift submission failed"
        
        # Check balances updated
        balances = finmon.get_balances()
        assert balances["Рио"]["official"] == 5000.0, "Official balance not updated"
        assert balances["Рио"]["box"] == 2000.0, "Box balance not updated"
        
        # Check CSV log
        movements = finmon.get_recent_movements("Рио", limit=1)
        assert len(movements) == 1, "Movement not logged"
        assert movements[0]['club'] == 'Рио', "Wrong club in log"
        assert movements[0]['duty_name'] == 'Иван Иванов', "Duty name not logged"
        assert float(movements[0]['delta_official']) == 5000.0, "Wrong delta in log"
        
        print("✅ Shift submission test passed")


def test_club_mapping():
    """Test chat to club mapping"""
    print("Testing club mapping...")
    
    finmon = FinMonSimple("/tmp/test_bal.json", "/tmp/test_log.csv")
    
    assert finmon.get_club_from_chat(5329834944) == "Рио", "Wrong mapping for Rio"
    assert finmon.get_club_from_chat(5992731922) == "Север", "Wrong mapping for Sever"
    assert finmon.get_club_from_chat(99999999) is None, "Should return None for unmapped chat"
    
    print("✅ Club mapping test passed")


def test_format_functions():
    """Test formatting functions"""
    print("Testing formatting functions...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        
        # Test shift summary
        data = {
            'club': 'Рио',
            'fact_cash': 3440.0,
            'fact_card': 12345.0,
            'qr': 0.0,
            'card2': 0.0,
            'safe_cash_end': 5000.0,
            'box_cash_end': 2000.0
        }
        
        summary = finmon.format_shift_summary(data, "Иван Иванов")
        assert "Рио" in summary, "Club not in summary"
        assert "Иван Иванов" in summary, "Duty name not in summary"
        assert "3,440" in summary or "3 440" in summary, "Cash not in summary"
        
        # Test balances format
        balances_text = finmon.format_balances()
        assert "Рио" in balances_text, "Rio not in balances text"
        assert "Север" in balances_text, "Sever not in balances text"
        
        print("✅ Formatting functions test passed")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Testing FinMon Simple Module")
    print("=" * 60 + "\n")
    
    try:
        test_initialization()
        test_parse_number()
        test_parse_shift_paste()
        test_submit_shift()
        test_club_mapping()
        test_format_functions()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
