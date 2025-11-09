-- Миграция для добавления системы чек-листов приема смены
-- Создано: 2025-11-08
-- Описание: Добавляет таблицы для чек-листов проверки клуба при открытии смены

-- Таблица с шаблонами пунктов чек-листа
CREATE TABLE IF NOT EXISTS shift_checklist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL, -- 'equipment', 'cleanliness', 'inventory', 'documents', 'safety'
    item_name TEXT NOT NULL,
    description TEXT, -- дополнительное описание пункта
    is_required BOOLEAN DEFAULT 1, -- обязательный ли пункт
    requires_photo BOOLEAN DEFAULT 0, -- требуется ли фото
    sort_order INTEGER NOT NULL, -- порядок отображения
    is_active BOOLEAN DEFAULT 1, -- активен ли пункт
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица с ответами админов на чек-лист
CREATE TABLE IF NOT EXISTS shift_checklist_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL, -- ID смены из active_shifts
    item_id INTEGER NOT NULL, -- ID пункта из shift_checklist_items
    status TEXT NOT NULL, -- 'ok', 'issue', 'skipped'
    photo_file_id TEXT, -- file_id фото из Telegram (если есть)
    notes TEXT, -- комментарий админа
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES shift_checklist_items(id) ON DELETE CASCADE
);

-- Таблица для отслеживания прогресса чек-листа
CREATE TABLE IF NOT EXISTS shift_checklist_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL UNIQUE, -- ID смены
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    is_completed BOOLEAN DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    checked_items INTEGER DEFAULT 0,
    issues_count INTEGER DEFAULT 0, -- количество проблем
    last_reminder_at TIMESTAMP, -- когда последний раз отправляли напоминание
    FOREIGN KEY (shift_id) REFERENCES active_shifts(id) ON DELETE CASCADE
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_checklist_responses_shift ON shift_checklist_responses(shift_id);
CREATE INDEX IF NOT EXISTS idx_checklist_responses_item ON shift_checklist_responses(item_id);
CREATE INDEX IF NOT EXISTS idx_checklist_progress_shift ON shift_checklist_progress(shift_id);
CREATE INDEX IF NOT EXISTS idx_checklist_items_category ON shift_checklist_items(category, sort_order);
CREATE INDEX IF NOT EXISTS idx_checklist_items_active ON shift_checklist_items(is_active);

-- Вставка стандартных пунктов чек-листа

-- Категория: Оборудование (equipment)
INSERT INTO shift_checklist_items (category, item_name, description, is_required, requires_photo, sort_order) VALUES
('equipment', 'Все ПК включены и работают', 'Проверить запуск всех игровых компьютеров', 1, 0, 1),
('equipment', 'Геймпады заряжены', 'Проверить заряд всех геймпадов (минимум 50%)', 1, 0, 2),
('equipment', 'VR-оборудование на местах', 'Шлемы, контроллеры, датчики - все на местах и работают', 1, 0, 3),
('equipment', 'Клавиатуры и мыши исправны', 'Проверить работоспособность периферии', 1, 0, 4),
('equipment', 'Мониторы работают', 'Проверить все мониторы на битые пиксели и артефакты', 1, 0, 5),
('equipment', 'Сетевое оборудование', 'Роутер, свитчи - все работает, интернет есть', 1, 0, 6);

-- Категория: Чистота (cleanliness)
INSERT INTO shift_checklist_items (category, item_name, description, is_required, requires_photo, sort_order) VALUES
('cleanliness', 'Столы и рабочие места чистые', 'Протереть все столы, убрать мусор', 1, 0, 10),
('cleanliness', 'Пол чистый', 'Подмести/пропылесосить пол в игровой зоне', 1, 0, 11),
('cleanliness', 'Туалет чистый', 'Проверить чистоту туалета, наличие бумаги и мыла', 1, 0, 12),
('cleanliness', 'Барная зона в порядке', 'Чистая барная стойка, посуда помыта', 1, 0, 13),
('cleanliness', 'Мусорные корзины опустошены', 'Вынести мусор, поставить новые пакеты', 1, 0, 14);

-- Категория: Товары и запасы (inventory)
INSERT INTO shift_checklist_items (category, item_name, description, is_required, requires_photo, sort_order) VALUES
('inventory', 'Напитки в наличии', 'Проверить наличие популярных напитков в холодильнике', 1, 0, 20),
('inventory', 'Снеки в наличии', 'Проверить наличие чипсов, батончиков и т.д.', 1, 0, 21),
('inventory', 'Кальянные принадлежности', 'Табак, уголь, фольга - достаточное количество', 0, 0, 22),
('inventory', 'Расходники', 'Салфетки, стаканы, трубочки в наличии', 1, 0, 23);

-- Категория: Документы и касса (documents)
INSERT INTO shift_checklist_items (category, item_name, description, is_required, requires_photo, sort_order) VALUES
('documents', 'Касса работает', 'Проверить работу всех касс (наличные, карта, QR)', 1, 0, 30),
('documents', 'Остаток в сейфе сверен', 'Пересчитать деньги в сейфе, сверить с предыдущей сменой', 1, 0, 31),
('documents', 'Остаток в боксе сверен', 'Пересчитать деньги в боксе (рабочая касса)', 1, 0, 32);

-- Категория: Безопасность (safety)
INSERT INTO shift_checklist_items (category, item_name, description, is_required, requires_photo, sort_order) VALUES
('safety', 'Проверка пожарной сигнализации', 'Индикаторы горят, система в норме', 1, 0, 40),
('safety', 'Огнетушители на местах', 'Проверить наличие огнетушителей и сроки годности', 1, 0, 41),
('safety', 'Аварийные выходы свободны', 'Эвакуационные пути не заблокированы', 1, 0, 42),
('safety', 'Видеонаблюдение работает', 'Проверить работу камер видеонаблюдения', 0, 0, 43);
