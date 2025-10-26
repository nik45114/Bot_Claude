-- FinMon Module Database Schema
-- Financial Monitoring for Computer Clubs

-- Таблица клубов
CREATE TABLE IF NOT EXISTS finmon_clubs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица балансов касс (по одной записи на клуб)
CREATE TABLE IF NOT EXISTS finmon_balances (
    club_id INTEGER PRIMARY KEY,
    official REAL DEFAULT 0,
    box REAL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (club_id) REFERENCES finmon_clubs(id)
);

-- Таблица смен
CREATE TABLE IF NOT EXISTS finmon_shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    chat_id INTEGER,
    club_id INTEGER NOT NULL,
    shift_date DATE NOT NULL,
    shift_time TEXT NOT NULL CHECK(shift_time IN ('morning', 'evening')),
    
    -- Выручка
    fact_cash REAL DEFAULT 0,
    fact_card REAL DEFAULT 0,
    qr REAL DEFAULT 0,
    card2 REAL DEFAULT 0,
    
    -- Кассы (конечные балансы после смены)
    safe_cash_end REAL DEFAULT 0,
    box_cash_end REAL DEFAULT 0,
    goods_cash REAL DEFAULT 0,
    
    -- Инвентарь
    joysticks_total INTEGER DEFAULT 0,
    joysticks_in_repair INTEGER DEFAULT 0,
    joysticks_need_repair INTEGER DEFAULT 0,
    games_count INTEGER DEFAULT 0,
    
    -- Дежурный
    duty_name TEXT,
    duty_username TEXT,
    
    -- Дельты (изменения балансов)
    delta_official REAL DEFAULT 0,
    delta_box REAL DEFAULT 0,
    
    -- Кто создал
    created_by INTEGER,
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (club_id) REFERENCES finmon_clubs(id)
);

-- Таблица движений (истории изменений балансов)
CREATE TABLE IF NOT EXISTS finmon_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    club_id INTEGER NOT NULL,
    shift_id INTEGER,
    delta_official REAL DEFAULT 0,
    delta_box REAL DEFAULT 0,
    FOREIGN KEY (club_id) REFERENCES finmon_clubs(id),
    FOREIGN KEY (shift_id) REFERENCES finmon_shifts(id)
);

-- Таблица маппинга чатов на клубы
CREATE TABLE IF NOT EXISTS finmon_chat_club_map (
    chat_id INTEGER PRIMARY KEY,
    club_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (club_id) REFERENCES finmon_clubs(id)
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_finmon_shifts_club_id ON finmon_shifts(club_id);
CREATE INDEX IF NOT EXISTS idx_finmon_shifts_ts ON finmon_shifts(ts);
CREATE INDEX IF NOT EXISTS idx_finmon_movements_club_id ON finmon_movements(club_id);
CREATE INDEX IF NOT EXISTS idx_finmon_movements_ts ON finmon_movements(ts);

-- Начальные данные - клубы
INSERT OR IGNORE INTO finmon_clubs (id, name) VALUES
    (1, 'Рио'),
    (2, 'Север');

-- Инициализация балансов
INSERT OR IGNORE INTO finmon_balances (club_id, official, box) VALUES
    (1, 0, 0),
    (2, 0, 0);

-- Начальные маппинги чатов
-- 5329834944 → Рио
-- 5992731922 → Север
INSERT OR IGNORE INTO finmon_chat_club_map (chat_id, club_id) VALUES
    (5329834944, 1),
    (5992731922, 2);
