-- Добавление поля для отметки присутствия уборщицы
-- Дата: 2025-11-12

-- Добавляем поле cleaner_was_present (была ли уборщица)
-- NULL = не отмечено, TRUE = была, FALSE = не была
ALTER TABLE cleaning_service_reviews ADD COLUMN cleaner_was_present BOOLEAN DEFAULT NULL;

-- Для существующих записей с рейтингом считаем что уборщица была
UPDATE cleaning_service_reviews SET cleaner_was_present = TRUE WHERE rating IS NOT NULL;
