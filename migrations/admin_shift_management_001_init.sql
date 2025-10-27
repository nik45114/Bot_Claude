-- Admin & Shift Management Migration
-- Добавляет таблицы для расширенного управления админами и контроля смен

-- Создаем таблицу для расширенного управления админами
CREATE TABLE IF NOT EXISTS admin_management (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    full_name TEXT,
    role TEXT DEFAULT 'staff',
    permissions TEXT, -- JSON строка с правами
    added_by INTEGER,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    notes TEXT,
    shift_count INTEGER DEFAULT 0,
    last_shift_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создаем таблицу для отслеживания активности админов
CREATE TABLE IF NOT EXISTS admin_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT, -- JSON с деталями
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES admin_management(user_id)
);

-- Создаем таблицу для детального контроля смен
CREATE TABLE IF NOT EXISTS shift_control (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    club_name TEXT NOT NULL,
    shift_date DATE NOT NULL,
    shift_time TEXT NOT NULL, -- 'morning' or 'evening'
    
    -- Данные смены
    fact_cash REAL DEFAULT 0,
    fact_card REAL DEFAULT 0,
    qr_amount REAL DEFAULT 0,
    card2_amount REAL DEFAULT 0,
    safe_cash_end REAL DEFAULT 0,
    box_cash_end REAL DEFAULT 0,
    
    -- Фото и OCR
    photo_file_id TEXT,
    photo_path TEXT,
    ocr_text TEXT,
    ocr_numbers TEXT, -- JSON с извлеченными числами
    ocr_verified BOOLEAN DEFAULT 0,
    ocr_confidence REAL DEFAULT 0,
    
    -- Статус и проверка
    status TEXT DEFAULT 'pending', -- pending, verified, rejected
    verified_by INTEGER,
    verified_at TIMESTAMP,
    verification_notes TEXT,
    
    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (admin_id) REFERENCES admin_management(user_id),
    FOREIGN KEY (verified_by) REFERENCES admin_management(user_id)
);

-- Создаем таблицу для истории изменений статуса смен
CREATE TABLE IF NOT EXISTS shift_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT,
    changed_by INTEGER NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shift_id) REFERENCES shift_control(id),
    FOREIGN KEY (changed_by) REFERENCES admin_management(user_id)
);

-- Создаем индексы для производительности
CREATE INDEX IF NOT EXISTS idx_admin_management_user_id ON admin_management(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_management_role ON admin_management(role);
CREATE INDEX IF NOT EXISTS idx_admin_management_active ON admin_management(is_active);
CREATE INDEX IF NOT EXISTS idx_admin_management_updated_at ON admin_management(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_activity_admin_id ON admin_activity(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_activity_timestamp ON admin_activity(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_shift_control_admin ON shift_control(admin_id);
CREATE INDEX IF NOT EXISTS idx_shift_control_date ON shift_control(shift_date);
CREATE INDEX IF NOT EXISTS idx_shift_control_status ON shift_control(status);
CREATE INDEX IF NOT EXISTS idx_shift_control_club ON shift_control(club_name);
CREATE INDEX IF NOT EXISTS idx_shift_control_created_at ON shift_control(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shift_status_history_shift_id ON shift_status_history(shift_id);
CREATE INDEX IF NOT EXISTS idx_shift_status_history_timestamp ON shift_status_history(timestamp DESC);

-- Синхронизируем существующих админов
INSERT OR IGNORE INTO admin_management (user_id, username, full_name, added_by, is_active, created_at)
SELECT user_id, username, full_name, added_by, is_active, created_at
FROM admins 
WHERE is_active = 1;
