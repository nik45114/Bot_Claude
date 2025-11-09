-- Migration: Create maintenance tasks system
-- Date: 2025-11-08
-- Description: System for tracking equipment maintenance tasks (cleaning keyboards, mice, dusting PCs)

-- Типы оборудования и их инвентарные номера
CREATE TABLE IF NOT EXISTS equipment_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club TEXT NOT NULL,  -- 'rio' или 'sever'
    equipment_type TEXT NOT NULL,  -- 'pc', 'keyboard', 'mouse'
    inventory_number TEXT NOT NULL,  -- Инвентарный номер (для периферии) или номер ПК
    pc_number INTEGER,  -- Номер компьютера (1-23 для РИО, 1-21 для СЕВЕРА)
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(club, equipment_type, inventory_number)
);

-- Типы задач обслуживания
CREATE TABLE IF NOT EXISTS maintenance_task_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    task_description TEXT,
    frequency_days INTEGER NOT NULL,  -- Периодичность в днях (30 для клавиатур/мышей, 60 для продувки)
    equipment_type TEXT NOT NULL,  -- 'pc', 'keyboard', 'mouse'
    requires_photo BOOLEAN DEFAULT 1,
    is_active BOOLEAN DEFAULT 1
);

-- Задачи обслуживания (назначенные администраторам)
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    club TEXT NOT NULL,
    equipment_id INTEGER NOT NULL,
    task_type_id INTEGER NOT NULL,
    assigned_date DATE NOT NULL,
    due_date DATE NOT NULL,
    status TEXT DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'overdue'
    completed_date TIMESTAMP,
    photo_file_id TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipment_id) REFERENCES equipment_inventory(id),
    FOREIGN KEY (task_type_id) REFERENCES maintenance_task_types(id)
);

