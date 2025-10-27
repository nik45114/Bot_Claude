# Инструкции по установке системы управления админами и сменами v4.14

## Автоматическая установка (Linux/Ubuntu)

```bash
# Скачайте и запустите скрипт установки
sudo ./install_admin_shift.sh
```

## Ручная установка

### 1. Остановка бота
```bash
sudo systemctl stop club_assistant
```

### 2. Создание бэкапа
```bash
cd /opt/club_assistant
sudo mkdir -p backups/admin_shift_$(date +%Y%m%d_%H%M%S)
sudo cp bot.py backups/admin_shift_*/bot.py.backup
sudo cp knowledge.db backups/admin_shift_*/knowledge.db.backup
sudo cp config.json backups/admin_shift_*/config.json.backup
```

### 3. Скачивание обновлений
```bash
cd /opt/club_assistant
git pull origin main
```

### 4. Установка системных зависимостей
```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-rus libtesseract-dev
```

### 5. Установка Python зависимостей
```bash
cd /opt/club_assistant
source venv/bin/activate
pip install opencv-python>=4.8.0 pytesseract>=0.3.10 Pillow>=10.0.0
deactivate
```

### 6. Создание директорий
```bash
sudo mkdir -p /opt/club_assistant/photos
sudo mkdir -p /opt/club_assistant/backups
sudo chown -R club_assistant:club_assistant /opt/club_assistant/photos
sudo chown -R club_assistant:club_assistant /opt/club_assistant/backups
sudo chmod 755 /opt/club_assistant/photos
sudo chmod 755 /opt/club_assistant/backups
```

### 7. Применение патча
```bash
cd /opt/club_assistant
source venv/bin/activate
python3 integration_patch.py bot.py
deactivate
```

### 8. Миграция базы данных
```bash
cd /opt/club_assistant
source venv/bin/activate
python3 migrate_admin_shift.py knowledge.db
deactivate
```

### 9. Запуск бота
```bash
sudo systemctl start club_assistant
```

## Проверка установки

### Команды для проверки в Telegram:
- `/systemstatus` - статус всех систем
- `/adminmgmt` - управление админами
- `/shiftmgmt` - контроль смен
- `/manualupdate` - ручное обновление

### Проверка в терминале:
```bash
# Статус сервиса
sudo systemctl status club_assistant

# Логи
sudo journalctl -u club_assistant -f

# Проверка OCR
tesseract --version

# Проверка директорий
ls -la /opt/club_assistant/photos
ls -la /opt/club_assistant/backups
```

## Откат изменений

Если что-то пошло не так:

```bash
# Остановка бота
sudo systemctl stop club_assistant

# Восстановление из бэкапа
cd /opt/club_assistant
sudo cp backups/admin_shift_*/bot.py.backup bot.py
sudo cp backups/admin_shift_*/knowledge.db.backup knowledge.db
sudo cp backups/admin_shift_*/config.json.backup config.json

# Запуск бота
sudo systemctl start club_assistant
```

## Новые файлы

После установки будут созданы:
- `modules/admin_management.py` - управление админами
- `modules/shift_control.py` - контроль смен
- `modules/ocr_processor.py` - OCR обработка
- `modules/manual_update.py` - ручное обновление
- `modules/admin_shift_integration.py` - интеграция
- `migrations/admin_shift_management_001_init.sql` - миграция БД
- `integration_patch.py` - скрипт интеграции
- `migrate_admin_shift.py` - скрипт миграции
- `install_admin_shift.sh` - скрипт установки

## Новые таблицы в базе данных

- `admin_management` - расширенное управление админами
- `admin_activity` - активность админов
- `shift_control` - детальный контроль смен
- `shift_status_history` - история изменений статуса

## Поддержка

При возникновении проблем:
1. Проверьте логи: `sudo journalctl -u club_assistant -n 50`
2. Проверьте статус системы: `/systemstatus`
3. Проверьте лог обновлений: `/updatelog`
4. При необходимости выполните откат
