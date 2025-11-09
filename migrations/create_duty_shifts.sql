-- Migration: Create duty shifts table for controller shifts
-- Date: 2025-11-08
-- Updated: 2025-11-09 - Revised checklist structure per feedback
-- Description: Tables for duty shift management with checklist and handover notes

-- Duty shifts table
CREATE TABLE IF NOT EXISTS duty_shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    duty_person TEXT NOT NULL,  -- 'Правый Глаз' или 'Левый Глаз'
    user_id INTEGER,  -- Telegram user_id дежурного
    username TEXT,  -- @username дежурного
    shift_date DATE NOT NULL,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    handover_notes TEXT,  -- Заметки при передаче смены (заменяет "Рабочие задачи")
    checklist_completed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Duty checklist items
CREATE TABLE IF NOT EXISTS duty_checklist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    item_text TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    requires_photo BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Duty checklist progress
CREATE TABLE IF NOT EXISTS duty_checklist_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    checked BOOLEAN DEFAULT 0,
    checked_at TIMESTAMP,
    notes TEXT,
    photo_file_id TEXT,
    FOREIGN KEY (shift_id) REFERENCES duty_shifts(id),
    FOREIGN KEY (item_id) REFERENCES duty_checklist_items(id)
);

-- Insert checklist items based on updated requirements
-- Новый порядок: 1. Ночная смена, 2. Оборудование, 3. Чистота

INSERT INTO duty_checklist_items (category, item_text, description, sort_order, requires_photo) VALUES

-- 1. Ночная смена (в начало списка)
('🌙 Ночная смена', 'Выключить компы', 'Выключить все компьютеры и мониторы', 10, 0),
('🌙 Ночная смена', 'Выключить кондиционеры', 'Выключить все кондиционеры', 20, 0),
('🌙 Ночная смена', 'Выключить свет', 'Выключить освещение в зале', 30, 0),
('🌙 Ночная смена', 'Вентиляция РИО в ночной режим', 'Перевести вентиляцию в ночной режим (только РИО)', 40, 0),

-- 2. Оборудование (упрощенная версия)
('⚡ Оборудование', 'Проверить наличие периферии и ее исправность', 'Проверить мыши, клавиатуры, гарнитуры, веб-камеры', 100, 0),

-- 3. Чистота (в конец списка)
('🧹 Чистота', 'Зал чистый', 'Проверить чистоту игрового зала', 200, 0),
('🧹 Чистота', 'Туалет в порядке', 'Проверить чистоту туалета, наличие бумаги и мыла', 210, 0),
('🧹 Чистота', 'Бар убран', 'Проверить чистоту барной стойки', 220, 0),
('🧹 Чистота', 'Клавиатуры чистые', 'Проверить состояние клавиатур', 230, 0),
('🧹 Чистота', 'Пол чистый', 'Проверить чистоту пола во всех зонах', 240, 0),
('🧹 Чистота', 'Мусор вынесен', 'Проверить, что мусор вынесен', 250, 0);

-- Удаленные категории (по обратной связи):
-- - 📱 Соцсети (удалена)
-- - 📋 Рабочие задачи (заменена на handover_notes)
-- - 💰 Отчёт администратора (удалена)
-- - 🏢 Север (удалена)
-- - 🔐 Безопасность (удалена)
-- - 📦 Товары (удалена)

-- Indexes
CREATE INDEX IF NOT EXISTS idx_duty_shifts_date ON duty_shifts(shift_date DESC);
CREATE INDEX IF NOT EXISTS idx_duty_shifts_person ON duty_shifts(duty_person);
CREATE INDEX IF NOT EXISTS idx_duty_checklist_progress_shift ON duty_checklist_progress(shift_id);
