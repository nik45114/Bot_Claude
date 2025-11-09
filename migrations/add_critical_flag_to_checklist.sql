-- Добавляем поле is_critical для разделения пунктов чек-листа
-- is_critical = 1: критичные пункты, блокируют приём смены
-- is_critical = 0: некритичные пункты (уборка, мыши и т.п.), только уведомление управляющему

ALTER TABLE shift_checklist_items ADD COLUMN is_critical BOOLEAN DEFAULT 1;

-- Делаем некритичными пункты про уборку
UPDATE shift_checklist_items
SET is_critical = 0
WHERE category = 'cleanliness'
OR item_name LIKE '%уборщица%'
OR item_name LIKE '%уборка%'
OR item_name LIKE '%мыши%'
OR item_name LIKE '%мыш%';

-- По умолчанию все остальные пункты критичные