-- История выполненных задач
CREATE TABLE IF NOT EXISTS maintenance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,
    task_type_id INTEGER NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    photo_file_id TEXT,
    notes TEXT,
    FOREIGN KEY (task_id) REFERENCES maintenance_tasks(id),
    FOREIGN KEY (equipment_id) REFERENCES equipment_inventory(id),
    FOREIGN KEY (task_type_id) REFERENCES maintenance_task_types(id)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_maintenance_tasks_admin ON maintenance_tasks(admin_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_tasks_status ON maintenance_tasks(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_tasks_due_date ON maintenance_tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_equipment_inventory_club ON equipment_inventory(club);

-- Вставка типов задач
INSERT INTO maintenance_task_types (task_name, task_description, frequency_days, equipment_type, requires_photo) VALUES
('Чистка клавиатуры', 'Очистка клавиатуры от пыли и грязи', 30, 'keyboard', 1),
('Чистка мыши', 'Очистка компьютерной мыши', 30, 'mouse', 1),
('Продувка ПК', 'Продувка системного блока от пыли', 60, 'pc', 1);

-- Вставка инвентаря для РИО (23 ПК)
INSERT INTO equipment_inventory (club, equipment_type, inventory_number, pc_number) VALUES
('rio', 'pc', 'PC-RIO-01', 1),
('rio', 'pc', 'PC-RIO-02', 2),
('rio', 'pc', 'PC-RIO-03', 3),
('rio', 'pc', 'PC-RIO-04', 4),
('rio', 'pc', 'PC-RIO-05', 5),
('rio', 'pc', 'PC-RIO-06', 6),
('rio', 'pc', 'PC-RIO-07', 7),
('rio', 'pc', 'PC-RIO-08', 8),
('rio', 'pc', 'PC-RIO-09', 9),
('rio', 'pc', 'PC-RIO-10', 10),
('rio', 'pc', 'PC-RIO-11', 11),
('rio', 'pc', 'PC-RIO-12', 12),
('rio', 'pc', 'PC-RIO-13', 13),
('rio', 'pc', 'PC-RIO-14', 14),
('rio', 'pc', 'PC-RIO-15', 15),
('rio', 'pc', 'PC-RIO-16', 16),
('rio', 'pc', 'PC-RIO-17', 17),
('rio', 'pc', 'PC-RIO-18', 18),
('rio', 'pc', 'PC-RIO-19', 19),
('rio', 'pc', 'PC-RIO-20', 20),
('rio', 'pc', 'PC-RIO-21', 21),
('rio', 'pc', 'PC-RIO-22', 22),
('rio', 'pc', 'PC-RIO-23', 23);

-- Вставка инвентаря для СЕВЕРА (21 ПК)
INSERT INTO equipment_inventory (club, equipment_type, inventory_number, pc_number) VALUES
('sever', 'pc', 'PC-SEV-01', 1),
('sever', 'pc', 'PC-SEV-02', 2),
('sever', 'pc', 'PC-SEV-03', 3),
('sever', 'pc', 'PC-SEV-04', 4),
('sever', 'pc', 'PC-SEV-05', 5),
('sever', 'pc', 'PC-SEV-06', 6),
('sever', 'pc', 'PC-SEV-07', 7),
('sever', 'pc', 'PC-SEV-08', 8),
('sever', 'pc', 'PC-SEV-09', 9),
('sever', 'pc', 'PC-SEV-10', 10),
('sever', 'pc', 'PC-SEV-11', 11),
('sever', 'pc', 'PC-SEV-12', 12),
('sever', 'pc', 'PC-SEV-13', 13),
('sever', 'pc', 'PC-SEV-14', 14),
('sever', 'pc', 'PC-SEV-15', 15),
('sever', 'pc', 'PC-SEV-16', 16),
('sever', 'pc', 'PC-SEV-17', 17),
('sever', 'pc', 'PC-SEV-18', 18),
('sever', 'pc', 'PC-SEV-19', 19),
('sever', 'pc', 'PC-SEV-20', 20),
('sever', 'pc', 'PC-SEV-21', 21);

-- Клавиатуры и мыши для РИО
INSERT INTO equipment_inventory (club, equipment_type, inventory_number, pc_number) VALUES
('rio', 'keyboard', 'KB-RIO-01', 1),
('rio', 'keyboard', 'KB-RIO-02', 2),
('rio', 'keyboard', 'KB-RIO-03', 3),
('rio', 'keyboard', 'KB-RIO-04', 4),
('rio', 'keyboard', 'KB-RIO-05', 5),
('rio', 'keyboard', 'KB-RIO-06', 6),
('rio', 'keyboard', 'KB-RIO-07', 7),
('rio', 'keyboard', 'KB-RIO-08', 8),
('rio', 'keyboard', 'KB-RIO-09', 9),
('rio', 'keyboard', 'KB-RIO-10', 10),
('rio', 'keyboard', 'KB-RIO-11', 11),
('rio', 'keyboard', 'KB-RIO-12', 12),
('rio', 'keyboard', 'KB-RIO-13', 13),
('rio', 'keyboard', 'KB-RIO-14', 14),
('rio', 'keyboard', 'KB-RIO-15', 15),
('rio', 'keyboard', 'KB-RIO-16', 16),
('rio', 'keyboard', 'KB-RIO-17', 17),
('rio', 'keyboard', 'KB-RIO-18', 18),
('rio', 'keyboard', 'KB-RIO-19', 19),
('rio', 'keyboard', 'KB-RIO-20', 20),
('rio', 'keyboard', 'KB-RIO-21', 21),
('rio', 'keyboard', 'KB-RIO-22', 22),
('rio', 'keyboard', 'KB-RIO-23', 23),
('rio', 'mouse', 'MS-RIO-01', 1),
('rio', 'mouse', 'MS-RIO-02', 2),
('rio', 'mouse', 'MS-RIO-03', 3),
('rio', 'mouse', 'MS-RIO-04', 4),
('rio', 'mouse', 'MS-RIO-05', 5),
('rio', 'mouse', 'MS-RIO-06', 6),
('rio', 'mouse', 'MS-RIO-07', 7),
('rio', 'mouse', 'MS-RIO-08', 8),
('rio', 'mouse', 'MS-RIO-09', 9),
('rio', 'mouse', 'MS-RIO-10', 10),
('rio', 'mouse', 'MS-RIO-11', 11),
('rio', 'mouse', 'MS-RIO-12', 12),
('rio', 'mouse', 'MS-RIO-13', 13),
('rio', 'mouse', 'MS-RIO-14', 14),
('rio', 'mouse', 'MS-RIO-15', 15),
('rio', 'mouse', 'MS-RIO-16', 16),
('rio', 'mouse', 'MS-RIO-17', 17),
('rio', 'mouse', 'MS-RIO-18', 18),
('rio', 'mouse', 'MS-RIO-19', 19),
('rio', 'mouse', 'MS-RIO-20', 20),
('rio', 'mouse', 'MS-RIO-21', 21),
('rio', 'mouse', 'MS-RIO-22', 22),
('rio', 'mouse', 'MS-RIO-23', 23);

-- Клавиатуры и мыши для СЕВЕРА
INSERT INTO equipment_inventory (club, equipment_type, inventory_number, pc_number) VALUES
('sever', 'keyboard', 'KB-SEV-01', 1),
('sever', 'keyboard', 'KB-SEV-02', 2),
('sever', 'keyboard', 'KB-SEV-03', 3),
('sever', 'keyboard', 'KB-SEV-04', 4),
('sever', 'keyboard', 'KB-SEV-05', 5),
('sever', 'keyboard', 'KB-SEV-06', 6),
('sever', 'keyboard', 'KB-SEV-07', 7),
('sever', 'keyboard', 'KB-SEV-08', 8),
('sever', 'keyboard', 'KB-SEV-09', 9),
('sever', 'keyboard', 'KB-SEV-10', 10),
('sever', 'keyboard', 'KB-SEV-11', 11),
('sever', 'keyboard', 'KB-SEV-12', 12),
('sever', 'keyboard', 'KB-SEV-13', 13),
('sever', 'keyboard', 'KB-SEV-14', 14),
('sever', 'keyboard', 'KB-SEV-15', 15),
('sever', 'keyboard', 'KB-SEV-16', 16),
('sever', 'keyboard', 'KB-SEV-17', 17),
('sever', 'keyboard', 'KB-SEV-18', 18),
('sever', 'keyboard', 'KB-SEV-19', 19),
('sever', 'keyboard', 'KB-SEV-20', 20),
('sever', 'keyboard', 'KB-SEV-21', 21),
('sever', 'mouse', 'MS-SEV-01', 1),
('sever', 'mouse', 'MS-SEV-02', 2),
('sever', 'mouse', 'MS-SEV-03', 3),
('sever', 'mouse', 'MS-SEV-04', 4),
('sever', 'mouse', 'MS-SEV-05', 5),
('sever', 'mouse', 'MS-SEV-06', 6),
('sever', 'mouse', 'MS-SEV-07', 7),
('sever', 'mouse', 'MS-SEV-08', 8),
('sever', 'mouse', 'MS-SEV-09', 9),
('sever', 'mouse', 'MS-SEV-10', 10),
('sever', 'mouse', 'MS-SEV-11', 11),
('sever', 'mouse', 'MS-SEV-12', 12),
('sever', 'mouse', 'MS-SEV-13', 13),
('sever', 'mouse', 'MS-SEV-14', 14),
('sever', 'mouse', 'MS-SEV-15', 15),
('sever', 'mouse', 'MS-SEV-16', 16),
('sever', 'mouse', 'MS-SEV-17', 17),
('sever', 'mouse', 'MS-SEV-18', 18),
('sever', 'mouse', 'MS-SEV-19', 19),
('sever', 'mouse', 'MS-SEV-20', 20),
('sever', 'mouse', 'MS-SEV-21', 21);
