-- FinMon Module Database Schema
-- Financial Monitoring for Computer Clubs

-- Таблица клубов
CREATE TABLE IF NOT EXISTS finmon_clubs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('official', 'box')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица смен
CREATE TABLE IF NOT EXISTS finmon_shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    shift_date DATE NOT NULL,
    shift_time TEXT NOT NULL CHECK(shift_time IN ('morning', 'evening')),
    admin_tg_id INTEGER NOT NULL,
    admin_username TEXT,
    
    -- Выручка
    fact_cash REAL DEFAULT 0,
    fact_card REAL DEFAULT 0,
    qr REAL DEFAULT 0,
    card2 REAL DEFAULT 0,
    
    -- Кассы
    safe_cash_end REAL DEFAULT 0,
    box_cash_end REAL DEFAULT 0,
    goods_cash REAL DEFAULT 0,
    
    -- Расходы
    compensations REAL DEFAULT 0,
    salary_payouts REAL DEFAULT 0,
    other_expenses REAL DEFAULT 0,
    
    -- Инвентарь
    joysticks_total INTEGER DEFAULT 0,
    joysticks_in_repair INTEGER DEFAULT 0,
    joysticks_need_repair INTEGER DEFAULT 0,
    games_count INTEGER DEFAULT 0,
    
    -- Хозяйство
    toilet_paper BOOLEAN DEFAULT 0,
    paper_towels BOOLEAN DEFAULT 0,
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (club_id) REFERENCES finmon_clubs(id)
);

-- Таблица балансов касс
CREATE TABLE IF NOT EXISTS finmon_cashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    cash_type TEXT NOT NULL CHECK(cash_type IN ('official', 'box')),
    balance REAL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (club_id) REFERENCES finmon_clubs(id),
    UNIQUE(club_id, cash_type)
);

-- Начальные данные - 4 клуба (2 клуба x 2 типа касс)
INSERT OR IGNORE INTO finmon_clubs (id, name, type) VALUES
    (1, 'Рио', 'official'),
    (2, 'Рио', 'box'),
    (3, 'Мичуринская', 'official'),
    (4, 'Мичуринская', 'box');

-- Инициализация балансов для всех клубов
INSERT OR IGNORE INTO finmon_cashes (club_id, cash_type, balance) VALUES
    (1, 'official', 0),
    (2, 'box', 0),
    (3, 'official', 0),
    (4, 'box', 0);
