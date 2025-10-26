#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone unit tests for time detection functions (no telegram dependency)
Tests the shift auto-detection logic based on Moscow time
"""

import sys
from datetime import datetime, date, timedelta
import pytz

# Inline the time detection functions for testing without telegram dependency
TIMEZONE = 'Europe/Moscow'
SHIFT_CLOSE_TIMES = {
    'morning': '10:00',
    'evening': '22:00'
}
EARLY_CLOSE_OFFSET_HOURS = 1
GRACE_MINUTES_AFTER_CLOSE = 60


def now_msk() -> datetime:
    """Get current time in Moscow timezone"""
    msk = pytz.timezone(TIMEZONE)
    return datetime.now(msk)


def parse_msk_time(time_str: str, ref_date: date = None) -> datetime:
    """Parse time string (HH:MM) to MSK datetime"""
    if ref_date is None:
        ref_date = now_msk().date()
    
    msk = pytz.timezone(TIMEZONE)
    hour, minute = map(int, time_str.split(':'))
    dt = datetime(ref_date.year, ref_date.month, ref_date.day, hour, minute)
    return msk.localize(dt)


def is_within_window(
    now: datetime,
    close_time_str: str,
    early_offset_hours: int,
    grace_minutes: int,
    ref_date: date = None
) -> bool:
    """Check if current time is within the shift close window"""
    if ref_date is None:
        ref_date = now.date()
    
    close_time = parse_msk_time(close_time_str, ref_date)
    early_time = close_time - timedelta(hours=early_offset_hours)
    grace_end = close_time + timedelta(minutes=grace_minutes)
    
    return early_time <= now <= grace_end


def test_parse_msk_time():
    """Test MSK time parsing"""
    print("\n1. Testing parse_msk_time...")
    
    # Test with specific date
    test_date = date(2024, 10, 25)
    dt = parse_msk_time("10:00", test_date)
    
    assert dt.hour == 10, f"Expected hour 10, got {dt.hour}"
    assert dt.minute == 0, f"Expected minute 0, got {dt.minute}"
    assert dt.date() == test_date, f"Expected date {test_date}, got {dt.date()}"
    assert dt.tzinfo is not None, "Timezone should be set"
    print("✅ parse_msk_time works correctly")


def test_is_within_window():
    """Test window detection logic"""
    print("\n2. Testing is_within_window...")
    
    msk = pytz.timezone(TIMEZONE)
    test_date = date(2024, 10, 25)
    
    # Morning shift: 10:00 close, 09:00 early, 11:00 grace end
    
    # Test at 08:59 - should be outside window
    dt_0859 = msk.localize(datetime(2024, 10, 25, 8, 59))
    result = is_within_window(dt_0859, "10:00", 1, 60, test_date)
    assert not result, "08:59 should be outside window"
    print("✅ 08:59 correctly identified as outside window")
    
    # Test at 09:00 - should be inside window (early)
    dt_0900 = msk.localize(datetime(2024, 10, 25, 9, 0))
    result = is_within_window(dt_0900, "10:00", 1, 60, test_date)
    assert result, "09:00 should be inside window"
    print("✅ 09:00 correctly identified as inside window")
    
    # Test at 10:00 - should be inside window (exact close time)
    dt_1000 = msk.localize(datetime(2024, 10, 25, 10, 0))
    result = is_within_window(dt_1000, "10:00", 1, 60, test_date)
    assert result, "10:00 should be inside window"
    print("✅ 10:00 correctly identified as inside window")
    
    # Test at 10:30 - should be inside window (grace period)
    dt_1030 = msk.localize(datetime(2024, 10, 25, 10, 30))
    result = is_within_window(dt_1030, "10:00", 1, 60, test_date)
    assert result, "10:30 should be inside window"
    print("✅ 10:30 correctly identified as inside window (grace)")
    
    # Test at 11:00 - should be inside window (end of grace)
    dt_1100 = msk.localize(datetime(2024, 10, 25, 11, 0))
    result = is_within_window(dt_1100, "10:00", 1, 60, test_date)
    assert result, "11:00 should be inside window (end of grace)"
    print("✅ 11:00 correctly identified as inside window (end of grace)")
    
    # Test at 11:01 - should be outside window (after grace)
    dt_1101 = msk.localize(datetime(2024, 10, 25, 11, 1))
    result = is_within_window(dt_1101, "10:00", 1, 60, test_date)
    assert not result, "11:01 should be outside window"
    print("✅ 11:01 correctly identified as outside window")


def test_evening_window():
    """Test evening shift window"""
    print("\n3. Testing evening shift window...")
    
    msk = pytz.timezone(TIMEZONE)
    test_date = date(2024, 10, 25)
    
    # Evening shift: 22:00 close, 21:00 early, 23:00 grace end
    
    # Test at 20:59 - outside
    dt_2059 = msk.localize(datetime(2024, 10, 25, 20, 59))
    result = is_within_window(dt_2059, "22:00", 1, 60, test_date)
    assert not result, "20:59 should be outside window"
    print("✅ 20:59 correctly identified as outside window")
    
    # Test at 21:00 - inside (early)
    dt_2100 = msk.localize(datetime(2024, 10, 25, 21, 0))
    result = is_within_window(dt_2100, "22:00", 1, 60, test_date)
    assert result, "21:00 should be inside window"
    print("✅ 21:00 correctly identified as inside window")
    
    # Test at 22:00 - inside (close time)
    dt_2200 = msk.localize(datetime(2024, 10, 25, 22, 0))
    result = is_within_window(dt_2200, "22:00", 1, 60, test_date)
    assert result, "22:00 should be inside window"
    print("✅ 22:00 correctly identified as inside window")
    
    # Test at 22:15 - inside (grace)
    dt_2215 = msk.localize(datetime(2024, 10, 25, 22, 15))
    result = is_within_window(dt_2215, "22:00", 1, 60, test_date)
    assert result, "22:15 should be inside window"
    print("✅ 22:15 correctly identified as inside window (grace)")
    
    # Test at 23:01 - outside
    dt_2301 = msk.localize(datetime(2024, 10, 25, 23, 1))
    result = is_within_window(dt_2301, "22:00", 1, 60, test_date)
    assert not result, "23:01 should be outside window"
    print("✅ 23:01 correctly identified as outside window")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing FinMon Time Detection Functions")
    print("=" * 60)
    
    try:
        test_parse_msk_time()
        test_is_within_window()
        test_evening_window()
        
        print("\n" + "=" * 60)
        print("✅ ALL TIME DETECTION TESTS PASSED!")
        print("=" * 60)
        
        # Display configuration
        print("\nConfiguration:")
        print(f"  Timezone: {TIMEZONE}")
        print(f"  Morning close: {SHIFT_CLOSE_TIMES['morning']}")
        print(f"  Evening close: {SHIFT_CLOSE_TIMES['evening']}")
        print(f"  Early offset: {EARLY_CLOSE_OFFSET_HOURS} hour(s)")
        print(f"  Grace period: {GRACE_MINUTES_AFTER_CLOSE} minutes")
        
        # Show current time
        print("\nCurrent MSK time:")
        current = now_msk()
        print(f"  {current.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        print("\nTime windows:")
        print(f"  Morning: 09:00 - 11:00 MSK")
        print(f"  Evening: 21:00 - 23:00 MSK")
        print(f"  Evening grace: 00:00 - 00:30 MSK (next day)")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
