-- Migration: Add accounting sync log table
-- Description: Track which shifts were sent to accounting system to avoid duplicates
-- Date: 2025-11-01

-- Table to track sent shifts
CREATE TABLE IF NOT EXISTS accounting_sync_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shift_date TEXT NOT NULL,
  shift_type TEXT NOT NULL,  -- 'morning' or 'evening'
  club TEXT,
  cash_amount REAL,
  cashless_amount REAL,
  qr_amount REAL,
  sync_status TEXT DEFAULT 'success',  -- 'success', 'failed', 'pending'
  response_data TEXT,  -- JSON response from accounting API
  sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  error_message TEXT
);

-- Unique index to prevent duplicate syncs
CREATE UNIQUE INDEX IF NOT EXISTS idx_accounting_sync_unique
ON accounting_sync_log(shift_date, shift_type, club);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_accounting_sync_status
ON accounting_sync_log(sync_status, sent_at);
