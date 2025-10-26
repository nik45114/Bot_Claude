#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Schedule - Google Sheets Integration for Duty Schedule
Reads duty schedule from Google Sheets to determine who is on duty
"""

import logging
from datetime import date
from typing import Optional, Dict
import os

logger = logging.getLogger(__name__)

# Try to import gspread
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    logger.warning("⚠️ gspread not available - duty detection will be disabled")

# Shift codes mapping
SHIFT_CODES = {
    'Рио': {
        'morning': 'н(р)',  # night Rio closes in morning
        'evening': 'д(р)'   # day Rio closes in evening
    },
    'Север': {
        'morning': 'н(с)',  # night Sever closes in morning
        'evening': 'д(с)'   # day Sever closes in evening
    }
}

class FinMonSchedule:
    """Google Sheets duty schedule integration"""
    
    def __init__(self, credentials_path: str = None, sheet_url: str = None):
        """
        Initialize schedule reader
        
        Args:
            credentials_path: Path to Google Service Account JSON
            sheet_url: URL or ID of Google Sheet
        """
        self.credentials_path = credentials_path
        self.sheet_url = sheet_url or "https://docs.google.com/spreadsheets/d/19ILASe6UH7-j1okxg9mvz_GrkQAkCJLXA1mxwocLcV8"
        self.client = None
        self.spreadsheet = None
        self.enabled = False
        self.error_logged = False
        
        if not GSPREAD_AVAILABLE:
            logger.warning("⚠️ Duty schedule disabled: gspread not installed")
            return
        
        if credentials_path and os.path.exists(credentials_path):
            self._init_client()
        else:
            logger.warning(f"⚠️ Duty schedule disabled: credentials not found at {credentials_path}")
    
    def _init_client(self):
        """Initialize Google Sheets client"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_path, scope
            )
            self.client = gspread.authorize(creds)
            
            # Try to open the spreadsheet
            self.spreadsheet = self.client.open_by_url(self.sheet_url)
            self.enabled = True
            
            logger.info(f"✅ Connected to schedule sheet: {self.spreadsheet.title}")
            
        except Exception as e:
            if not self.error_logged:
                logger.warning(f"⚠️ Could not connect to schedule sheet: {e}")
                logger.warning("⚠️ Duty detection will be disabled. Make sure the service account has access.")
                self.error_logged = True
            self.enabled = False
    
    def get_duty_name(self, club: str, shift_date: date, shift_time: str) -> Optional[str]:
        """
        Get the name of the person on duty from the schedule
        
        Args:
            club: Club name ("Рио" or "Север")
            shift_date: Date of the shift
            shift_time: 'morning' or 'evening'
        
        Returns:
            Full name of person on duty, or None if not found/disabled
        """
        if not self.enabled:
            return None
        
        try:
            # Get the first worksheet
            worksheet = self.spreadsheet.sheet1
            
            # Get all values
            all_values = worksheet.get_all_values()
            
            if not all_values or len(all_values) < 2:
                logger.warning("⚠️ Schedule sheet is empty or has insufficient data")
                return None
            
            # Row 1 has dates in DD.MM format
            header_row = all_values[0]
            
            # Format the date to match DD.MM format
            date_str = shift_date.strftime("%d.%m")
            
            # Find the column with this date
            date_col_idx = None
            for idx, cell in enumerate(header_row):
                if cell.strip() == date_str:
                    date_col_idx = idx
                    break
            
            if date_col_idx is None:
                logger.debug(f"⚠️ Date {date_str} not found in schedule")
                return None
            
            # Determine which code to look for
            if club not in SHIFT_CODES:
                logger.warning(f"⚠️ Unknown club: {club}")
                return None
            
            target_code = SHIFT_CODES[club][shift_time]
            
            # Search for the code in the column
            for row_idx in range(1, len(all_values)):  # Skip header row
                row = all_values[row_idx]
                
                if date_col_idx < len(row):
                    cell_value = row[date_col_idx].strip().lower()
                    
                    # Check if this cell contains our target code
                    if target_code.lower() in cell_value:
                        # Get the name from column A
                        if len(row) > 0:
                            name = row[0].strip()
                            if name:
                                logger.info(f"✅ Found duty: {name} for {club} on {date_str} ({shift_time})")
                                return name
            
            logger.debug(f"⚠️ No duty found for {club} on {date_str} ({shift_time}) with code {target_code}")
            return None
            
        except Exception as e:
            if not self.error_logged:
                logger.error(f"❌ Error reading schedule: {e}")
                self.error_logged = True
            return None
    
    def get_service_account_email(self) -> Optional[str]:
        """Get the service account email for sharing instructions"""
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            return None
        
        try:
            import json
            with open(self.credentials_path, 'r') as f:
                creds = json.load(f)
                return creds.get('client_email')
        except Exception as e:
            logger.error(f"❌ Error reading service account email: {e}")
            return None
