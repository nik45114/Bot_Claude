#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Formatters - Helper functions for formatting shift data
"""

from datetime import date


def get_shift_emoji(shift_time: str) -> str:
    """
    Get emoji for shift time
    
    Args:
        shift_time: 'morning' or 'evening'
    
    Returns:
        Emoji string
    """
    return "☀️" if shift_time == 'morning' else "🌙"


def get_shift_label(shift_time: str) -> str:
    """
    Get Russian label for shift time
    
    Args:
        shift_time: 'morning' or 'evening'
    
    Returns:
        Russian label string
    """
    return "Утро" if shift_time == 'morning' else "Вечер"


def format_date_short(dt: date) -> str:
    """
    Format date as DD.MM
    
    Args:
        dt: Date object
    
    Returns:
        Formatted date string (e.g., "25.10")
    """
    return dt.strftime('%d.%m')


def format_shift_badge(shift_time: str, shift_date: date) -> str:
    """
    Format complete shift badge with emoji, label and date
    
    Args:
        shift_time: 'morning' or 'evening'
        shift_date: Date object
    
    Returns:
        Formatted badge string (e.g., "☀️ Утро 25.10")
    """
    emoji = get_shift_emoji(shift_time)
    label = get_shift_label(shift_time)
    date_str = format_date_short(shift_date)
    
    return f"{emoji} {label} {date_str}"
