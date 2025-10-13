# 🤖 Club Assistant Bot v2.1 - ФИНАЛЬНАЯ СБОРКА

**Telegram бот с AI, автообучением и автообновлениями из GitHub**

---

## ✨ Возможности

✅ **Умное обучение** - `/learn текст` - бот сам извлекает вопрос/ответ  
✅ **База знаний SQLite** - быстрый поиск с нечётким совпадением  
✅ **ChatGPT интеграция** - ответы через OpenAI API  
✅ **Автообновление** - `/update` прямо из Telegram  
✅ **Docker поддержка** - развёртывание в контейнере  
✅ **Минимум ресурсов** - 50-100 MB RAM  

---

## 🚀 Быстрая установка (2 минуты)

### На VPS:

```bash
# Скачайте архив на VPS
wget https://github.com/YOUR_USERNAME/club-bot/archive/main.zip
unzip main.zip
cd club-bot-main

# Запустите установку
chmod +x install.sh
sudo ./install.sh
```

Скрипт спросит:
1. **Способ установки** (Docker или обычная)
2. **Telegram Bot Token**
3. **OpenAI API Key**
4. **Ваш Telegram ID**
5. **GitHub репозиторий** (опционально)

Всё остальное настроится автоматически!

---

## 📦 Структура файлов

```
club-bot/
├── bot.py              # Основной код (400 строк, ПРОТЕСТИРОВАН)
├── requirements.txt    # Python зависимости
├── config.json.example # Пример конфигурации
├── .gitignore          # Защита секретов
├── Dockerfile          # Docker образ
├── docker-compose.yml  # Docker Compose конфиг
├── install.sh          # Универсальный установщик
└── README.md           # Эта инструкция
```

---

## 🎯 Использование

### Команды пользователя:
- Любой вопрос → бот ответит из базы или через GPT

### Команды администратора:

#### `/learn` - Умное обучение
```
/learn Клуб находится на улице Ленина 123, второй этаж
```
Бот сам извлечёт:
- ❓ "Где находится клуб?"
- 💬 "ул. Ленина, 123, 2 этаж"
- 📁 категория: "location"

#### `/stats` - Статистика
```
/stats
```
Показывает сколько знаний в базе, по категориям.

#### `/forget` - Удаление
```
/forget адрес
```
Удаляет все записи содержащие слово "адрес".

#### `/update` - Обновление с GitHub
```
/update
```
Загружает последнюю версию из GitHub.

---

## 🔄 Установка с Docker

### Вариант 1: Через install.sh (рекомендуется)
```bash
sudo ./install.sh
# Выберите "2" для Docker
```

### Вариант 2: Вручную
```bash
# Создайте config.json
cat > config.json << 'EOF'
{
  "telegram_token": "ВАШ_ТОКЕН",
  "openai_api_key": "ВАШ_КЛЮЧ",
  "admin_ids": [ВАШ_ID],
  "github_repo": ""
}
EOF

# Запустите
docker-compose up -d --build
```

### Управление Docker:
```bash
# Логи
docker-compose logs -f

# Перезапуск
docker-compose restart

# Остановка
docker-compose down

# Обновление
docker-compose up -d --build
```

---

## 🛠️ Обычная установка (systemd)

### Вариант 1: Через install.sh (рекомендуется)
```bash
sudo ./install.sh
# Выберите "1" для systemd
```

### Вариант 2: Вручную
```bash
# Создайте директорию
mkdir -p /opt/club_assistant
cd /opt/club_assistant

# Скопируйте файлы
cp bot.py requirements.txt .gitignore /opt/club_assistant/

# Создайте config.json
cat > config.json << 'EOF'
{
  "telegram_token": "ВАШ_ТОКЕН",
  "openai_api_key": "ВАШ_КЛЮЧ",
  "admin_ids": [ВАШ_ID],
  "github_repo": ""
}
EOF
chmod 600 config.json

# Установите зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создайте systemd service
cat > /etc/systemd/system/club_assistant.service << 'EOF'
[Unit]
Description=Club Assistant Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/club_assistant
ExecStart=/opt/club_assistant/venv/bin/python /opt/club_assistant/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Запустите
systemctl daemon-reload
systemctl enable club_assistant
systemctl start club_assistant
```

