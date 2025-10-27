#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schedule Parser - Парсинг расписания смен из Google Sheets
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Tuple
import time

logger = logging.getLogger(__name__)

# Try to import gspread and google auth
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    logger.warning("⚠️ gspread not available - install with: pip install gspread google-auth")

# Russian month names
MONTH_NAMES = {
    1: 'Январь',
    2: 'Февраль',
    3: 'Март',
    4: 'Апрель',
    5: 'Май',
    6: 'Июнь',
    7: 'Июль',
    8: 'Август',
    9: 'Сентябрь',
    10: 'Октябрь',
    11: 'Ноябрь',
    12: 'Декабрь'
}

# Shift type and club mappings
SHIFT_MAPPINGS = {
    'Д(С)': ('Север', 'morning'),
    'Н(С)': ('Север', 'evening'),
    'Д(Р)': ('Рио', 'morning'),
    'Н(Р)': ('Рио', 'evening'),
}


class ScheduleParser:
    """Parser for duty schedule from Google Sheets"""
    
    def __init__(self, shift_manager, admin_db=None, spreadsheet_id: str = None, credentials_path: str = None):
        """
        Initialize parser
        
        Args:
            shift_manager: ShiftManager instance for DB operations
            admin_db: AdminDB instance for name mapping
            spreadsheet_id: Google Sheets ID
            credentials_path: Path to service account JSON credentials
        """
        self.shift_manager = shift_manager
        self.admin_db = admin_db
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        
        # Cache for parsed data
        self._cache = {}
        self._cache_timestamp = {}
        self._cache_ttl = 600  # 10 minutes
        
        # Google Sheets client (lazy init)
        self._client = None
        self._spreadsheet = None
        
        if not GSPREAD_AVAILABLE:
            logger.error("❌ gspread not installed - Google Sheets parsing disabled")
        elif not self.spreadsheet_id or not self.credentials_path:
            logger.warning("⚠️ Google Sheets not configured - missing spreadsheet_id or credentials_path")
        else:
            logger.info(f"📋 Schedule parser configured: spreadsheet {self.spreadsheet_id[:10]}...")
    
    def _get_sheet_client(self):
        """Get or create gspread client with service account auth"""
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread not available")
        
        if not self._client:
            try:
                # Define scopes
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets.readonly',
                    'https://www.googleapis.com/auth/drive.readonly'
                ]
                
                # Load credentials
                creds = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=scopes
                )
                
                # Create client
                self._client = gspread.authorize(creds)
                logger.info("✅ Google Sheets client authorized")
                
            except Exception as e:
                logger.error(f"❌ Failed to authorize Google Sheets client: {e}")
                raise
        
        return self._client
    
    def _get_spreadsheet(self):
        """Get spreadsheet object"""
        if not self._spreadsheet:
            client = self._get_sheet_client()
            self._spreadsheet = client.open_by_key(self.spreadsheet_id)
            logger.info(f"✅ Opened spreadsheet: {self._spreadsheet.title}")
        
        return self._spreadsheet
    
    def _get_month_sheet(self, target_date: date):
        """
        Get worksheet for specific month
        
        Args:
            target_date: Date to find sheet for
        
        Returns:
            Worksheet or None if not found
        """
        try:
            spreadsheet = self._get_spreadsheet()
            
            month_name = MONTH_NAMES.get(target_date.month, '')
            year = target_date.year
            
            # Try multiple sheet name formats
            possible_names = [
                f"{month_name} {year}",  # "Октябрь 2025"
                month_name,              # "Октябрь"
                f"{month_name} {str(year)[2:]}",  # "Октябрь 25"
            ]
            
            for sheet_name in possible_names:
                logger.info(f"🔍 Looking for sheet: {sheet_name}")
                try:
                    worksheet = spreadsheet.worksheet(sheet_name)
                    logger.info(f"✅ Found sheet: {sheet_name}")
                    return worksheet
                except gspread.exceptions.WorksheetNotFound:
                    logger.debug(f"   Not found: {sheet_name}")
                    continue
            
            logger.warning(f"⚠️ Sheet not found for {target_date.month}/{target_date.year}")
            return None
                
        except Exception as e:
            logger.error(f"❌ Error accessing sheet: {e}")
            return None
    
    def _parse_date_headers(self, worksheet) -> Dict[int, date]:
        """
        Parse date headers from first row
        
        Args:
            worksheet: gspread Worksheet object
        
        Returns:
            Dict mapping column index to date object
        """
        date_headers = {}
        
        try:
            # Get first row (headers)
            first_row = worksheet.row_values(1)
            
            logger.info(f"📅 Parsing {len(first_row)} header cells")
            
            # Determine year from sheet title or use current year
            sheet_title = worksheet.title
            year = date.today().year  # Default to current year
            
            # Try to extract year from sheet title
            if ' ' in sheet_title:
                last_part = sheet_title.split()[-1]
                if last_part.isdigit():
                    year_candidate = int(last_part)
                    # If it's 2-digit year (e.g., "25"), assume 20xx
                    if year_candidate < 100:
                        year = 2000 + year_candidate
                    else:
                        year = year_candidate
            
            logger.info(f"📅 Using year: {year} (from sheet '{sheet_title}')")
            
            # Parse each cell (starting from column B, index 1)
            for col_index, cell_value in enumerate(first_row[1:], start=2):
                if not cell_value or cell_value.strip() == '':
                    continue
                
                # Try to parse date in format DD.MM
                match = re.match(r'(\d{1,2})\.(\d{1,2})', str(cell_value).strip())
                if match:
                    day = int(match.group(1))
                    month = int(match.group(2))
                    
                    try:
                        parsed_date = date(year, month, day)
                        date_headers[col_index] = parsed_date
                        logger.debug(f"  Column {col_index}: {cell_value} → {parsed_date}")
                    except ValueError as e:
                        logger.warning(f"⚠️ Invalid date in column {col_index}: {cell_value} ({e})")
            
            logger.info(f"✅ Parsed {len(date_headers)} date headers")
            return date_headers
            
        except Exception as e:
            logger.error(f"❌ Error parsing date headers: {e}")
            return {}
    
    def _map_fullname_to_user_id(self, full_name: str) -> Optional[int]:
        """
        Map full name from sheet to user ID from admin database
        
        Args:
            full_name: Full name from Google Sheet
        
        Returns:
            User ID or None if not found
        """
        if not self.admin_db or not full_name:
            return None
        
        # Normalize name
        normalized_name = ' '.join(full_name.strip().split())
        
        try:
            # Search in admin database
            admins, _ = self.admin_db.search_admins(normalized_name, per_page=10)
            
            if not admins:
                logger.debug(f"👤 No admin found for: {normalized_name}")
                return None
            
            # Check for exact or close match
            for admin in admins:
                admin_full_name = admin.get('full_name', '')
                if not admin_full_name:
                    continue
                
                # Normalize admin name
                admin_normalized = ' '.join(admin_full_name.strip().split())
                
                # Case-insensitive comparison
                if admin_normalized.lower() == normalized_name.lower():
                    user_id = admin.get('user_id')
                    logger.info(f"✅ Matched '{normalized_name}' → user_id={user_id}")
                    return user_id
                
                # Partial match (first or last name)
                if (normalized_name.lower() in admin_normalized.lower() or 
                    admin_normalized.lower() in normalized_name.lower()):
                    user_id = admin.get('user_id')
                    logger.info(f"⚠️ Partial match '{normalized_name}' → '{admin_full_name}' (user_id={user_id})")
                    return user_id
            
            logger.debug(f"👤 No matching admin for: {normalized_name}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error mapping name to user_id: {e}")
            return None
    
    def parse_for_date(self, target_date: date, use_cache: bool = True) -> Dict[Tuple[str, str], Dict]:
        """
        Parse schedule for specific date
        
        Args:
            target_date: Date to parse schedule for
            use_cache: Whether to use cached data
        
        Returns:
            Dict with structure: {(club, shift_type): {'admin_id': int, 'admin_name': str}}
        """
        # Check cache
        cache_key = target_date.isoformat()
        if use_cache and cache_key in self._cache:
            cache_age = time.time() - self._cache_timestamp.get(cache_key, 0)
            if cache_age < self._cache_ttl:
                logger.info(f"📦 Using cached data for {target_date} (age: {cache_age:.0f}s)")
                return self._cache[cache_key]
        
        result = {}
        
        try:
            # Get worksheet for this month
            worksheet = self._get_month_sheet(target_date)
            if not worksheet:
                logger.warning(f"⚠️ No sheet found for {target_date}")
                return result
            
            # Parse date headers
            date_headers = self._parse_date_headers(worksheet)
            if not date_headers:
                logger.warning(f"⚠️ No date headers found in sheet")
                return result
            
            # Find column for target date
            target_col = None
            for col_index, header_date in date_headers.items():
                if header_date == target_date:
                    target_col = col_index
                    break
            
            if target_col is None:
                logger.info(f"📅 Date {target_date} not found in sheet headers")
                return result
            
            logger.info(f"🎯 Found target date in column {target_col}")
            
            # Get all values from the sheet (more efficient than row-by-row)
            all_values = worksheet.get_all_values()
            
            # Parse each row (skip header row)
            duties_found = 0
            for row_index, row_values in enumerate(all_values[1:], start=2):
                # Get full name from column A (index 0)
                full_name = row_values[0].strip() if row_values else ''
                if not full_name or full_name == '.':
                    continue
                
                # Get cell value for target date
                cell_value = row_values[target_col - 1].strip() if len(row_values) >= target_col else ''
                
                if not cell_value or cell_value == '.':
                    continue
                
                # Parse shift type and club
                if cell_value in SHIFT_MAPPINGS:
                    club, shift_type = SHIFT_MAPPINGS[cell_value]
                    
                    # Map name to user ID
                    user_id = self._map_fullname_to_user_id(full_name)
                    
                    # Store result
                    key = (club, shift_type)
                    result[key] = {
                        'admin_id': user_id,
                        'admin_name': full_name
                    }
                    
                    duties_found += 1
                    logger.info(f"  Row {row_index}: {full_name} → {cell_value} ({club}, {shift_type})")
            
            logger.info(f"✅ Parsed {duties_found} duties for {target_date}")
            
            # Update cache
            self._cache[cache_key] = result
            self._cache_timestamp[cache_key] = time.time()
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error parsing schedule for {target_date}: {e}")
            import traceback
            traceback.print_exc()
            return result
    
    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._cache_timestamp.clear()
        logger.info("🗑️ Cache cleared")
    
    def test_connection(self) -> bool:
        """
        Test Google Sheets connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            spreadsheet = self._get_spreadsheet()
            logger.info(f"✅ Connection test successful: {spreadsheet.title}")
            logger.info(f"📊 Sheets: {[ws.title for ws in spreadsheet.worksheets()]}")
            return True
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def get_available_months(self) -> List[str]:
        """
        Get list of available month sheets
        
        Returns:
            List of sheet names
        """
        try:
            spreadsheet = self._get_spreadsheet()
            sheets = [ws.title for ws in spreadsheet.worksheets()]
            logger.info(f"📅 Available sheets: {sheets}")
            return sheets
        except Exception as e:
            logger.error(f"❌ Error getting sheets: {e}")
            return []
    
    # Legacy methods for compatibility
    
    def get_duty_for_date(self, duty_date: date, club: str, shift_type: str) -> Optional[Dict]:
        """
        Get duty admin for specific date (DB fallback)
        
        Args:
            duty_date: Date to check
            club: Club name
            shift_type: 'morning' or 'evening'
        
        Returns:
            Duty info dict or None
        """
        return self.shift_manager.get_expected_duty(club, shift_type, duty_date)
    
    def get_week_schedule(self, start_date: Optional[date] = None) -> List[Dict]:
        """
        Get schedule for a week (DB fallback)
        
        Args:
            start_date: Start date (default: today)
        
        Returns:
            List of duty entries for the week
        """
        if start_date is None:
            start_date = date.today()
        
        return self.shift_manager.get_week_schedule(start_date, days=7)


def create_parser(shift_manager, admin_db=None, spreadsheet_id=None, credentials_path=None) -> ScheduleParser:
    """Factory function to create ScheduleParser"""
    return ScheduleParser(
        shift_manager=shift_manager,
        admin_db=admin_db,
        spreadsheet_id=spreadsheet_id,
        credentials_path=credentials_path
    )
