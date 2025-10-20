#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Formatters - Formatting functions for Financial Monitoring reports
"""

from datetime import date, datetime
from typing import Dict, Any, List


def format_shift_report(shift_data: dict, club_name: str) -> str:
    """
    Форматирование детального отчёта о смене в красивом формате
    
    Args:
        shift_data: Данные смены
        club_name: Название клуба
    
    Returns:
        Отформатированный отчёт
    """
    time_label = "☀️ Утро" if shift_data.get('shift_time') == 'morning' else "🌙 Вечер"
    shift_date = shift_data.get('shift_date')
    if isinstance(shift_date, str):
        shift_date = datetime.fromisoformat(shift_date).date()
    date_str = shift_date.strftime('%d.%m.%Y')
    
    # Заголовок
    report = f"[{club_name}] {time_label} {date_str}\n"
    report += "━━━━━━━━━━━━━━━━━━━━\n"
    
    # Выручка
    report += "💰 Выручка:\n"
    report += f"  Наличные: {shift_data.get('fact_cash', 0):,.0f} ₽\n"
    report += f"  Безнал (осн): {shift_data.get('fact_card', 0):,.0f} ₽\n"
    report += f"  QR-код: {shift_data.get('qr', 0):,.0f} ₽\n"
    report += f"  Безнал (новая): {shift_data.get('card2', 0):,.0f} ₽\n"
    
    # Общая выручка
    total_revenue = (
        shift_data.get('fact_cash', 0) + 
        shift_data.get('fact_card', 0) + 
        shift_data.get('qr', 0) + 
        shift_data.get('card2', 0)
    )
    report += f"  📊 Итого: {total_revenue:,.0f} ₽\n"
    
    report += "\n🏦 Остатки на конец смены:\n"
    report += f"  Сейф: {shift_data.get('safe_cash_end', 0):,.0f} ₽\n"
    report += f"  Коробка: {shift_data.get('box_cash_end', 0):,.0f} ₽\n"
    report += f"  Товарка (нал): {shift_data.get('goods_cash', 0):,.0f} ₽\n"
    
    # Расходы
    report += "\n💸 Расходы:\n"
    report += f"  Компенсации: {shift_data.get('compensations', 0):,.0f} ₽\n"
    report += f"  Зарплаты: {shift_data.get('salary_payouts', 0):,.0f} ₽\n"
    report += f"  Прочие: {shift_data.get('other_expenses', 0):,.0f} ₽\n"
    
    total_expenses = (
        shift_data.get('compensations', 0) + 
        shift_data.get('salary_payouts', 0) + 
        shift_data.get('other_expenses', 0)
    )
    report += f"  📊 Итого: {total_expenses:,.0f} ₽\n"
    
    # Инвентарь
    report += "\n🎮 Инвентарь:\n"
    report += f"  Геймпады: {shift_data.get('joysticks_total', 0)} шт "
    report += f"(в ремонте: {shift_data.get('joysticks_in_repair', 0)}, "
    report += f"требуется: {shift_data.get('joysticks_need_repair', 0)})\n"
    report += f"  Игр: {shift_data.get('games_count', 0)} шт\n"
    
    # Хозяйство
    report += "\n🧻 Хозяйство:\n"
    toilet = "✅ есть" if shift_data.get('toilet_paper') else "❌ нет"
    towels = "✅ есть" if shift_data.get('paper_towels') else "❌ нет"
    report += f"  Туалетка: {toilet}\n"
    report += f"  Полотенца: {towels}\n"
    
    # Примечания
    if shift_data.get('notes'):
        report += f"\n📝 Примечание:\n"
        report += f"  {shift_data['notes']}\n"
    
    return report


def format_balance_report(balances: List[Dict[str, Any]]) -> str:
    """
    Форматирование отчёта о балансах касс
    
    Args:
        balances: Список балансов
    
    Returns:
        Отформатированный отчёт
    """
    if not balances:
        return "❌ Нет данных о балансах касс"
    
    report = "💰 ТЕКУЩИЕ БАЛАНСЫ КАСС\n"
    report += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    current_club = None
    for balance in balances:
        club_name = balance.get('club_name', 'Unknown')
        if current_club != club_name:
            current_club = club_name
            report += f"🏢 {current_club}\n"
        
        cash_type = balance.get('cash_type', 'unknown')
        cash_type_label = "💼 Официальная" if cash_type == 'official' else "📦 Коробка"
        balance_val = balance.get('balance', 0)
        report += f"  {cash_type_label}: {balance_val:,.2f} ₽\n"
    
    return report


def format_shifts_list(shifts: List[Dict[str, Any]], get_club_display_name_func) -> str:
    """
    Форматирование списка последних смен
    
    Args:
        shifts: Список смен
        get_club_display_name_func: Функция для получения названия клуба
    
    Returns:
        Отформатированный список смен
    """
    if not shifts:
        return "❌ Нет сданных смен"
    
    report = "📊 ПОСЛЕДНИЕ СМЕНЫ\n"
    report += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for shift in shifts:
        club_name = get_club_display_name_func(shift['club_id'])
        time_label = "☀️ Утро" if shift['shift_time'] == 'morning' else "🌙 Вечер"
        
        shift_date = shift['shift_date']
        if isinstance(shift_date, str):
            shift_date = datetime.fromisoformat(shift_date).date()
        date_str = shift_date.strftime('%d.%m.%Y')
        
        report += f"📅 [{club_name}] {time_label} {date_str}\n"
        report += f"👤 Админ: {shift.get('admin_username', 'Unknown')}\n"
        
        total_revenue = (
            shift.get('fact_cash', 0) + 
            shift.get('fact_card', 0) + 
            shift.get('qr', 0) + 
            shift.get('card2', 0)
        )
        report += f"💰 Выручка: {shift.get('fact_cash', 0):,.0f} ₽ (нал) + "
        report += f"{shift.get('fact_card', 0):,.0f} ₽ (б/н) = {total_revenue:,.0f} ₽\n"
        
        total_expenses = (
            shift.get('compensations', 0) + 
            shift.get('salary_payouts', 0) + 
            shift.get('other_expenses', 0)
        )
        if total_expenses > 0:
            report += f"💸 Расходы: {total_expenses:,.0f} ₽\n"
        
        report += "━━━━━━━━━━━━━━━━\n"
    
    return report


def format_summary(summary_data: Dict[str, Any], period_name: str) -> str:
    """
    Форматирование сводного отчёта по доходам/расходам
    
    Args:
        summary_data: Данные сводки
        period_name: Название периода (например, "За сегодня", "За неделю")
    
    Returns:
        Отформатированный отчёт
    """
    report = f"📈 СВОДКА {period_name.upper()}\n"
    report += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if not summary_data or not summary_data.get('clubs'):
        report += "❌ Нет данных за выбранный период\n"
        return report
    
    # По каждому клубу
    for club_name, club_data in summary_data.get('clubs', {}).items():
        report += f"🏢 {club_name}\n"
        report += f"  📊 Смен: {club_data.get('shift_count', 0)}\n"
        report += f"  💰 Доход наличные: {club_data.get('total_cash', 0):,.0f} ₽\n"
        report += f"  💳 Доход безнал: {club_data.get('total_card', 0):,.0f} ₽\n"
        report += f"  📱 QR-код: {club_data.get('total_qr', 0):,.0f} ₽\n"
        
        total_income = (
            club_data.get('total_cash', 0) + 
            club_data.get('total_card', 0) + 
            club_data.get('total_qr', 0) + 
            club_data.get('total_card2', 0)
        )
        report += f"  ✅ Всего доход: {total_income:,.0f} ₽\n"
        
        total_expenses = (
            club_data.get('total_compensations', 0) + 
            club_data.get('total_salary', 0) + 
            club_data.get('total_other_expenses', 0)
        )
        report += f"  💸 Всего расходы: {total_expenses:,.0f} ₽\n"
        
        net_profit = total_income - total_expenses
        profit_emoji = "📈" if net_profit >= 0 else "📉"
        report += f"  {profit_emoji} Чистая прибыль: {net_profit:,.0f} ₽\n"
        report += "\n"
    
    # Общая сводка
    total_data = summary_data.get('total', {})
    if total_data:
        report += "━━━━━━━━━━━━━━━━━━━━\n"
        report += "🌟 ИТОГО ПО ВСЕМ КЛУБАМ:\n"
        report += f"  📊 Смен: {total_data.get('shift_count', 0)}\n"
        
        total_income = (
            total_data.get('total_cash', 0) + 
            total_data.get('total_card', 0) + 
            total_data.get('total_qr', 0) + 
            total_data.get('total_card2', 0)
        )
        report += f"  💰 Доход: {total_income:,.0f} ₽\n"
        
        total_expenses = (
            total_data.get('total_compensations', 0) + 
            total_data.get('total_salary', 0) + 
            total_data.get('total_other_expenses', 0)
        )
        report += f"  💸 Расходы: {total_expenses:,.0f} ₽\n"
        
        net_profit = total_income - total_expenses
        profit_emoji = "📈" if net_profit >= 0 else "📉"
        report += f"  {profit_emoji} Прибыль: {net_profit:,.0f} ₽\n"
    
    return report