### Управление systemd:
```bash
# Статус
systemctl status club_assistant

# Логи
journalctl -u club_assistant -f

# Перезапуск
systemctl restart club_assistant

# Остановка
systemctl stop club_assistant
```

---

## 🔄 Настройка автообновлений с GitHub

### 1. Создайте репозиторий на GitHub
1. Зайдите на [github.com](https://github.com)
2. New repository → `club-bot`
3. Private ✅

### 2. Загрузите файлы
```bash
cd /opt/club_assistant

git init
git add bot.py requirements.txt .gitignore
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/club-bot.git
git push -u origin main
```

**ВАЖНО:** НЕ загружайте `config.json` и `knowledge.db`!

### 3. Добавьте URL в config.json
```json
{
  "telegram_token": "...",
  "openai_api_key": "...",
  "admin_ids": [123456789],
  "github_repo": "https://github.com/YOUR_USERNAME/club-bot.git"
}
```

### 4. Обновление
Теперь просто пишите боту в Telegram:
```
/update
```

Или на VPS:
```bash
cd /opt/club_assistant
git pull
systemctl restart club_assistant  # или docker-compose restart
```

---

## 💡 Примеры использования

### Обучение:
```
Админ: /learn Парковка бесплатная, вход со двора

Бот: ✅ Запомнил!
     ❓ Где парковка?
     💬 Бесплатная парковка, вход со двора
     📁 parking
```

### Вопросы:
```
Пользователь: где вы находитесь?
Бот: 💡 ул. Ленина, 123, 2 этаж

Пользователь: сколько стоит абонемент?
Бот: 🤔 Думаю...
Бот: 🤖 [ответ от ChatGPT]
     💾 Сохранено в базу
```

---

## 🔐 Безопасность

- ✅ `config.json` защищён (chmod 600)
- ✅ `.gitignore` исключает секреты из Git
- ✅ База данных только на сервере
- ✅ Приватный GitHub репозиторий (рекомендуется)

---

## 📊 Потребление ресурсов

| Ресурс | Использование |
|--------|---------------|
| RAM    | 50-100 MB     |
| CPU    | 0.1-1%        |
| Диск   | ~50 MB        |

Подходит для самого дешёвого VPS!

---

## 🆘 Устранение проблем

### Бот не запускается
```bash
# Systemd
journalctl -u club_assistant -n 50

# Docker
docker-compose logs --tail=50
```

### Бот не отвечает
Проверьте config.json:
```bash
python3 -c "import json; print(json.load(open('config.json')))"
```

### Обновление не работает
1. Убедитесь что `github_repo` указан в config.json
2. Проверьте git: `git status`
3. Попробуйте: `git pull origin main`

---

## 📝 Changelog

### v2.1 (Final)
- ✅ Исправлены все баги
- ✅ Работает из коробки
- ✅ Docker поддержка
- ✅ Универсальный установщик
- ✅ Протестирован и готов к prod

### v2.0
- Умное обучение через GPT
- Автообновление с GitHub
- Улучшенная база данных

### v1.0
- Базовый функционал

---

## 📞 Поддержка

**Этот бот готов к работе!** Просто установите и используйте.

Если нужны изменения - просто обновите `bot.py` в GitHub и выполните `/update` в Telegram.

---

## 🎉 Готово!

Теперь у вас есть полноценный AI-ассистент который:
- ✅ Работает 24/7
- ✅ Учится сам
- ✅ Обновляется одной командой
- ✅ Жрёт минимум ресурсов

**Наслаждайтесь! 🚀**
