-- Добавление поля club в duty_checklist_progress
-- Дата: 2025-11-11

-- Добавляем колонку club
ALTER TABLE duty_checklist_progress ADD COLUMN club TEXT;

-- Обновляем существующие записи (устанавливаем NULL для старых)
-- Это нормально, так как старые записи будут работать как и раньше

-- Создаем индекс для быстрого поиска по shift_id, item_id и club
CREATE INDEX IF NOT EXISTS idx_duty_checklist_progress_club
ON duty_checklist_progress(shift_id, item_id, club);
