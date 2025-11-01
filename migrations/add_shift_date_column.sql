-- Migration: Add shift_date column to active_shifts
-- Description: Store the actual shift date (which may differ from opened_at for evening shifts)
-- Date: 2025-11-01

-- Add shift_date column (default to date from opened_at for backward compatibility)
ALTER TABLE active_shifts ADD COLUMN shift_date TEXT;

-- Update existing records to use the date from opened_at
UPDATE active_shifts
SET shift_date = DATE(opened_at)
WHERE shift_date IS NULL;
