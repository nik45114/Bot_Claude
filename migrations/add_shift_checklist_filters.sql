-- Миграция: Добавление фильтров по клубу и типу смены в чек-листы
-- Дата: 2025-11-09
-- Описание: Добавляет колонки club и shift_type для фильтрации пунктов чек-листа

-- Добавляем колонки для фильтрации
ALTER TABLE shift_checklist_items ADD COLUMN club TEXT;
ALTER TABLE shift_checklist_items ADD COLUMN shift_type TEXT;

-- Обновляем существующие записи - они будут показываться везде (NULL = показывать всем)
-- Если нужно, можно установить значения для конкретных пунктов:

-- Пример: Специфичные для Севера пункты (если есть)
-- UPDATE shift_checklist_items SET club = 'sever' WHERE item_name = 'Какой-то пункт только для Севера';

-- Пример: Пункты только для утренней смены
-- UPDATE shift_checklist_items SET shift_type = 'morning' WHERE item_name = 'Проверка остатка в сейфе сверен';

-- Пример: Пункты только для вечерней смены
-- UPDATE shift_checklist_items SET shift_type = 'evening' WHERE item_name = 'Закрытие кассы';

-- По умолчанию все существующие пункты доступны для всех клубов и смен (NULL)
