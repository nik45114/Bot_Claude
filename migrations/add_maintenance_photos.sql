-- Добавление таблицы для фото-отчётов по обслуживанию
-- Дата: 2025-11-11

-- Таблица для хранения фото-отчётов
CREATE TABLE IF NOT EXISTS maintenance_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    photo_file_id TEXT NOT NULL,  -- Telegram file_id для фото
    caption TEXT,  -- Опциональный комментарий к фото
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id) REFERENCES maintenance_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (equipment_id) REFERENCES equipment_inventory(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admins(user_id) ON DELETE CASCADE
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_maintenance_photos_task ON maintenance_photos(task_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_photos_equipment ON maintenance_photos(equipment_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_photos_admin ON maintenance_photos(admin_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_photos_date ON maintenance_photos(uploaded_at);

-- Добавляем поле для хранения file_id фото в таблицу maintenance_tasks (для обратной совместимости)
ALTER TABLE maintenance_tasks ADD COLUMN photo_file_id TEXT;
