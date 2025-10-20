#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Models - Pydantic models for Financial Monitoring
"""

from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional


class Club(BaseModel):
    """Модель клуба"""
    id: Optional[int] = None
    name: str
    type: str  # 'official' or 'box'
    created_at: Optional[datetime] = None


class Shift(BaseModel):
    """Модель смены"""
    id: Optional[int] = None
    club_id: int
    shift_date: date
    shift_time: str  # 'morning' or 'evening'
    admin_tg_id: int
    admin_username: Optional[str] = None
    
    # Выручка
    fact_cash: float = 0.0
    fact_card: float = 0.0
    qr: float = 0.0
    card2: float = 0.0
    
    # Кассы
    safe_cash_end: float = 0.0
    box_cash_end: float = 0.0
    goods_cash: float = 0.0
    
    # Расходы
    compensations: float = 0.0
    salary_payouts: float = 0.0
    other_expenses: float = 0.0
    
    # Инвентарь
    joysticks_total: int = 0
    joysticks_in_repair: int = 0
    joysticks_need_repair: int = 0
    games_count: int = 0
    
    # Хозяйство
    toilet_paper: bool = False
    paper_towels: bool = False
    
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class CashBalance(BaseModel):
    """Модель баланса кассы"""
    id: Optional[int] = None
    club_id: int
    cash_type: str  # 'official' or 'box'
    balance: float = 0.0
    updated_at: Optional[datetime] = None
