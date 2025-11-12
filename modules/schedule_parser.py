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

# Shift type and club mappings (case-insensitive)
SHIFT_MAPPINGS = {
    # Заглавные буквы
    'Д(С)': ('Север', 'morning'),
    'Н(С)': ('Север', 'evening'),
    'Д(Р)': ('Рио', 'morning'),
    'Н(Р)': ('Рио', 'evening'),
    # Строчные буквы
    'д(с)': ('Север', 'morning'),
    'н(с)': ('Север', 'evening'),
    'д(р)': ('Рио', 'morning'),
    'н(р)': ('Рио', 'evening'),
    # Смешанный регистр (на всякий случай)
    'Д(с)': ('Север', 'morning'),
    'Н(с)': ('Север', 'evening'),
    'Д(р)': ('Рио', 'morning'),
    'Н(р)': ('Рио', 'evening'),
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
                # Define scopes (need full access for updating sheets)
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
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
            
            logger.info(f"📅 Date headers: {list(date_headers.values())[:5]}... (showing first 5)")
            
            # Find column for target date
            target_col = None
            for col_index, header_date in date_headers.items():
                if header_date == target_date:
                    target_col = col_index
                    break
            
            if target_col is None:
                logger.warning(f"📅 Date {target_date} NOT found in sheet headers")
                logger.info(f"   Available dates: {sorted([d.strftime('%d.%m.%Y') for d in date_headers.values()])[:10]}")
                return result
            
            logger.info(f"🎯 Found target date in column {target_col}")
            
            # Get all values from the sheet (more efficient than row-by-row)
            all_values = worksheet.get_all_values()
            logger.info(f"📊 Total rows in sheet: {len(all_values)}")
            
            # Parse each row (skip header row)
            duties_found = 0
            rows_checked = 0
            for row_index, row_values in enumerate(all_values[1:], start=2):
                rows_checked += 1
                
                # Get full name from column A (index 0)
                full_name = row_values[0].strip() if row_values else ''
                if not full_name or full_name == '.':
                    continue
                
                # Get cell value for target date
                cell_value = row_values[target_col - 1].strip() if len(row_values) >= target_col else ''
                
                # Log first 5 rows for debugging
                if rows_checked <= 5:
                    logger.info(f"  Row {row_index}: name='{full_name}', cell='{cell_value}'")
                
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
                    logger.info(f"  ✅ Row {row_index}: {full_name} → {cell_value} ({club}, {shift_type})")
                elif cell_value and duties_found < 3:  # Log first few unknown values
                    logger.warning(f"  ⚠️ Row {row_index}: unknown value '{cell_value}' (expected: Д(С), Н(С), Д(Р), Н(Р))")
            
            logger.info(f"✅ Checked {rows_checked} rows, found {duties_found} duties for {target_date}")
            
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

    def get_duty_name(self, club: str, shift_date: date, shift_type: str) -> Optional[str]:
        """
        Get the name of the person on duty from the schedule

        Args:
            club: Club name ("Рио" or "Север")
            shift_date: Date of the shift
            shift_type: 'morning' or 'evening'

        Returns:
            Full name of person on duty, or None if not found
        """
        duty_info = self.get_duty_for_date(shift_date, club, shift_type)
        if duty_info:
            return duty_info.get('admin_name')
        return None
    
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

    def get_admin_shifts_for_month(self, admin_name: str, target_month: date) -> List[Dict]:
        """
        Get all shifts for specific admin in a given month from Google Sheets

        Args:
            admin_name: Full name of admin (e.g., "Теплов Владислав дмитриевич")
            target_month: Any date in the target month

        Returns:
            List of dicts with structure: [{
                'date': date object,
                'club': 'Рио' or 'Север',
                'shift_type': 'morning' or 'evening',
                'marker': 'д(р)' etc
            }, ...]
        """
        result = []

        try:
            # Get worksheet for this month
            worksheet = self._get_month_sheet(target_month)
            if not worksheet:
                logger.warning(f"⚠️ No sheet found for {target_month}")
                return result

            # Parse date headers
            date_headers = self._parse_date_headers(worksheet)
            if not date_headers:
                logger.warning(f"⚠️ No date headers found")
                return result

            # Get all values from column A (admin names)
            col_a_values = worksheet.col_values(1)

            # Find admin's row (only in main list - stop at first empty cell)
            admin_row = None
            for row_idx, name_cell in enumerate(col_a_values, start=1):
                if row_idx > 2 and (not name_cell or not name_cell.strip()):
                    break  # End of main list
                if admin_name in name_cell:
                    admin_row = row_idx
                    logger.info(f"🔍 Found admin '{admin_name}' at row {row_idx}")
                    break

            if not admin_row:
                logger.info(f"ℹ️ Admin '{admin_name}' not found in schedule")
                return result

            # Get all values from admin's row
            admin_row_values = worksheet.row_values(admin_row)

            # Check each date column for shift markers
            for col_idx, shift_date in date_headers.items():
                if col_idx > len(admin_row_values):
                    continue

                cell_value = admin_row_values[col_idx - 1].strip() if col_idx > 0 else ""

                if cell_value and cell_value in SHIFT_MAPPINGS:
                    club, shift_type = SHIFT_MAPPINGS[cell_value]
                    result.append({
                        'date': shift_date,
                        'club': club,
                        'shift_type': shift_type,
                        'marker': cell_value
                    })

            logger.info(f"✅ Found {len(result)} shifts for {admin_name} in {target_month.strftime('%B %Y')}")
            return result

        except Exception as e:
            logger.error(f"❌ Error getting admin shifts: {e}")
            return result

    def update_duty_assignment(self, duty_date: date, club: str, shift_type: str, old_admin_name: str, new_admin_name: str) -> bool:
        """
        Update duty assignment in Google Sheets when replacement occurs

        Removes shift marker (д(р), н(р), д(с), н(с)) from old admin and adds to new admin

        Args:
            duty_date: Date of the duty
            club: Club name ('Рио' or 'Север')
            shift_type: 'morning' or 'evening'
            old_admin_name: Full name of admin who was originally scheduled
            new_admin_name: Full name of admin who takes the shift

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the worksheet for this month
            worksheet = self._get_month_sheet(duty_date)
            if not worksheet:
                logger.error(f"❌ Could not find worksheet for {duty_date}")
                return False

            # Parse date headers to find the column
            date_headers = self._parse_date_headers(worksheet)
            target_col = None
            for col_idx, col_date in date_headers.items():
                if col_date == duty_date:
                    target_col = col_idx
                    break

            if not target_col:
                logger.error(f"❌ Could not find column for date {duty_date}")
                return False

            # Map club and shift_type to shift marker
            shift_markers = {
                ('Рио', 'morning'): 'д(р)',
                ('Рио', 'evening'): 'н(р)',
                ('Север', 'morning'): 'д(с)',
                ('Север', 'evening'): 'н(с)'
            }

            target_marker = shift_markers.get((club, shift_type))
            if not target_marker:
                logger.error(f"❌ Unknown club/shift_type combination: {club}/{shift_type}")
                return False

            # Get all values from column A (admin names) and target column (shift markers)
            col_a_values = worksheet.col_values(1)  # Column A with names
            target_col_values = worksheet.col_values(target_col)  # Target date column

            # Find row with old admin name (only in main list - stop at first empty cell in column A)
            old_admin_row = None
            new_admin_row = None

            # Find the end of the main admin list (first empty row in column A)
            main_list_end = len(col_a_values)
            for row_idx, name_cell in enumerate(col_a_values, start=1):
                if row_idx > 2 and (not name_cell or not name_cell.strip()):  # Skip header rows, find first empty
                    main_list_end = row_idx
                    logger.info(f"📍 Main admin list ends at row {main_list_end}")
                    break

            for row_idx, name_cell in enumerate(col_a_values, start=1):
                # Stop searching after main list ends
                if row_idx >= main_list_end:
                    break

                if not name_cell or not name_cell.strip():
                    continue

                # Check if this is the old admin's row
                if old_admin_name in name_cell:
                    # Verify this row has the target marker in the date column
                    if row_idx <= len(target_col_values):
                        date_cell = target_col_values[row_idx - 1] if row_idx > 0 else ""
                        if target_marker in date_cell.lower():
                            old_admin_row = row_idx
                            logger.info(f"🔍 Found old admin '{old_admin_name}' at row {row_idx} with marker {target_marker}")

                # Check if this is the new admin's row
                if new_admin_name in name_cell:
                    new_admin_row = row_idx
                    logger.info(f"🔍 Found new admin '{new_admin_name}' at row {row_idx}")

            # If old admin not found, it means the shift was empty or something else
            if not old_admin_row:
                logger.warning(f"⚠️ Old admin '{old_admin_name}' with marker {target_marker} not found")

            # Remove marker from old admin if found
            if old_admin_row:
                old_cell_value = worksheet.cell(old_admin_row, target_col).value or ""
                # Remove the marker from old admin's cell
                new_old_value = old_cell_value.replace(target_marker, '').strip()
                worksheet.update_cell(old_admin_row, target_col, new_old_value)
                logger.info(f"✅ Removed '{target_marker}' from {old_admin_name} at row {old_admin_row}")

            # Add marker to new admin
            if new_admin_row:
                new_cell_value = worksheet.cell(new_admin_row, target_col).value or ""
                # Add marker if not already there
                if target_marker not in new_cell_value.lower():
                    if new_cell_value.strip():
                        new_value = f"{new_cell_value} {target_marker}"
                    else:
                        new_value = target_marker
                    try:
                        worksheet.update_cell(new_admin_row, target_col, new_value)
                        logger.info(f"✅ Added '{target_marker}' to {new_admin_name} at row {new_admin_row}")
                    except Exception as e:
                        if "protected" in str(e).lower():
                            logger.error(f"❌ Cannot update row {new_admin_row} - cell is PROTECTED. "
                                       f"Please add bot email 'bot-925@clstmb.iam.gserviceaccount.com' to protected range permissions "
                                       f"or remove protection from the cell.")
                        raise
                else:
                    logger.info(f"ℹ️ {new_admin_name} already has {target_marker}")
            else:
                logger.warning(f"⚠️ Could not find row for new admin '{new_admin_name}'")
                return False

            logger.info(f"✅ Updated Google Sheets: {duty_date} {club}/{shift_type}: {old_admin_name} → {new_admin_name}")
            return True

        except Exception as e:
            logger.error(f"❌ Error updating duty assignment: {e}")
            return False

    def parse_monthly_totals(self, target_date: date) -> Dict[int, Dict[str, int]]:
        """
        Парсить итоговое количество смен за месяц из колонок AF-AJ

        Args:
            target_date: Дата месяца для парсинга

        Returns:
            Dict {admin_id: {'rio': count, 'sever': count, 'total': count}}
        """
        result = {}

        try:
            # Получаем worksheet для этого месяца
            worksheet = self._get_month_sheet(target_date)
            if not worksheet:
                logger.warning(f"⚠️ No sheet found for {target_date}")
                return result

            # Колонки с итогами: AF=32, AG=33, AH=34, AI=35, AJ=36
            # Сначала читаем заголовки чтобы понять какая колонка за что отвечает
            all_values = worksheet.get_all_values()
            logger.info(f"📊 Parsing monthly totals from {len(all_values)} rows")

            # Читаем заголовки из первой строки (индекс 0)
            headers = all_values[0] if all_values else []

            # Определяем какие колонки содержат данные о клубах
            # Ищем упоминания "Рио", "Север" в заголовках AF-AJ
            rio_col = None
            sever_col = None
            total_col = 31  # AF (индекс 31) - обычно общее количество

            for col_idx in range(31, min(36, len(headers))):
                header = headers[col_idx].lower() if col_idx < len(headers) else ''
                logger.info(f"  Column {col_idx} (letter {chr(65+col_idx)}): '{headers[col_idx] if col_idx < len(headers) else ''}'")

                if 'рио' in header or 'rio' in header:
                    rio_col = col_idx
                    logger.info(f"  ✅ Found Rio column at index {col_idx}")
                elif 'север' in header or 'sever' in header:
                    sever_col = col_idx
                    logger.info(f"  ✅ Found Sever column at index {col_idx}")

            logger.info(f"📋 Detected columns: Rio={rio_col}, Sever={sever_col}, Total={total_col}")

            # Парсим каждую строку (пропускаем заголовок)
            for row_index, row_values in enumerate(all_values[1:], start=2):
                # Имя из колонки A (index 0)
                full_name = row_values[0].strip() if row_values else ''
                if not full_name or full_name == '.':
                    continue

                # Получаем user_id по имени
                user_id = self._map_fullname_to_user_id(full_name)
                if not user_id:
                    continue

                # Читаем значения из определённых колонок
                total_shifts = 0
                rio_shifts = 0
                sever_shifts = 0

                try:
                    # Колонка AF (индекс 31) - общее количество смен
                    if len(row_values) > 31 and row_values[31].strip():
                        total_val = row_values[31].strip()
                        if total_val.isdigit():
                            total_shifts = int(total_val)

                    # Читаем из определённых колонок если нашли их в заголовках
                    if rio_col and len(row_values) > rio_col and row_values[rio_col].strip():
                        rio_val = row_values[rio_col].strip()
                        if rio_val.isdigit():
                            rio_shifts = int(rio_val)

                    if sever_col and len(row_values) > sever_col and row_values[sever_col].strip():
                        sever_val = row_values[sever_col].strip()
                        if sever_val.isdigit():
                            sever_shifts = int(sever_val)

                except (ValueError, IndexError) as e:
                    logger.warning(f"⚠️ Error parsing totals for {full_name}: {e}")
                    continue

                # Если есть хоть какие-то данные - сохраняем
                if total_shifts > 0 or rio_shifts > 0 or sever_shifts > 0:
                    # Если разбивка по клубам не найдена, распределяем поровну
                    if total_shifts > 0 and rio_shifts == 0 and sever_shifts == 0:
                        rio_shifts = total_shifts // 2
                        sever_shifts = total_shifts - rio_shifts
                    elif rio_shifts > 0 or sever_shifts > 0:
                        total_shifts = rio_shifts + sever_shifts

                    result[user_id] = {
                        'rio': rio_shifts,
                        'sever': sever_shifts,
                        'total': total_shifts
                    }
                    logger.info(f"  ✅ {full_name} (ID:{user_id}): Рио={rio_shifts}, Север={sever_shifts}, Всего={total_shifts}")

            logger.info(f"✅ Parsed monthly totals for {len(result)} admins")
            return result

        except Exception as e:
            logger.error(f"❌ Error parsing monthly totals: {e}")
            return result


def create_parser(shift_manager, admin_db=None, spreadsheet_id=None, credentials_path=None) -> ScheduleParser:
    """Factory function to create ScheduleParser"""
    return ScheduleParser(
        shift_manager=shift_manager,
        admin_db=admin_db,
        spreadsheet_id=spreadsheet_id,
        credentials_path=credentials_path
    )
