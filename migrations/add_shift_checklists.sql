-- Миграция: Система чек-листов приема смены
-- Дата: 2025-11-10
-- Описание: Добавляет таблицы для 3 новых чек-листов приема смены

-- ========================================
-- ЧЕК-ЛИСТ #1: РЕЙТИНГ УБОРКИ АДМИНА
-- ========================================
CREATE TABLE IF NOT EXISTS shift_cleaning_rating (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL,
    club TEXT NOT NULL,
    rated_by_admin_id INTEGER NOT NULL,
    previous_admin_id INTEGER,

    -- Оценки (true = хорошо, false = плохо)
    bar_cleaned BOOLEAN NOT NULL,
    hall_cleaned BOOLEAN NOT NULL,

    -- Фото доказательства (обязательно если оценка плохая)
    bar_photo_file_id TEXT,
    hall_photo_file_id TEXT,

    -- Дополнительные заметки
    notes TEXT,

    -- Временные метки
    rated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE CASCADE,
    FOREIGN KEY (rated_by_admin_id) REFERENCES admins(user_id),
    FOREIGN KEY (previous_admin_id) REFERENCES admins(user_id)
);

CREATE INDEX IF NOT EXISTS idx_cleaning_rating_shift ON shift_cleaning_rating(shift_id);
CREATE INDEX IF NOT EXISTS idx_cleaning_rating_admin ON shift_cleaning_rating(previous_admin_id);
CREATE INDEX IF NOT EXISTS idx_cleaning_rating_date ON shift_cleaning_rating(rated_at);


-- ========================================
-- ЧЕК-ЛИСТ #2: ОТЗЫВЫ ОБ УБОРЩИЦЕ
-- ========================================
CREATE TABLE IF NOT EXISTS cleaning_service_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL,
    club TEXT NOT NULL,
    reviewer_admin_id INTEGER NOT NULL,

    -- Оценка 1-5 звёзд
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),

    -- Текстовый отзыв (опционально)
    review_text TEXT,

    -- Фото (опционально)
    photo_file_id TEXT,

    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_admin_id) REFERENCES admins(user_id)
);

CREATE INDEX IF NOT EXISTS idx_cleaning_reviews_club ON cleaning_service_reviews(club);
CREATE INDEX IF NOT EXISTS idx_cleaning_reviews_date ON cleaning_service_reviews(created_at);
CREATE INDEX IF NOT EXISTS idx_cleaning_reviews_rating ON cleaning_service_reviews(rating);


-- ========================================
-- ЧЕК-ЛИСТ #3: ИНВЕНТАРЬ ПРИ ПРИЕМЕ СМЕНЫ
-- ========================================
CREATE TABLE IF NOT EXISTS shift_inventory_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL UNIQUE,
    club TEXT NOT NULL,
    admin_id INTEGER NOT NULL,

    -- Мыши
    mice_on_tables INTEGER NOT NULL DEFAULT 0,
    mice_in_stock INTEGER NOT NULL DEFAULT 0,
    mice_dongles_in_stock INTEGER NOT NULL DEFAULT 0,

    -- Клавиатуры
    keyboards_on_tables INTEGER NOT NULL DEFAULT 0,
    keyboards_in_stock INTEGER NOT NULL DEFAULT 0,

    -- Наушники
    headsets_on_tables INTEGER NOT NULL DEFAULT 0,
    headsets_in_stock INTEGER NOT NULL DEFAULT 0,
    headset_mics_in_stock INTEGER NOT NULL DEFAULT 0,
    headset_cables_in_stock INTEGER NOT NULL DEFAULT 0,

    -- Зарядки (только для Rio)
    chargers_in_stock INTEGER DEFAULT 0,

    -- Статус и временные метки
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comparison_alert_sent BOOLEAN DEFAULT 0,

    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admins(user_id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_shift ON shift_inventory_checklist(shift_id);
CREATE INDEX IF NOT EXISTS idx_inventory_club ON shift_inventory_checklist(club);
CREATE INDEX IF NOT EXISTS idx_inventory_date ON shift_inventory_checklist(completed_at);


-- ========================================
-- СИСТЕМА НАПОМИНАНИЙ
-- ========================================
CREATE TABLE IF NOT EXISTS shift_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL,
    reminder_type TEXT NOT NULL,  -- 'inventory', 'cleaning_rating', 'shift_not_opened'
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    next_reminder_at TIMESTAMP,
    is_resolved BOOLEAN DEFAULT 0,

    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reminders_shift ON shift_reminders(shift_id);
CREATE INDEX IF NOT EXISTS idx_reminders_type ON shift_reminders(reminder_type);
CREATE INDEX IF NOT EXISTS idx_reminders_next ON shift_reminders(next_reminder_at);
CREATE INDEX IF NOT EXISTS idx_reminders_resolved ON shift_reminders(is_resolved);


-- ========================================
-- ШТРАФНАЯ СИСТЕМА
-- ========================================
CREATE TABLE IF NOT EXISTS cleaning_penalties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    rating_id INTEGER NOT NULL,
    penalty_amount REAL DEFAULT 0,
    reason TEXT,
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid BOOLEAN DEFAULT 0,

    FOREIGN KEY (admin_id) REFERENCES admins(user_id),
    FOREIGN KEY (rating_id) REFERENCES shift_cleaning_rating(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_penalties_admin ON cleaning_penalties(admin_id);
CREATE INDEX IF NOT EXISTS idx_penalties_paid ON cleaning_penalties(paid);
