# Настройка Google Sheets API для парсинга расписания

Это руководство поможет настроить доступ бота к вашей Google Таблице с расписанием смен.

## Шаг 1: Создание Google Cloud Project

1. Перейдите на [Google Cloud Console](https://console.cloud.google.com/)
2. Нажмите **Select a project** → **New Project**
3. Введите название проекта (например, "ClubAssistantBot")
4. Нажмите **Create**

## Шаг 2: Включение Google Sheets API

1. В меню слева выберите **APIs & Services** → **Library**
2. Найдите **Google Sheets API**
3. Нажмите на API и затем **Enable**

## Шаг 3: Создание Service Account

1. Перейдите в **APIs & Services** → **Credentials**
2. Нажмите **Create Credentials** → **Service Account**
3. Заполните форму:
   - **Service account name**: `club-assistant-bot`
   - **Service account ID**: будет создан автоматически
   - **Description**: "Service account for schedule parsing"
4. Нажмите **Create and Continue**
5. В разделе **Role** можно пропустить (нажать **Continue**)
6. Нажмите **Done**

## Шаг 4: Генерация JSON ключа

1. На странице **Credentials** найдите созданный Service Account
2. Нажмите на него (или на иконку редактирования)
3. Перейдите на вкладку **Keys**
4. Нажмите **Add Key** → **Create new key**
5. Выберите формат **JSON**
6. Нажмите **Create**
7. Файл с ключом автоматически скачается на ваш компьютер

**Важно**: Сохраните этот файл в безопасном месте! Он содержит приватный ключ для доступа к API.

## Шаг 5: Загрузка ключа на сервер

1. Переименуйте скачанный файл в `google_credentials.json`

2. Загрузите файл на сервер в директорию бота:
   ```bash
   scp google_credentials.json user@your-server:/opt/club_assistant/
   ```

3. Установите правильные права доступа:
   ```bash
   sudo chmod 600 /opt/club_assistant/google_credentials.json
   sudo chown club_bot:club_bot /opt/club_assistant/google_credentials.json
   ```

## Шаг 6: Предоставление доступа к таблице

1. Откройте скачанный JSON файл и найдите поле `client_email`
   - Пример: `club-assistant-bot@project-name.iam.gserviceaccount.com`

2. Откройте вашу Google Таблицу с расписанием

3. Нажмите **Share** (Поделиться) в правом верхнем углу

4. Вставьте email из `client_email` в поле получателя

5. Установите права **Viewer** (Читатель) или **Editor** (Редактор)

6. Снимите галочку **Notify people** (чтобы не отправлять уведомление)

7. Нажмите **Share**

## Шаг 7: Настройка переменных окружения

1. Откройте файл `.env` в директории бота:
   ```bash
   sudo nano /opt/club_assistant/.env
   ```

2. Добавьте следующие строки:
   ```bash
   # Google Sheets Integration
   GOOGLE_SA_JSON=/opt/club_assistant/google_credentials.json
   GOOGLE_SHEET_ID=19ILASe6UH7-j1okxg9mvz_GrkQAkCJLXA1mxwocLcV8
   ```

3. Если нужно, замените `GOOGLE_SHEET_ID` на ID вашей таблицы:
   - ID таблицы находится в URL: `https://docs.google.com/spreadsheets/d/XXXXX/edit`
   - Где `XXXXX` - это ID таблицы

4. Сохраните файл (Ctrl+O, Enter, Ctrl+X)

## Шаг 8: Установка зависимостей

1. Активируйте виртуальное окружение:
   ```bash
   cd /opt/club_assistant
   source venv/bin/activate
   ```

2. Установите обновленные зависимости:
   ```bash
   pip install -r requirements.txt
   ```

## Шаг 9: Перезапуск бота

```bash
sudo systemctl restart club_assistant
```

## Шаг 10: Проверка работы

1. Проверьте логи бота:
   ```bash
   sudo journalctl -u club_assistant -f
   ```

2. Вы должны увидеть строку:
   ```
   ✅ Google Sheets schedule parser enabled
   ```

3. Если видите ошибку, проверьте:
   - Правильность пути к JSON файлу
   - Права доступа к файлу
   - Доступ Service Account к таблице
   - ID таблицы в переменных окружения

## Проверка парсинга расписания

1. Отправьте боту команду (только для владельца):
   ```
   /schedule test
   ```

2. Бот должен показать информацию о дежурных на сегодня из Google Таблицы

3. Для синхронизации расписания на 30 дней вперед:
   ```
   /schedule sync
   ```

## Структура таблицы

Убедитесь что ваша таблица имеет правильную структуру:

- **Листы**: Названы по месяцам - "Октябрь 2025", "Ноябрь 2025", и т.д.
- **Строка 1**: Даты в формате DD.MM (01.10, 02.10, ...)
- **Колонка A**: ФИО администраторов
- **Ячейки**: 
  - `Д(С)` - дневная смена в Севере
  - `Н(С)` - ночная смена в Севере
  - `Д(Р)` - дневная смена в Рио
  - `Н(Р)` - ночная смена в Рио
  - `.` - выходной

## Связь ФИО с админами

Бот автоматически связывает ФИО из таблицы с Telegram ID через:
- **Панель управления админами**: `/admins`
- Там можно отредактировать имя админа, чтобы оно совпадало с ФИО в таблице

**Важно**: ФИО в таблице и в базе бота должны совпадать (регистр не важен).

## Устранение неполадок

### Ошибка: "Failed to parse Google Sheets"

1. Проверьте доступ Service Account к таблице
2. Убедитесь что JSON файл существует и доступен для чтения
3. Проверьте ID таблицы

### Ошибка: "Sheet not found"

1. Проверьте название листа (должно быть точное совпадение: "Октябрь 2025")
2. Убедитесь что лист на нужный месяц существует

### ФИО не распознаются

1. Откройте `/admins`
2. Найдите админа и отредактируйте его имя
3. Введите точное ФИО как в таблице

### Проверка credentials

```bash
cat /opt/club_assistant/google_credentials.json
```

Должен вывести JSON с полями:
- `type`: "service_account"
- `project_id`: название вашего проекта
- `private_key_id`: ID ключа
- `private_key`: приватный ключ
- `client_email`: email service account

## Безопасность

1. **Никогда** не публикуйте JSON файл с credentials
2. Не добавляйте его в Git (уже в `.gitignore`)
3. Храните backup credentials в безопасном месте
4. При компрометации - удалите ключ в Google Cloud Console и создайте новый

## Дополнительные ресурсы

- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [Service Accounts Overview](https://cloud.google.com/iam/docs/service-accounts)
- [gspread Documentation](https://docs.gspread.org/)

