#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QR сервер с поддержкой polling (для Raspberry Pi за NAT)
Raspberry Pi сам опрашивает сервер за именами
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import qrcode
from io import BytesIO
import threading
from datetime import datetime

# НАСТРОЙКИ
SERVER_PORT = 8080
MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 12

# Очередь имён (thread-safe)
name_queue = []
queue_lock = threading.Lock()

# Список матов для фильтрации
PROFANITY_LIST = [
    "хуй", "пизд", "ебл", "ебан", "бля", "сук", "dick", "fuck", "shit",
    "bitch", "ass", "cunt", "cock", "damn", "hell", "nigga", "nigger"
]


def contains_profanity(text: str) -> bool:
    """Проверить на наличие мата"""
    text_lower = text.lower()
    return any(word in text_lower for word in PROFANITY_LIST)


def sanitize_name(name: str) -> str:
    """Очистить и проверить имя"""
    name = name.strip()

    # Обрезать длину
    if len(name) > MAX_NAME_LENGTH:
        name = name[:MAX_NAME_LENGTH]

    # Заменить мат звёздочками
    if contains_profanity(name):
        for word in PROFANITY_LIST:
            if word in name.lower():
                name = name.replace(word, "*" * len(word))
                name = name.replace(word.upper(), "*" * len(word))
                name = name.replace(word.capitalize(), "*" * len(word))

    return name


class QRServerHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP запросов"""

    def log_message(self, format, *args):
        """Логирование"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} - {format % args}")

    def do_GET(self):
        """GET запросы"""

        # API для polling - получить имя из очереди
        if self.path == "/api/get_name":
            with queue_lock:
                if len(name_queue) > 0:
                    # Извлечь первое имя из очереди
                    name = name_queue.pop(0)

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    response = json.dumps({
                        "status": "success",
                        "name": name,
                        "queue_size": len(name_queue)
                    })
                    self.wfile.write(response.encode('utf-8'))

                    print(f"[API] Выдано имя: {name}, осталось в очереди: {len(name_queue)}")
                else:
                    # Очередь пуста
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    response = json.dumps({
                        "status": "empty",
                        "message": "No names in queue"
                    })
                    self.wfile.write(response.encode('utf-8'))
            return

        # Проверка здоровья
        if self.path == "/health":
            with queue_lock:
                queue_size = len(name_queue)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            response = json.dumps({
                "status": "ok",
                "queue_size": queue_size
            })
            self.wfile.write(response.encode('utf-8'))
            return

        # Форма ввода имени
        if self.path == "/" or self.path == "/form":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()

            html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход в игру</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #051420 0%, #0a2030 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: rgba(20, 30, 35, 0.9);
            border: 2px solid #00ffff;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 0 50px rgba(0, 255, 255, 0.3);
        }

        h1 {
            color: #00ffff;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        }

        .form-group {
            margin-bottom: 25px;
        }

        label {
            display: block;
            color: #00ffff;
            margin-bottom: 10px;
            font-size: 1.1em;
        }

        input[type="text"] {
            width: 100%;
            padding: 15px;
            font-size: 1.2em;
            border: 2px solid #00b3b3;
            border-radius: 10px;
            background: rgba(5, 20, 32, 0.8);
            color: #ffffff;
            transition: all 0.3s;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: #00ffff;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.4);
        }

        button {
            width: 100%;
            padding: 18px;
            font-size: 1.3em;
            font-weight: bold;
            color: #051420;
            background: linear-gradient(135deg, #00ffff 0%, #00b3b3 100%);
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 255, 255, 0.5);
        }

        button:active {
            transform: translateY(0);
        }

        .hint {
            text-align: center;
            color: #00b3b3;
            font-size: 0.9em;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 ВХОД В ИГРУ 🎮</h1>
        <form method="POST" action="/submit">
            <div class="form-group">
                <label for="name">Введите ваше имя:</label>
                <input
                    type="text"
                    id="name"
                    name="name"
                    minlength="2"
                    maxlength="12"
                    required
                    autocomplete="off"
                    placeholder="Ваше имя"
                    autofocus
                >
            </div>
            <button type="submit">ВОЙТИ В ИГРУ</button>
        </form>
        <div class="hint">
            От 2 до 12 символов<br>
            Мат фильтруется автоматически
        </div>
    </div>
</body>
</html>
            """
            self.wfile.write(html.encode('utf-8'))
            return

        # QR код как изображение
        if self.path == "/qr":
            self.send_response(200)
            self.send_header("Content-type", "image/png")
            self.end_headers()

            # URL формы (нужно указать реальный внешний IP/домен)
            url = f"http://64.188.79.142:{SERVER_PORT}/form"

            # Сгенерировать QR код
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            # Конвертировать в PNG
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            self.wfile.write(buffer.getvalue())
            return

        # 404
        self.send_error(404)

    def do_POST(self):
        """POST запросы"""

        if self.path == "/submit":
            # Прочитать данные формы
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(post_data)

            name = params.get('name', [''])[0]
            name = sanitize_name(name)

            # Проверка длины
            if len(name) < MIN_NAME_LENGTH or len(name) > MAX_NAME_LENGTH:
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()

                html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ошибка</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #051420 0%, #0a2030 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: rgba(20, 30, 35, 0.9);
            border: 2px solid #ff6b6b;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            text-align: center;
        }}
        h1 {{ color: #ff6b6b; margin-bottom: 20px; }}
        p {{ color: #ffffff; font-size: 1.1em; margin-bottom: 30px; }}
        a {{
            display: inline-block;
            padding: 15px 30px;
            background: #00ffff;
            color: #051420;
            text-decoration: none;
            border-radius: 10px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>❌ Ошибка</h1>
        <p>Имя должно быть от {MIN_NAME_LENGTH} до {MAX_NAME_LENGTH} символов</p>
        <a href="/form">Попробовать снова</a>
    </div>
</body>
</html>
                """
                self.wfile.write(html.encode('utf-8'))
                return

            # Добавить имя в очередь
            with queue_lock:
                name_queue.append(name)
                queue_size = len(name_queue)

            print(f"[QUEUE] Добавлено имя: {name}, размер очереди: {queue_size}")

            # Показать успех
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()

            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Успех</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #051420 0%, #0a2030 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: rgba(20, 30, 35, 0.9);
            border: 2px solid #6bff6b;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            text-align: center;
        }}
        h1 {{
            color: #6bff6b;
            margin-bottom: 20px;
            font-size: 2.5em;
        }}
        p {{
            color: #ffffff;
            font-size: 1.3em;
            margin-bottom: 30px;
        }}
        .name {{
            color: #00ffff;
            font-size: 1.5em;
            font-weight: bold;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ ГОТОВО!</h1>
        <div class="name">{name}</div>
        <p>Вы успешно авторизовались!<br>Можете закрыть эту страницу.</p>
    </div>
</body>
</html>
            """
            self.wfile.write(html.encode('utf-8'))
            return

        # 404
        self.send_error(404)


def main():
    """Запустить сервер"""
    print("=" * 60)
    print("   QR СЕРВЕР С POLLING (для Raspberry Pi за NAT)")
    print("=" * 60)
    print()
    print(f"🌐 Сервер запущен на порту {SERVER_PORT}")
    print(f"📱 Форма: http://64.188.79.142:{SERVER_PORT}/form")
    print(f"📸 QR код: http://64.188.79.142:{SERVER_PORT}/qr")
    print(f"🔌 API polling: http://64.188.79.142:{SERVER_PORT}/api/get_name")
    print()
    print("📊 Raspberry Pi должен опрашивать /api/get_name")
    print("   для получения имён из очереди")
    print()
    print("Нажмите Ctrl+C для остановки")
    print("=" * 60)

    server = HTTPServer(('0.0.0.0', SERVER_PORT), QRServerHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nОстановка сервера...")
        server.shutdown()


if __name__ == "__main__":
    main()
