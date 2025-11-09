-- Migration: Fix finmon_shifts table schema for club assistant
-- Date: 2025-11-08
-- Description: Rename old finmon_shifts table and create new one with correct schema

-- Rename old table to backup
ALTER TABLE finmon_shifts RENAME TO finmon_shifts_old;

-- Create new finmon_shifts table with correct schema
CREATE TABLE finmon_shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    club TEXT NOT NULL,
    shift_type TEXT NOT NULL CHECK(shift_type IN ('morning', 'evening')),
    opened_at TIMESTAMP,
    closed_at TIMESTAMP,

    -- Revenue
    cash_revenue REAL DEFAULT 0,
    card_revenue REAL DEFAULT 0,
    qr_revenue REAL DEFAULT 0,
    card2_revenue REAL DEFAULT 0,
    total_revenue REAL DEFAULT 0,

    -- Cash boxes
    safe_cash_start REAL DEFAULT 0,
    safe_cash_end REAL DEFAULT 0,
    box_cash_start REAL DEFAULT 0,
    box_cash_end REAL DEFAULT 0,

    -- Expenses
    total_expenses REAL DEFAULT 0,

    -- Z-reports photos
    z_report_cash_photo TEXT,
    z_report_card_photo TEXT,
    z_report_qr_photo TEXT,
    z_report_card2_photo TEXT,

    -- Z-reports OCR data
    z_report_cash_ocr TEXT,
    z_report_card_ocr TEXT,
    z_report_qr_ocr TEXT,
    z_report_card2_ocr TEXT,

    -- Disabled payment methods
    cash_disabled BOOLEAN DEFAULT 0,
    card_disabled BOOLEAN DEFAULT 0,
    qr_disabled BOOLEAN DEFAULT 0,
    card2_disabled BOOLEAN DEFAULT 0,

    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_finmon_shifts_club_shift ON finmon_shifts(club, shift_type, closed_at DESC);
CREATE INDEX idx_finmon_shifts_admin ON finmon_shifts(admin_id);
CREATE INDEX idx_finmon_shifts_closed_at ON finmon_shifts(closed_at DESC);
