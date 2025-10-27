#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schedule Parser - Парсинг расписания смен из Google Sheets
(Пока заглушка для будущей реализации)
"""

import logging
from datetime import date, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class ScheduleParser:
    """Parser for duty schedule from Google Sheets (stub for future implementation)"""
    
    def __init__(self, shift_manager):
        """
        Initialize parser
        
        Args:
            shift_manager: ShiftManager instance for DB operations
        """
        self.shift_manager = shift_manager
        self.google_sheets_url = None  # Will be configured later
        self.credentials_path = None
    
    def configure(self, sheets_url: str, credentials_path: str):
        """
        Configure Google Sheets connection
        
        Args:
            sheets_url: URL to Google Sheet
            credentials_path: Path to credentials JSON file
        """
        self.google_sheets_url = sheets_url
        self.credentials_path = credentials_path
        logger.info(f"📋 Schedule parser configured: {sheets_url}")
    
    def parse_schedule(self) -> bool:
        """
        Parse schedule from Google Sheets
        
        TODO: Implement Google Sheets API integration
        
        Returns:
            True if successful, False otherwise
        """
        logger.warning("⚠️ Schedule parser not yet implemented - using manual input")
        return False
    
    def import_to_db(self, schedule_data: List[Dict]) -> int:
        """
        Import parsed schedule to database
        
        Args:
            schedule_data: List of duty entries with format:
                [{
                    'date': date,
                    'club': str,
                    'shift_type': str,
                    'admin_id': int (optional),
                    'admin_name': str (optional)
                }, ...]
        
        Returns:
            Number of entries imported
        """
        imported = 0
        
        for entry in schedule_data:
            success = self.shift_manager.add_duty_schedule(
                duty_date=entry.get('date'),
                club=entry.get('club'),
                shift_type=entry.get('shift_type'),
                admin_id=entry.get('admin_id'),
                admin_name=entry.get('admin_name')
            )
            
            if success:
                imported += 1
        
        logger.info(f"✅ Imported {imported}/{len(schedule_data)} schedule entries")
        return imported
    
    def get_duty_for_date(self, duty_date: date, club: str, shift_type: str) -> Optional[Dict]:
        """
        Get duty admin for specific date
        
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
        Get schedule for a week
        
        Args:
            start_date: Start date (default: today)
        
        Returns:
            List of duty entries for the week
        """
        if start_date is None:
            start_date = date.today()
        
        schedule = []
        
        for days_offset in range(7):
            check_date = start_date + timedelta(days=days_offset)
            
            for club in ['rio', 'sever']:
                for shift_type in ['morning', 'evening']:
                    duty = self.get_duty_for_date(check_date, club, shift_type)
                    if duty:
                        schedule.append(duty)
        
        return schedule
    
    def manual_add_duty(self, date_str: str, club: str, shift_type: str, 
                       admin_name: str, admin_id: Optional[int] = None) -> bool:
        """
        Manually add duty schedule entry
        
        Args:
            date_str: Date string in format 'YYYY-MM-DD' or 'DD.MM.YYYY'
            club: Club name ('rio' or 'sever')
            shift_type: 'morning' or 'evening'
            admin_name: Admin display name
            admin_id: Admin user ID (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Parse date
            if '.' in date_str:
                # DD.MM.YYYY format
                day, month, year = date_str.split('.')
                duty_date = date(int(year), int(month), int(day))
            else:
                # YYYY-MM-DD format
                year, month, day = date_str.split('-')
                duty_date = date(int(year), int(month), int(day))
            
            return self.shift_manager.add_duty_schedule(
                duty_date=duty_date,
                club=club,
                shift_type=shift_type,
                admin_id=admin_id,
                admin_name=admin_name
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to manually add duty: {e}")
            return False


def create_parser(shift_manager) -> ScheduleParser:
    """Factory function to create ScheduleParser"""
    return ScheduleParser(shift_manager)

