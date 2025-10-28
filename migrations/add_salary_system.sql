-- Migration: Add Salary Calculation System
-- Description: Tables and columns for salary tracking, payments, and cash withdrawals
-- Date: 2025-10-27

-- Add salary-related columns to admins table
ALTER TABLE admins ADD COLUMN employment_type TEXT DEFAULT 'self_employed'; -- 'self_employed', 'staff', 'gpc'
ALTER TABLE admins ADD COLUMN salary_per_shift REAL DEFAULT 0;
ALTER TABLE admins ADD COLUMN tax_rate REAL DEFAULT 0; -- percentage (0 = use default)

-- Create salary_payments table
CREATE TABLE IF NOT EXISTS salary_payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admin_id INTEGER NOT NULL,
  payment_type TEXT NOT NULL, -- 'advance' or 'salary'
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  total_shifts INTEGER NOT NULL,
  gross_amount REAL NOT NULL,
  tax_amount REAL NOT NULL,
  net_amount REAL NOT NULL,
  cash_taken REAL DEFAULT 0, -- already taken from register
  amount_due REAL NOT NULL, -- what's left to pay
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (admin_id) REFERENCES admins(user_id)
);

-- Create shift_cash_withdrawals table
CREATE TABLE IF NOT EXISTS shift_cash_withdrawals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shift_id INTEGER NOT NULL,
  admin_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  reason TEXT DEFAULT 'salary',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (shift_id) REFERENCES active_shifts(id),
  FOREIGN KEY (admin_id) REFERENCES admins(user_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_salary_payments_admin ON salary_payments(admin_id);
CREATE INDEX IF NOT EXISTS idx_salary_payments_period ON salary_payments(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_shift_cash_withdrawals_shift ON shift_cash_withdrawals(shift_id);
CREATE INDEX IF NOT EXISTS idx_shift_cash_withdrawals_admin ON shift_cash_withdrawals(admin_id);
CREATE INDEX IF NOT EXISTS idx_admins_employment_type ON admins(employment_type);

