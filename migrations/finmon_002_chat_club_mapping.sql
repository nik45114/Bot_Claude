-- FinMon Chat-Club Mapping Migration
-- Adds table for mapping Telegram chat IDs to clubs and adds "Север" club

-- Таблица маппинга чатов на клубы
CREATE TABLE IF NOT EXISTS finmon_chat_club_map (
    chat_id INTEGER PRIMARY KEY,
    club_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (club_id) REFERENCES finmon_clubs(id)
);

-- Добавляем клуб "Север" если его еще нет
INSERT OR IGNORE INTO finmon_clubs (id, name, type) VALUES
    (5, 'Север', 'official'),
    (6, 'Север', 'box');

-- Инициализация балансов для клуба "Север"
INSERT OR IGNORE INTO finmon_cashes (club_id, cash_type, balance) VALUES
    (5, 'official', 0),
    (6, 'box', 0);

-- Начальные маппинги (как указано в задаче)
-- 5329834944 → Рио (official)
-- 5992731922 → Север (official)
INSERT OR IGNORE INTO finmon_chat_club_map (chat_id, club_id) VALUES
    (5329834944, 1),  -- Рио official
    (5992731922, 5);  -- Север official
