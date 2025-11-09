-- Миграция для добавления системы контроля от проверяющего аккаунта
-- Создано: 2025-11-08
-- Описание: Добавляет таблицы для панели контролера и управления проверками

-- Таблица действий контролера
CREATE TABLE IF NOT EXISTS controller_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id INTEGER NOT NULL, -- ID контролера (Telegram user_id)
    shift_id INTEGER, -- ID смены (может быть NULL для общих действий)
    admin_id INTEGER, -- ID админа, к которому относится действие
    action_type TEXT NOT NULL, -- 'photo_request', 'remark', 'force_close', 'view_checklist', 'check_in'
    message TEXT, -- текст сообщения/запроса/замечания
    photo_file_id TEXT, -- file_id ответного фото от админа
    status TEXT DEFAULT 'pending', -- 'pending', 'completed', 'cancelled'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE SET NULL,
    FOREIGN KEY (admin_id) REFERENCES admins(user_id) ON DELETE CASCADE
);

-- Таблица замечаний контролера
CREATE TABLE IF NOT EXISTS controller_remarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id INTEGER NOT NULL, -- ID контролера
    shift_id INTEGER, -- ID смены (может быть NULL)
    admin_id INTEGER NOT NULL, -- админ, которому адресовано замечание
    club TEXT, -- клуб ('rio', 'sever')
    remark_type TEXT NOT NULL, -- 'cleanliness', 'equipment', 'service', 'inventory', 'other'
    severity TEXT DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    description TEXT NOT NULL, -- описание замечания
    photo_file_id TEXT, -- file_id фото проблемы
    status TEXT DEFAULT 'open', -- 'open', 'acknowledged', 'resolved', 'disputed'
    resolution_notes TEXT, -- комментарий админа при разрешении
    resolution_photo_file_id TEXT, -- фото исправленной проблемы
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP, -- когда админ подтвердил получение
    resolved_at TIMESTAMP, -- когда проблема решена
    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE SET NULL,
    FOREIGN KEY (admin_id) REFERENCES admins(user_id) ON DELETE CASCADE
);

-- Таблица запросов фото от контролера
CREATE TABLE IF NOT EXISTS controller_photo_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id INTEGER NOT NULL,
    shift_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    request_type TEXT NOT NULL, -- 'club_state', 'specific_area', 'equipment', 'cash_register', 'custom'
    request_description TEXT, -- что именно нужно сфотографировать
    photo_file_id TEXT, -- file_id полученного фото
    status TEXT DEFAULT 'pending', -- 'pending', 'received', 'expired'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    received_at TIMESTAMP,
    expires_at TIMESTAMP, -- срок выполнения запроса (например, через 15 минут)
    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES admins(user_id) ON DELETE CASCADE
);

-- Таблица истории проверок клуба контролером
CREATE TABLE IF NOT EXISTS controller_inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id INTEGER NOT NULL,
    shift_id INTEGER,
    club TEXT NOT NULL, -- 'rio', 'sever'
    inspection_type TEXT DEFAULT 'routine', -- 'routine', 'spot_check', 'complaint_followup'
    overall_rating INTEGER, -- оценка от 1 до 5
    notes TEXT, -- общие заметки
    issues_found INTEGER DEFAULT 0, -- количество найденных проблем
    photos_count INTEGER DEFAULT 0, -- количество фото
    duration_minutes INTEGER, -- длительность проверки в минутах
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE SET NULL
);

-- Таблица уведомлений для админов от контролера
CREATE TABLE IF NOT EXISTS controller_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    notification_type TEXT NOT NULL, -- 'reminder', 'warning', 'praise', 'info'
    message TEXT NOT NULL,
    priority TEXT DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    is_read BOOLEAN DEFAULT 0,
    related_remark_id INTEGER, -- связанное замечание
    related_action_id INTEGER, -- связанное действие
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES admins(user_id) ON DELETE CASCADE,
    FOREIGN KEY (related_remark_id) REFERENCES controller_remarks(id) ON DELETE CASCADE,
    FOREIGN KEY (related_action_id) REFERENCES controller_actions(id) ON DELETE CASCADE
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_controller_actions_controller ON controller_actions(controller_id);
CREATE INDEX IF NOT EXISTS idx_controller_actions_shift ON controller_actions(shift_id);
CREATE INDEX IF NOT EXISTS idx_controller_actions_admin ON controller_actions(admin_id);
CREATE INDEX IF NOT EXISTS idx_controller_actions_status ON controller_actions(status);
CREATE INDEX IF NOT EXISTS idx_controller_actions_type ON controller_actions(action_type);

CREATE INDEX IF NOT EXISTS idx_controller_remarks_controller ON controller_remarks(controller_id);
CREATE INDEX IF NOT EXISTS idx_controller_remarks_shift ON controller_remarks(shift_id);
CREATE INDEX IF NOT EXISTS idx_controller_remarks_admin ON controller_remarks(admin_id);
CREATE INDEX IF NOT EXISTS idx_controller_remarks_status ON controller_remarks(status);
CREATE INDEX IF NOT EXISTS idx_controller_remarks_severity ON controller_remarks(severity);
CREATE INDEX IF NOT EXISTS idx_controller_remarks_club ON controller_remarks(club);

CREATE INDEX IF NOT EXISTS idx_photo_requests_controller ON controller_photo_requests(controller_id);
CREATE INDEX IF NOT EXISTS idx_photo_requests_shift ON controller_photo_requests(shift_id);
CREATE INDEX IF NOT EXISTS idx_photo_requests_admin ON controller_photo_requests(admin_id);
CREATE INDEX IF NOT EXISTS idx_photo_requests_status ON controller_photo_requests(status);

CREATE INDEX IF NOT EXISTS idx_inspections_controller ON controller_inspections(controller_id);
CREATE INDEX IF NOT EXISTS idx_inspections_club ON controller_inspections(club);
CREATE INDEX IF NOT EXISTS idx_inspections_shift ON controller_inspections(shift_id);

CREATE INDEX IF NOT EXISTS idx_notifications_admin ON controller_notifications(admin_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON controller_notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_priority ON controller_notifications(priority);
