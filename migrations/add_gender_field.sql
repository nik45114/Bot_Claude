-- Добавление поля gender в таблицу admins
-- Дата: 2025-11-11

-- Добавляем колонку gender (male/female/null)
ALTER TABLE admins ADD COLUMN gender TEXT CHECK(gender IN ('male', 'female', NULL));

-- Автоматически проставляем пол по именам
-- Женские имена (по отчеству на -овна/-евна или по окончанию имени)
UPDATE admins
SET gender = 'female'
WHERE is_active = 1
AND (
    -- По отчеству
    full_name LIKE '%овна%'
    OR full_name LIKE '%евна%'
    OR full_name LIKE '%ична%'
    -- По имени
    OR full_name LIKE 'Анастасия%'
    OR full_name LIKE 'Виктория%'
    OR full_name LIKE 'Кира%'
    OR full_name LIKE 'Карина%'
);

-- Мужские имена (все остальные активные админы с ФИО)
UPDATE admins
SET gender = 'male'
WHERE is_active = 1
AND gender IS NULL
AND full_name IS NOT NULL
AND full_name != ''
AND full_name NOT LIKE 'Клуб%'
AND full_name NOT LIKE 'Главный%'
AND full_name NOT LIKE 'Око%';

-- Специальные аккаунты оставляем NULL
-- (Клуб рио, Клуб север, Око Саурона, Главный администратор)
