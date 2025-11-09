# QR Bot Server - Инструкция

## Статус сервера

Сервер успешно развернут и работает на **64.188.79.142:8080**

## Доступные URL

- **Форма ввода имени**: http://64.188.79.142:8080/form
- **QR код**: http://64.188.79.142:8080/qr
- **API (polling)**: http://64.188.79.142:8080/api/get_name
- **Health check**: http://64.188.79.142:8080/health

## Управление сервисом

### Проверить статус
```bash
sudo systemctl status arcade-qr-bot
```

### Остановить
```bash
sudo systemctl stop arcade-qr-bot
```

### Запустить
```bash
sudo systemctl start arcade-qr-bot
```

### Перезапустить
```bash
sudo systemctl restart arcade-qr-bot
```

### Отключить автозапуск
```bash
sudo systemctl disable arcade-qr-bot
```

### Включить автозапуск
```bash
sudo systemctl enable arcade-qr-bot
```

### Посмотреть логи
```bash
sudo journalctl -u arcade-qr-bot -f
```

## API для клиента (Raspberry Pi)

### Получить имя из очереди (polling)

**Запрос:**
```bash
curl http://64.188.79.142:8080/api/get_name
```

**Ответ (когда есть имя):**
```json
{
  "status": "success",
  "name": "Игрок1",
  "queue_size": 0
}
```

**Ответ (когда очередь пуста):**
```json
{
  "status": "empty",
  "message": "No names in queue"
}
```

### Пример клиента на Python для Raspberry Pi

```python
import requests
import time

SERVER_URL = "http://64.188.79.142:8080/api/get_name"
POLL_INTERVAL = 2  # секунды

while True:
    try:
        response = requests.get(SERVER_URL, timeout=5)
        data = response.json()

        if data["status"] == "success":
            name = data["name"]
            print(f"Получено новое имя: {name}")
            # Здесь обработать имя для игры

        elif data["status"] == "empty":
            # Очередь пуста, продолжаем опрашивать
            pass

    except Exception as e:
        print(f"Ошибка: {e}")

    time.sleep(POLL_INTERVAL)
```

## Проверка работоспособности

```bash
# Health check
curl http://64.188.79.142:8080/health

# Добавить тестовое имя
curl -X POST http://64.188.79.142:8080/submit -d "name=Test"

# Получить имя из очереди
curl http://64.188.79.142:8080/api/get_name
```

## Файлы проекта

- Основной файл: `/opt/club_assistant/qr_bot_server_polling.py`
- Systemd сервис: `/etc/systemd/system/arcade-qr-bot.service`
- Документация: `/opt/club_assistant/QR_BOT_README.md`

## Настройки в коде

```python
SERVER_PORT = 8080           # Порт сервера
MIN_NAME_LENGTH = 2          # Минимальная длина имени
MAX_NAME_LENGTH = 12         # Максимальная длина имени
```

## Особенности

- Сервер работает в режиме polling (не требует webhook)
- Автоматическая фильтрация мата
- Автоматический перезапуск при сбоях (через systemd)
- Очередь имен (FIFO - First In, First Out)
- Thread-safe операции с очередью
- Красивый web-интерфейс в киберспорт стиле

## Что дальше?

1. Откройте http://64.188.79.142:8080/qr в браузере
2. Сохраните QR код
3. Распечатайте и разместите рядом с аркадным автоматом
4. Настройте клиент на Raspberry Pi для опроса сервера
5. Готово! Игроки смогут регистрироваться через QR код
