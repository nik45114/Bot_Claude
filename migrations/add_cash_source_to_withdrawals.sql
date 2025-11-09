-- Migration: Add cash_source to shift_cash_withdrawals
-- Description: Add cash_source column to track which cash register was used (main or box)
-- Date: 2025-11-08

-- Add cash_source column (default 'main' for backward compatibility)
ALTER TABLE shift_cash_withdrawals ADD COLUMN cash_source TEXT DEFAULT 'main';

-- Create index for faster filtering by cash_source
CREATE INDEX IF NOT EXISTS idx_shift_cash_withdrawals_source ON shift_cash_withdrawals(cash_source);
