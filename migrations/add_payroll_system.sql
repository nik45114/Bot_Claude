-- Migration: Add Payroll Management System
-- Description: Tables for salary calculation, payments, and employment types
-- Date: 2025-10-27

-- Salary configuration for different employment types
CREATE TABLE IF NOT EXISTS salary_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employment_type TEXT NOT NULL UNIQUE, -- 'self_employed', 'staff', 'contractor'
  rate_per_shift REAL NOT NULL,
  tax_percentage REAL NOT NULL DEFAULT 0,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Salary payments tracking
CREATE TABLE IF NOT EXISTS salary_payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admin_id INTEGER NOT NULL,
  shift_id INTEGER,  -- связь со сменой (если взял с кассы)
  amount REAL NOT NULL,
  payment_type TEXT, -- 'advance' or 'salary' or 'manual'
  payment_date DATE NOT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (admin_id) REFERENCES admins(user_id),
  FOREIGN KEY (shift_id) REFERENCES active_shifts(id)
);

-- Add employment type to admins table
ALTER TABLE admins ADD COLUMN employment_type TEXT DEFAULT 'self_employed';

-- Add salary tracking to active_shifts
ALTER TABLE active_shifts ADD COLUMN salary_taken REAL DEFAULT 0;
ALTER TABLE active_shifts ADD COLUMN closed_at TIMESTAMP;

-- Insert default salary configurations
INSERT OR REPLACE INTO salary_config (employment_type, rate_per_shift, tax_percentage) VALUES
('self_employed', 2000.0, 6.0),  -- Самозанятые: 2000₽ за смену, 6% налог
('staff', 1800.0, 43.0),         -- Штат: 1800₽ за смену, 43% налог
('contractor', 2200.0, 15.0);    -- ГПХ: 2200₽ за смену, 15% налог

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_salary_payments_admin ON salary_payments(admin_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_salary_payments_shift ON salary_payments(shift_id);
CREATE INDEX IF NOT EXISTS idx_admins_employment ON admins(employment_type);
CREATE INDEX IF NOT EXISTS idx_active_shifts_closed ON active_shifts(closed_at);

