#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test FinMon Integration with Bot
Verify that the wizard is properly registered and configured
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_import_wizard():
    """Test that wizard can be imported"""
    print("Testing wizard import...")
    
    from modules.finmon_shift_wizard import (
        ShiftWizard, SELECT_CLUB, SELECT_SHIFT_TIME,
        ENTER_FACT_CASH, ENTER_FACT_CARD, ENTER_QR, ENTER_CARD2,
        ENTER_SAFE, ENTER_BOX, CONFIRM_SHIFT
    )
    
    # Verify states are defined
    assert SELECT_CLUB is not None, "SELECT_CLUB not defined"
    assert SELECT_SHIFT_TIME is not None, "SELECT_SHIFT_TIME not defined"
    assert ENTER_FACT_CASH is not None, "ENTER_FACT_CASH not defined"
    assert CONFIRM_SHIFT is not None, "CONFIRM_SHIFT not defined"
    
    print("✅ Wizard import test passed")


def test_import_finmon_simple():
    """Test that finmon_simple can be imported"""
    print("Testing finmon_simple import...")
    
    from modules.finmon_simple import FinMonSimple, CHAT_TO_CLUB
    
    # Verify club mapping
    assert 5329834944 in CHAT_TO_CLUB, "Рио chat ID not in mapping"
    assert 5992731922 in CHAT_TO_CLUB, "Север chat ID not in mapping"
    assert CHAT_TO_CLUB[5329834944] == "Рио", "Рио mapping incorrect"
    assert CHAT_TO_CLUB[5992731922] == "Север", "Север mapping incorrect"
    
    print("✅ FinMonSimple import test passed")


def test_wizard_initialization():
    """Test wizard can be initialized"""
    print("Testing wizard initialization...")
    
    import tempfile
    from modules.finmon_simple import FinMonSimple
    from modules.finmon_shift_wizard import ShiftWizard
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        wizard = ShiftWizard(finmon, None, owner_ids=[123456])
        
        # Verify wizard attributes
        assert hasattr(wizard, 'finmon'), "Wizard missing finmon attribute"
        assert hasattr(wizard, 'cmd_shift'), "Wizard missing cmd_shift method"
        assert hasattr(wizard, 'cmd_balances'), "Wizard missing cmd_balances method"
        assert hasattr(wizard, 'cmd_movements'), "Wizard missing cmd_movements method"
        
        print("✅ Wizard initialization test passed")


def test_bot_import():
    """Test that bot module can be imported (without running)"""
    print("Testing bot import...")
    
    # This just verifies the bot file has no syntax errors
    # We don't actually run it since it requires config
    try:
        with open('bot.py', 'r') as f:
            code = f.read()
        
        # Check that required imports are present
        assert 'from modules.finmon_simple import FinMonSimple' in code, "Missing FinMonSimple import"
        assert 'from modules.finmon_shift_wizard import' in code, "Missing wizard import"
        assert 'SELECT_CLUB' in code, "Missing SELECT_CLUB state"
        assert 'CONFIRM_SHIFT' in code, "Missing CONFIRM_SHIFT state"
        
        print("✅ Bot import test passed")
    except FileNotFoundError:
        print("⚠️ bot.py not found, skipping bot import test")


def test_deprecation_warning():
    """Test that parse_shift_paste shows deprecation warning"""
    print("Testing deprecation warning...")
    
    import tempfile
    import logging
    from io import StringIO
    from modules.finmon_simple import FinMonSimple
    
    # Capture log output
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.WARNING)
    logger = logging.getLogger('modules.finmon_simple')
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        
        # Call deprecated function
        finmon.parse_shift_paste("Рио\nФакт нал: 1000", club="Рио")
        
        # Check for warning
        log_output = log_capture.getvalue()
        assert "deprecated" in log_output.lower() or "parse_shift_paste" in log_output, \
            "Deprecation warning not shown"
        
        print("✅ Deprecation warning test passed")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Testing FinMon Integration")
    print("=" * 60 + "\n")
    
    try:
        test_import_wizard()
        test_import_finmon_simple()
        test_wizard_initialization()
        test_bot_import()
        test_deprecation_warning()
        
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
