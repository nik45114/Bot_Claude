#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test FinMon Button-Based Wizard
"""

import os
import sys
import tempfile
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finmon_simple import FinMonSimple
from modules.finmon_shift_wizard import (
    ShiftWizard, SELECT_CLUB, SELECT_SHIFT_TIME,
    ENTER_FACT_CASH, ENTER_FACT_CARD, ENTER_QR, ENTER_CARD2,
    ENTER_SAFE, ENTER_BOX, CONFIRM_SHIFT
)


def test_wizard_states():
    """Test wizard states are defined correctly"""
    print("Testing wizard states...")
    
    # Check that all states are integers
    assert isinstance(SELECT_CLUB, int), "SELECT_CLUB should be an integer"
    assert isinstance(SELECT_SHIFT_TIME, int), "SELECT_SHIFT_TIME should be an integer"
    assert isinstance(ENTER_FACT_CASH, int), "ENTER_FACT_CASH should be an integer"
    assert isinstance(CONFIRM_SHIFT, int), "CONFIRM_SHIFT should be an integer"
    
    # Check states are unique
    states = [SELECT_CLUB, SELECT_SHIFT_TIME, ENTER_FACT_CASH, ENTER_FACT_CARD,
              ENTER_QR, ENTER_CARD2, ENTER_SAFE, ENTER_BOX, CONFIRM_SHIFT]
    assert len(states) == len(set(states)), "All states should be unique"
    
    print("✅ Wizard states test passed")


def test_wizard_initialization():
    """Test wizard initialization"""
    print("Testing wizard initialization...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        wizard = ShiftWizard(finmon, None, owner_ids=[123456])
        
        assert wizard.finmon == finmon, "FinMon instance not set"
        assert wizard.is_owner(123456), "Owner check failed"
        assert not wizard.is_owner(999999), "Non-owner check failed"
        
        print("✅ Wizard initialization test passed")


async def test_cmd_shift_with_club():
    """Test /shift command with club auto-detection"""
    print("Testing /shift with auto-detected club...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        wizard = ShiftWizard(finmon, None)
        
        # Mock update and context
        update = MagicMock()
        update.effective_chat.id = 5329834944  # Рио chat ID
        update.message = AsyncMock()
        
        context = MagicMock()
        context.user_data = {}
        
        # Call cmd_shift
        result = await wizard.cmd_shift(update, context)
        
        # Check result
        assert result == SELECT_SHIFT_TIME, f"Expected SELECT_SHIFT_TIME state, got {result}"
        assert context.user_data['shift_club'] == "Рио", "Club not set correctly"
        assert 'shift_data' in context.user_data, "Shift data not initialized"
        
        # Check message was sent
        assert update.message.reply_text.called, "Message not sent"
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]
        assert "Рио" in message_text, "Club name not in message"
        assert "Выберите время смены" in message_text, "Shift time prompt not in message"
        
        print("✅ /shift with auto-detected club test passed")


async def test_cmd_shift_without_club():
    """Test /shift command without club auto-detection"""
    print("Testing /shift without auto-detected club...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        wizard = ShiftWizard(finmon, None)
        
        # Mock update and context
        update = MagicMock()
        update.effective_chat.id = 99999999  # Unknown chat ID
        update.message = AsyncMock()
        
        context = MagicMock()
        context.user_data = {}
        
        # Call cmd_shift
        result = await wizard.cmd_shift(update, context)
        
        # Check result
        assert result == SELECT_CLUB, f"Expected SELECT_CLUB state, got {result}"
        assert 'shift_data' in context.user_data, "Shift data not initialized"
        
        # Check message was sent
        assert update.message.reply_text.called, "Message not sent"
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]
        assert "Выберите клуб" in message_text, "Club selection prompt not in message"
        
        print("✅ /shift without auto-detected club test passed")


async def test_select_club():
    """Test club selection"""
    print("Testing club selection...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        wizard = ShiftWizard(finmon, None)
        
        # Mock update and context for Rio
        update = MagicMock()
        update.callback_query = AsyncMock()
        update.callback_query.data = "club_rio"
        
        context = MagicMock()
        context.user_data = {'shift_data': {}}
        
        # Call select_club
        result = await wizard.select_club(update, context)
        
        # Check result
        assert result == SELECT_SHIFT_TIME, f"Expected SELECT_SHIFT_TIME state, got {result}"
        assert context.user_data['shift_club'] == "Рио", "Club not set correctly"
        
        # Check message was edited
        assert update.callback_query.edit_message_text.called, "Message not edited"
        
        print("✅ Club selection test passed")


async def test_select_shift_time():
    """Test shift time selection"""
    print("Testing shift time selection...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        wizard = ShiftWizard(finmon, None)
        
        # Mock update and context
        update = MagicMock()
        update.callback_query = AsyncMock()
        update.callback_query.data = "shift_time_evening"
        
        context = MagicMock()
        context.user_data = {
            'shift_club': 'Рио',
            'shift_data': {}
        }
        
        # Call select_shift_time
        result = await wizard.select_shift_time(update, context)
        
        # Check result
        assert result == ENTER_FACT_CASH, f"Expected ENTER_FACT_CASH state, got {result}"
        assert context.user_data['shift_time'] == "evening", "Shift time not set correctly"
        assert 'prev_official' in context.user_data, "Previous balances not set"
        assert 'prev_box' in context.user_data, "Previous box balance not set"
        
        # Check message was edited
        assert update.callback_query.edit_message_text.called, "Message not edited"
        call_args = update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0]
        assert "Прошлый раз" in message_text, "Previous balances not shown"
        
        print("✅ Shift time selection test passed")


async def test_receive_fact_cash():
    """Test receiving cash revenue"""
    print("Testing cash revenue input...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        wizard = ShiftWizard(finmon, None)
        
        # Mock update and context
        update = MagicMock()
        update.message = AsyncMock()
        update.message.text = "3 440"
        
        context = MagicMock()
        context.user_data = {
            'shift_data': {}
        }
        
        # Call receive_fact_cash
        result = await wizard.receive_fact_cash(update, context)
        
        # Check result
        assert result == ENTER_FACT_CARD, f"Expected ENTER_FACT_CARD state, got {result}"
        assert context.user_data['shift_data']['fact_cash'] == 3440.0, "Cash not set correctly"
        
        # Check message was sent
        assert update.message.reply_text.called, "Message not sent"
        
        print("✅ Cash revenue input test passed")


async def test_full_flow():
    """Test full wizard flow"""
    print("Testing full wizard flow...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        balances_file = os.path.join(tmpdir, "test_balances.json")
        log_file = os.path.join(tmpdir, "test_log.csv")
        
        finmon = FinMonSimple(balances_file, log_file)
        wizard = ShiftWizard(finmon, None)
        
        # Test data
        context = MagicMock()
        context.user_data = {
            'shift_club': 'Рио',
            'shift_time': 'evening',
            'prev_official': 0,
            'prev_box': 0,
            'shift_data': {
                'fact_cash': 3440.0,
                'fact_card': 12345.0,
                'qr': 500.0,
                'card2': 0.0,
                'safe_cash_end': 5000.0,
                'box_cash_end': 2000.0
            }
        }
        
        # Mock confirm
        update = MagicMock()
        update.callback_query = AsyncMock()
        update.callback_query.data = "shift_confirm"
        update.effective_user.id = 123456
        update.effective_user.username = "testuser"
        
        # Call confirm_shift
        from telegram.ext import ConversationHandler
        result = await wizard.confirm_shift(update, context)
        
        # Check result
        assert result == ConversationHandler.END, "Conversation not ended"
        
        # Check balances were updated
        balances = finmon.get_balances()
        assert balances['Рио']['official'] == 5000.0, "Official balance not updated"
        assert balances['Рио']['box'] == 2000.0, "Box balance not updated"
        
        # Check CSV log
        movements = finmon.get_recent_movements('Рио', limit=1)
        assert len(movements) == 1, "Movement not logged"
        
        print("✅ Full wizard flow test passed")


async def main():
    """Run all async tests"""
    await test_cmd_shift_with_club()
    await test_cmd_shift_without_club()
    await test_select_club()
    await test_select_shift_time()
    await test_receive_fact_cash()
    await test_full_flow()


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Testing FinMon Button-Based Wizard")
    print("=" * 60 + "\n")
    
    try:
        # Run sync tests
        test_wizard_states()
        test_wizard_initialization()
        
        # Run async tests
        import asyncio
        asyncio.run(main())
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
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
