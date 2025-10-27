-- Migration: Add Shift Management System
-- Description: Tables for active shifts, shift expenses, and duty schedule
-- Date: 2025-10-27

-- Active shifts tracking
CREATE TABLE IF NOT EXISTS active_shifts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admin_id INTEGER NOT NULL,
  club TEXT NOT NULL,
  shift_type TEXT NOT NULL,  -- 'morning' or 'evening'
  opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  confirmed_by INTEGER,  -- who confirmed (can be same as admin_id)
  status TEXT DEFAULT 'open'  -- 'open', 'closed'
);

-- Shift expenses during active shift
CREATE TABLE IF NOT EXISTS shift_expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shift_id INTEGER NOT NULL,
  cash_source TEXT NOT NULL,  -- 'main' or 'box'
  amount REAL NOT NULL,
  reason TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (shift_id) REFERENCES active_shifts(id)
);

-- Duty schedule (for future Google Sheets integration)
CREATE TABLE IF NOT EXISTS duty_schedule (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  club TEXT NOT NULL,
  shift_type TEXT NOT NULL,
  admin_id INTEGER,
  admin_name TEXT,
  imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(date, club, shift_type)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_active_shifts_admin ON active_shifts(admin_id, status);
CREATE INDEX IF NOT EXISTS idx_shift_expenses_shift ON shift_expenses(shift_id);
CREATE INDEX IF NOT EXISTS idx_duty_schedule_lookup ON duty_schedule(date, club, shift_type);

