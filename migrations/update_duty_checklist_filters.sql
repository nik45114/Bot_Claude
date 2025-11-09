-- Migration: Add filtering fields to duty_checklist_items
-- Date: 2025-11-09
-- Description: Add club and shift_type filters for conditional checklist items

-- Add new columns
ALTER TABLE duty_checklist_items ADD COLUMN club TEXT; -- NULL = показывать всегда, 'Рио' или 'Север' = только для этого клуба
ALTER TABLE duty_checklist_items ADD COLUMN shift_type TEXT; -- NULL = показывать всегда, 'morning' или 'evening' = только для этого типа смены

-- Update existing items with filters
-- Ночная смена - только для вечерних смен
UPDATE duty_checklist_items SET shift_type = 'evening' WHERE category = '🌙 Ночная смена';

-- Вентиляция РИО - только для клуба РИО
UPDATE duty_checklist_items SET club = 'Рио' WHERE item_text = 'Вентиляция РИО в ночной режим';
