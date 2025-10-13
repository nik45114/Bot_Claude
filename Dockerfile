FROM python:3.11-slim

WORKDIR /app

# Системные пакеты
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код бота
COPY bot.py .

# Запуск
CMD ["python", "-u", "bot.py"]
