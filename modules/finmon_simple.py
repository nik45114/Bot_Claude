#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Simple - Financial Monitoring without Database
Uses JSON for balances and CSV for transaction logs
"""

import json
import csv
import os
import re
from datetime import datetime, date
from typing import Dict, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

# File paths
BALANCES_FILE = "finmon_balances.json"
LOG_FILE = "finmon_log.csv"

# Club mapping
CHAT_TO_CLUB = {
    5329834944: "Рио",
    5992731922: "Север"
}

class FinMonSimple:
    """Simple financial monitoring with JSON/CSV storage"""
    
    def __init__(self, balances_file: str = BALANCES_FILE, log_file: str = LOG_FILE):
        self.balances_file = balances_file
        self.log_file = log_file
        self._init_storage()
    
    def _init_storage(self):
        """Initialize JSON and CSV files if they don't exist"""
        # Initialize balances file
        if not os.path.exists(self.balances_file):
            initial_balances = {
                "Рио": {"official": 0, "box": 0},
                "Север": {"official": 0, "box": 0}
            }
            with open(self.balances_file, 'w', encoding='utf-8') as f:
                json.dump(initial_balances, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Created {self.balances_file}")
        
        # Initialize CSV log file
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'club', 'shift_date', 'shift_time',
                    'admin_tg_id', 'admin_username', 'duty_name',
                    'safe_cash_end', 'box_cash_end',
                    'delta_official', 'delta_box',
                    'fact_cash', 'fact_card', 'qr', 'card2'
                ])
                writer.writeheader()
            logger.info(f"✅ Created {self.log_file}")
    
    def get_balances(self) -> Dict[str, Dict[str, float]]:
        """Load balances from JSON file"""
        try:
            with open(self.balances_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Error loading balances: {e}")
            return {"Рио": {"official": 0, "box": 0}, "Север": {"official": 0, "box": 0}}
    
    def save_balances(self, balances: Dict[str, Dict[str, float]]):
        """Save balances to JSON file"""
        try:
            with open(self.balances_file, 'w', encoding='utf-8') as f:
                json.dump(balances, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Balances saved")
        except Exception as e:
            logger.error(f"❌ Error saving balances: {e}")
    
    def get_club_from_chat(self, chat_id: int) -> Optional[str]:
        """Get club name from chat ID"""
        return CHAT_TO_CLUB.get(chat_id)
    
    def parse_number(self, text: str) -> float:
        """Parse number from text, handling spaces and commas"""
        if not text or text.lower() in ['0', 'нет', 'не работает', '-']:
            return 0.0
        
        # Remove spaces
        cleaned = text.strip().replace(' ', '')
        
        # Handle comma - if there's only one comma and it's followed by digits, treat as decimal separator
        # Otherwise remove it (thousands separator)
        if ',' in cleaned:
            comma_count = cleaned.count(',')
            if comma_count == 1:
                parts = cleaned.split(',')
                # If right part has 3 digits, it's thousands separator, remove it
                # If right part has 1-2 digits, it's decimal separator
                if len(parts) == 2 and len(parts[1]) <= 2:
                    cleaned = cleaned.replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            else:
                # Multiple commas - remove all
                cleaned = cleaned.replace(',', '')
        
        try:
            return float(cleaned)
        except ValueError:
            logger.warning(f"⚠️ Could not parse number: {text}")
            return 0.0
    
    def parse_shift_paste(self, text: str, club: str = None) -> Optional[Dict]:
        """
        DEPRECATED: Parse shift data from pasted text format
        
        This method is deprecated and no longer used by the wizard.
        Use the button-based wizard instead (ShiftWizard in finmon_shift_wizard.py).
        Kept for backward compatibility with tests only.
        
        Expected format (can be in one message):
        [Club name on first line if not auto-detected]
        Fact cash: 3 440
        Fact card: 12 345
        QR: 0 / не работает
        Card2: 0
        Safe cash: 5 000
        Box cash: 2 000
        
        Returns dict with parsed data or None if parsing fails
        """
        logger.warning("⚠️ parse_shift_paste is deprecated. Use button-based wizard instead.")
        lines = text.strip().split('\n')
        data = {
            'club': club,
            'fact_cash': 0.0,
            'fact_card': 0.0,
            'qr': 0.0,
            'card2': 0.0,
            'safe_cash_end': 0.0,
            'box_cash_end': 0.0
        }
        
        # Check if first line is club name
        if not club and lines:
            first_line = lines[0].strip()
            if first_line in ["Рио", "Север", "Rio", "Sever"]:
                data['club'] = "Рио" if first_line in ["Рио", "Rio"] else "Север"
                lines = lines[1:]  # Remove club line
        
        # Parse each line
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip empty lines
            if not line_lower:
                continue
            
            # Extract number from line
            # Look for patterns like "название: число" or "название число"
            match = re.search(r'[:：]\s*(.+)$', line)
            if match:
                value_str = match.group(1).strip()
            else:
                # Try to extract last word/number group
                parts = line.split()
                value_str = parts[-1] if parts else "0"
            
            # Determine which field this is
            if any(kw in line_lower for kw in ['факт нал', 'fact cash', 'наличка факт']):
                data['fact_cash'] = self.parse_number(value_str)
            elif any(kw in line_lower for kw in ['факт карт', 'fact card', 'карта факт']):
                data['fact_card'] = self.parse_number(value_str)
            elif 'qr' in line_lower or 'кр' in line_lower:
                data['qr'] = self.parse_number(value_str)
            elif any(kw in line_lower for kw in ['card2', 'карта2', 'новая карта']):
                data['card2'] = self.parse_number(value_str)
            elif any(kw in line_lower for kw in ['сейф', 'safe', 'офиц']):
                data['safe_cash_end'] = self.parse_number(value_str)
            elif any(kw in line_lower for kw in ['коробка', 'box', 'ящик']):
                data['box_cash_end'] = self.parse_number(value_str)
        
        return data if data['club'] else None
    
    def submit_shift(self, data: Dict, admin_tg_id: int, admin_username: str = "",
                    shift_date: date = None, shift_time: str = "evening", duty_name: str = "",
                    identity_confirmed: bool = False, confirmation_timestamp: str = "") -> bool:
        """
        Submit shift and update balances
        
        Args:
            data: Parsed shift data (includes 'expenses' list)
            admin_tg_id: Telegram ID of admin submitting shift
            admin_username: Telegram username
            shift_date: Date of shift (default: today)
            shift_time: 'morning' or 'evening'
            duty_name: Name of person on duty from schedule
            identity_confirmed: Whether admin confirmed their identity
            confirmation_timestamp: Timestamp of confirmation
        
        Returns:
            True if successful, False otherwise
        """
        if not data.get('club'):
            logger.error("❌ No club specified in shift data")
            return False
        
        club = data['club']
        if shift_date is None:
            shift_date = date.today()
        
        # Get expenses
        expenses = data.get('expenses', [])
        expenses_total = sum(exp['amount'] for exp in expenses)
        expenses_details = json.dumps(expenses, ensure_ascii=False) if expenses else ""
        
        # Load current balances
        balances = self.get_balances()
        
        if club not in balances:
            logger.error(f"❌ Unknown club: {club}")
            return False
        
        # Calculate deltas
        old_official = balances[club]['official']
        old_box = balances[club]['box']
        
        new_official = data['safe_cash_end']
        new_box = data['box_cash_end']
        
        delta_official = new_official - old_official
        delta_box = new_box - old_box
        
        # Update balances
        balances[club]['official'] = new_official
        balances[club]['box'] = new_box
        
        self.save_balances(balances)
        
        # Append to CSV log
        try:
            # Check if we need to add headers (file doesn't exist or is empty)
            file_exists = os.path.exists(self.log_file)
            fieldnames = [
                'timestamp', 'club', 'shift_date', 'shift_time',
                'admin_tg_id', 'admin_username', 'duty_name',
                'safe_cash_end', 'box_cash_end',
                'delta_official', 'delta_box',
                'fact_cash', 'fact_card', 'qr', 'card2',
                'expenses_total', 'expenses_details',
                'identity_confirmed', 'confirmation_timestamp'
            ]
            
            with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # Write header if file is new or empty
                if not file_exists or os.path.getsize(self.log_file) == 0:
                    writer.writeheader()
                
                writer.writerow({
                    'timestamp': datetime.now().isoformat(),
                    'club': club,
                    'shift_date': shift_date.isoformat(),
                    'shift_time': shift_time,
                    'admin_tg_id': admin_tg_id,
                    'admin_username': admin_username,
                    'duty_name': duty_name,
                    'safe_cash_end': new_official,
                    'box_cash_end': new_box,
                    'delta_official': delta_official,
                    'delta_box': delta_box,
                    'fact_cash': data.get('fact_cash', 0),
                    'fact_card': data.get('fact_card', 0),
                    'qr': data.get('qr', 0),
                    'card2': data.get('card2', 0),
                    'expenses_total': expenses_total,
                    'expenses_details': expenses_details,
                    'identity_confirmed': 1 if identity_confirmed else 0,
                    'confirmation_timestamp': confirmation_timestamp
                })
            logger.info(f"✅ Shift logged for {club} with {len(expenses)} expenses")
            return True
        except Exception as e:
            logger.error(f"❌ Error logging shift: {e}")
            return False
    
    def get_club_balances(self, club: str) -> Optional[Dict[str, float]]:
        """Get balances for a specific club"""
        balances = self.get_balances()
        return balances.get(club)
    
    def get_all_balances(self) -> Dict[str, Dict[str, float]]:
        """Get all balances"""
        return self.get_balances()
    
    def get_recent_movements(self, club: str = None, limit: int = 10) -> List[Dict]:
        """
        Get recent movements from CSV log
        
        Args:
            club: Filter by club (None for all)
            limit: Maximum number of rows to return
        
        Returns:
            List of movement dictionaries
        """
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            # Filter by club if specified
            if club:
                rows = [r for r in rows if r.get('club') == club]
            
            # Return most recent first
            rows.reverse()
            return rows[:limit]
        except Exception as e:
            logger.error(f"❌ Error reading movements: {e}")
            return []
    
    def format_shift_summary(self, data: Dict, duty_name: str = "") -> str:
        """Format shift data as summary for confirmation"""
        club = data.get('club', 'Неизвестно')
        
        summary = f"📊 Сводка смены\n\n"
        summary += f"🏢 Клуб: {club}\n\n"
        
        if duty_name:
            summary += f"👤 Дежурный по графику: {duty_name}\n\n"
        
        summary += "💰 Выручка:\n"
        summary += f"  • Наличка факт: {data.get('fact_cash', 0):,.0f}\n"
        summary += f"  • Карта факт: {data.get('fact_card', 0):,.0f}\n"
        summary += f"  • QR: {data.get('qr', 0):,.0f}\n"
        summary += f"  • Карта2: {data.get('card2', 0):,.0f}\n\n"
        
        summary += "🔐 Остатки:\n"
        summary += f"  • Сейф (офиц): {data.get('safe_cash_end', 0):,.0f}\n"
        summary += f"  • Коробка: {data.get('box_cash_end', 0):,.0f}\n"
        
        return summary
    
    def format_balances(self) -> str:
        """Format all balances as text"""
        balances = self.get_balances()
        
        text = "💰 Текущие остатки\n\n"
        for club, amounts in balances.items():
            text += f"🏢 {club}:\n"
            text += f"  • Офиц (сейф): {amounts['official']:,.0f}\n"
            text += f"  • Коробка: {amounts['box']:,.0f}\n\n"
        
        return text
    
    def format_movements(self, club: str, limit: int = 10) -> str:
        """Format recent movements for a club"""
        movements = self.get_recent_movements(club, limit)
        
        if not movements:
            return f"📝 Нет движений для {club}"
        
        text = f"📝 Последние движения - {club}\n\n"
        for mov in movements:
            date_str = mov.get('shift_date', 'N/A')
            time_str = mov.get('shift_time', 'N/A')
            delta_off = float(mov.get('delta_official', 0))
            delta_box = float(mov.get('delta_box', 0))
            duty = mov.get('duty_name', '')
            
            text += f"📅 {date_str} ({time_str})\n"
            if duty:
                text += f"👤 {duty}\n"
            text += f"  Δ Офиц: {delta_off:+,.0f}\n"
            text += f"  Δ Коробка: {delta_box:+,.0f}\n\n"
        
        return text
