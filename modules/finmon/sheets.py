#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Google Sheets - Integration with Google Sheets for Financial Monitoring
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Import conditionally since not all deployments may have Google Sheets configured
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    logger.warning("⚠️ gspread/oauth2client not installed - Google Sheets sync disabled")


class GoogleSheetsSync:
    """Класс для синхронизации с Google Sheets"""
    
    def __init__(self, credentials_path: str, sheet_name: str):
        self.credentials_path = credentials_path
        self.sheet_name = sheet_name
        self.client = None
        self.spreadsheet = None
        
        if not GSPREAD_AVAILABLE:
            logger.warning("⚠️ Google Sheets sync disabled - missing dependencies")
            return
        
        try:
            self._init_client()
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Sheets client: {e}")
    
    def _init_client(self):
        """Инициализация клиента Google Sheets"""
        if not GSPREAD_AVAILABLE:
            return
        
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_path, scope
            )
            self.client = gspread.authorize(creds)
            
            # Открыть или создать таблицу
            try:
                self.spreadsheet = self.client.open(self.sheet_name)
            except gspread.SpreadsheetNotFound:
                self.spreadsheet = self.client.create(self.sheet_name)
                logger.info(f"✅ Created new spreadsheet: {self.sheet_name}")
            
            # Инициализировать листы
            self._init_worksheets()
            
            logger.info(f"✅ Google Sheets client initialized: {self.sheet_name}")
        except Exception as e:
            logger.error(f"❌ Error initializing Google Sheets client: {e}")
            raise
    
    def _init_worksheets(self):
        """Инициализация рабочих листов"""
        if not self.spreadsheet:
            return
        
        try:
            # Лист "Shifts"
            try:
                shifts_ws = self.spreadsheet.worksheet("Shifts")
            except gspread.WorksheetNotFound:
                shifts_ws = self.spreadsheet.add_worksheet(title="Shifts", rows="1000", cols="20")
                # Заголовки
                headers = [
                    "Дата", "Время", "Клуб", "Админ", "Факт нал", "Факт безнал", "QR", "Новая касса",
                    "Сейф", "Коробка", "Товарка", "Комп", "ЗП", "Прочие",
                    "Геймпады", "Ремонт", "Требуется", "Игр", "Туалетка", "Полотенца", "Примечание"
                ]
                shifts_ws.append_row(headers)
            
            # Лист "Balances"
            try:
                balances_ws = self.spreadsheet.worksheet("Balances")
            except gspread.WorksheetNotFound:
                balances_ws = self.spreadsheet.add_worksheet(title="Balances", rows="100", cols="4")
                headers = ["Клуб", "Тип кассы", "Баланс", "Обновлено"]
                balances_ws.append_row(headers)
            
            logger.info("✅ Worksheets initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing worksheets: {e}")
    
    def append_shift(self, shift_data: Dict[str, Any], club_name: str) -> bool:
        """Добавить смену в Google Sheets"""
        if not GSPREAD_AVAILABLE or not self.spreadsheet:
            logger.warning("⚠️ Google Sheets not configured - skipping sync")
            return False
        
        try:
            shifts_ws = self.spreadsheet.worksheet("Shifts")
            
            # Форматирование данных для строки
            shift_time_label = "Утро" if shift_data.get('shift_time') == 'morning' else "Вечер"
            toilet_paper = "есть" if shift_data.get('toilet_paper') else "нет"
            paper_towels = "есть" if shift_data.get('paper_towels') else "нет"
            
            row = [
                str(shift_data.get('shift_date', '')),
                shift_time_label,
                club_name,
                shift_data.get('admin_username', ''),
                shift_data.get('fact_cash', 0),
                shift_data.get('fact_card', 0),
                shift_data.get('qr', 0),
                shift_data.get('card2', 0),
                shift_data.get('safe_cash_end', 0),
                shift_data.get('box_cash_end', 0),
                shift_data.get('goods_cash', 0),
                shift_data.get('compensations', 0),
                shift_data.get('salary_payouts', 0),
                shift_data.get('other_expenses', 0),
                shift_data.get('joysticks_total', 0),
                shift_data.get('joysticks_in_repair', 0),
                shift_data.get('joysticks_need_repair', 0),
                shift_data.get('games_count', 0),
                toilet_paper,
                paper_towels,
                shift_data.get('notes', '')
            ]
            
            shifts_ws.append_row(row)
            logger.info(f"✅ Shift added to Google Sheets")
            return True
        except Exception as e:
            logger.error(f"❌ Error appending shift to Google Sheets: {e}")
            return False
    
    def update_balances(self, balances: List[Dict[str, Any]]) -> bool:
        """Обновить балансы в Google Sheets"""
        if not GSPREAD_AVAILABLE or not self.spreadsheet:
            logger.warning("⚠️ Google Sheets not configured - skipping sync")
            return False
        
        try:
            balances_ws = self.spreadsheet.worksheet("Balances")
            
            # Очистить все кроме заголовка
            balances_ws.resize(rows=1)
            balances_ws.resize(rows=len(balances) + 1)
            
            # Добавить данные
            for balance in balances:
                club_type_label = "Официальная" if balance['cash_type'] == 'official' else "Коробка"
                row = [
                    balance['club_name'],
                    club_type_label,
                    balance['balance'],
                    str(balance.get('updated_at', ''))
                ]
                balances_ws.append_row(row)
            
            logger.info(f"✅ Balances updated in Google Sheets")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating balances in Google Sheets: {e}")
            return False
    
    def get_duty_admin_for_shift(self, club_name: str, shift_date: str, shift_time: str) -> Optional[str]:
        """
        Получить имя админа на дежурстве из Google Sheets расписания
        
        Args:
            club_name: Название клуба (например, "Рио", "Север")
            shift_date: Дата смены в формате YYYY-MM-DD
            shift_time: Время смены ('morning' или 'evening')
        
        Returns:
            Имя админа или None, если не найдено
        """
        if not GSPREAD_AVAILABLE or not self.spreadsheet:
            logger.debug("⚠️ Google Sheets not configured - cannot get duty admin")
            return None
        
        try:
            # Попытаться найти лист Schedule
            try:
                schedule_ws = self.spreadsheet.worksheet("Schedule")
            except:
                logger.debug("⚠️ Schedule worksheet not found")
                return None
            
            # Получить все данные из листа
            all_values = schedule_ws.get_all_values()
            
            if not all_values or len(all_values) < 2:
                logger.debug("⚠️ Schedule worksheet is empty")
                return None
            
            # Первая строка - заголовки
            headers = all_values[0]
            
            # Попытаться найти колонки
            # Ожидаемые колонки: Дата, Клуб, Смена, Админ
            try:
                date_col = headers.index('Дата')
                club_col = headers.index('Клуб')
                shift_col = headers.index('Смена')
                admin_col = headers.index('Админ')
            except ValueError:
                logger.warning("⚠️ Schedule worksheet missing required columns (Дата, Клуб, Смена, Админ)")
                return None
            
            # Преобразовать shift_time в русское название
            shift_time_ru = "Утро" if shift_time == 'morning' else "Вечер"
            
            # Преобразовать дату в формат, используемый в таблице (например, "01.01.2024")
            from datetime import datetime
            try:
                date_obj = datetime.fromisoformat(shift_date)
                date_formatted = date_obj.strftime('%d.%m.%Y')
            except:
                date_formatted = shift_date
            
            # Искать в строках
            for row in all_values[1:]:
                if len(row) <= max(date_col, club_col, shift_col, admin_col):
                    continue
                
                # Проверить совпадение по дате, клубу и смене
                if (row[date_col] == date_formatted and 
                    club_name in row[club_col] and 
                    row[shift_col] == shift_time_ru):
                    admin_name = row[admin_col].strip()
                    if admin_name:
                        logger.info(f"✅ Found duty admin from schedule: {admin_name}")
                        return admin_name
            
            logger.debug(f"⚠️ No duty admin found for {club_name} {shift_time_ru} {date_formatted}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting duty admin from schedule: {e}")
            return None
    
    def get_service_account_email(self) -> Optional[str]:
        """
        Получить email сервисного аккаунта для инструкций
        
        Returns:
            Email сервисного аккаунта или None
        """
        if not GSPREAD_AVAILABLE or not self.credentials_path:
            return None
        
        try:
            import json
            with open(self.credentials_path, 'r') as f:
                creds_data = json.load(f)
                return creds_data.get('client_email')
        except Exception as e:
            logger.error(f"❌ Error reading service account email: {e}")
            return None
