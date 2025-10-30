-- Таблица для хранения закрытых смен с полными данными
CREATE TABLE IF NOT EXISTS finmon_shifts (
    shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    club TEXT NOT NULL,
    shift_type TEXT NOT NULL, -- 'morning' или 'evening'
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP NOT NULL,

    -- Выручка
    cash_revenue REAL DEFAULT 0, -- наличка факт
    card_revenue REAL DEFAULT 0, -- карта факт
    qr_revenue REAL DEFAULT 0, -- QR
    card2_revenue REAL DEFAULT 0, -- карта 2
    total_revenue REAL DEFAULT 0, -- общая выручка

    -- Остатки касс
    safe_cash_start REAL DEFAULT 0, -- сейф начало
    safe_cash_end REAL DEFAULT 0, -- сейф конец
    box_cash_start REAL DEFAULT 0, -- бокс начало
    box_cash_end REAL DEFAULT 0, -- бокс конец

    -- Расходы
    total_expenses REAL DEFAULT 0, -- общие расходы (сумма из shift_expenses)

    -- Выручка по категориям
    bar_revenue REAL DEFAULT 0,
    hookah_revenue REAL DEFAULT 0,
    kitchen_revenue REAL DEFAULT 0,

    -- Z-отчеты (фото чеков)
    z_report_cash_photo TEXT, -- path или file_id фото z-отчета наличка
    z_report_card_photo TEXT, -- path или file_id фото z-отчета карта
    z_report_qr_photo TEXT, -- path или file_id фото z-отчета QR
    z_report_card2_photo TEXT, -- path или file_id фото z-отчета карта 2

    -- OCR данные из чеков
    z_report_cash_ocr TEXT, -- JSON с распознанными данными
    z_report_card_ocr TEXT,
    z_report_qr_ocr TEXT,
    z_report_card2_ocr TEXT,

    -- Флаги отсутствия выручки
    cash_disabled BOOLEAN DEFAULT 0, -- касса наличных не работала
    card_disabled BOOLEAN DEFAULT 0, -- касса карт не работала
    qr_disabled BOOLEAN DEFAULT 0, -- QR не работал
    card2_disabled BOOLEAN DEFAULT 0, -- карта 2 не работала

    -- Подтверждение
    confirmed_by INTEGER, -- кто подтвердил смену
    confirmed_at TIMESTAMP,

    -- Дополнительно
    notes TEXT, -- примечания
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (admin_id) REFERENCES admins(user_id),
    FOREIGN KEY (confirmed_by) REFERENCES admins(user_id)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_finmon_shifts_admin ON finmon_shifts(admin_id);
CREATE INDEX IF NOT EXISTS idx_finmon_shifts_club ON finmon_shifts(club);
CREATE INDEX IF NOT EXISTS idx_finmon_shifts_closed_at ON finmon_shifts(closed_at);
CREATE INDEX IF NOT EXISTS idx_finmon_shifts_club_date ON finmon_shifts(club, closed_at);
