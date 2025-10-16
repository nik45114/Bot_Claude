# 🎉 v4.13 - Улучшенные расходы + Полный V2Ray Manager

## ✅ Готово к использованию

### 📦 Новые/Обновлённые файлы:

1. **club_manager_v2.py** → `club_manager.py` - улучшенная система расходов
2. **v2ray_manager.py** (НОВЫЙ!) - полный менеджер V2Ray с SSH
3. **v2ray_commands.py** - команды V2Ray (без изменений, но требует v2ray_manager.py)
4. **UPDATE_TO_V4.13.md** - подробная инструкция обновления

---

## 💸 Улучшения расходов

### Что изменилось:

✅ **5+ форматов парсинга**:
```
- 4500 вика зп              ← стандартный
( - 4500 вика зп)           ← в скобках
зп вика 4500                ← тип первым
закупка 1500 monster        ← закупка
инкассация 10000            ← инкассация
```

✅ **Автоопределение получателя**:
```
"- 4500 вика зп" → recipient="вика", category="salary"
"закупка 1500 monster" → category="purchase", description="monster"
```

✅ **6 категорий расходов**:
- 👤 Зарплата (salary)
- 🛒 Закупки (purchase)
- 🏦 Инкассация (collection)
- 🔧 Ремонт (repair)
- 🔌 Коммунальные (utility)
- 💰 Прочее (other)

✅ **Новые методы**:
- `add_expense()` - добавить расход
- `get_expenses_stats()` - статистика
- `get_expenses_history()` - история
- Улучшенная `get_club_stats()` с расходами

✅ **Красивый вывод**:
```
💸 РАСХОДЫ
━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 Зарплата:
  👤 зп (вика): 4,500 ₽
  👤 зп (ваня): 4,500 ₽

🛒 Закупки:
  🛒 закупка monster: 1,500 ₽

🏦 Инкассация:
  🏦 инкассация: 10,000 ₽

📊 Всего расходов: 20,500 ₽
```

### База данных:

```sql
-- Новые поля в shift_expenses
ALTER TABLE shift_expenses ADD COLUMN recipient TEXT;
ALTER TABLE shift_expenses ADD COLUMN notes TEXT;
```

---

## 🔐 Полный V2Ray Manager

### Новый модуль: v2ray_manager.py

✅ **Класс V2RayServer**:
- SSH подключение (paramiko)
- Выполнение команд на сервере
- Передача файлов (SFTP)

✅ **Установка Xray**:
- Автоматическая установка на Ubuntu
- Проверка статуса systemctl
- Управление сервисом

✅ **REALITY протокол**:
- Генерация ключей x25519
- Настройка маскировки (SNI)
- Vision flow для обхода DPI

✅ **Управление пользователями**:
- Добавление с UUID
- Генерация VLESS ссылок
- Удаление пользователей
- Изменение SNI

✅ **База данных**:
```sql
CREATE TABLE v2ray_servers (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    host TEXT,
    port INTEGER DEFAULT 22,
    username TEXT,
    password TEXT,
    sni TEXT DEFAULT 'rutube.ru',
    public_key TEXT,
    short_id TEXT,
    ...
);

CREATE TABLE v2ray_users (
    id INTEGER PRIMARY KEY,
    server_id INTEGER,
    user_id TEXT,
    uuid TEXT,
    email TEXT,
    vless_link TEXT,
    ...
);
```

### Формат VLESS ссылки:

```
vless://uuid@ip:443
?encryption=none
&flow=xtls-rprx-vision
&security=reality
&sni=rutube.ru
&fp=chrome
&pbk=publicKey
&sid=shortId
&type=tcp
#username
```

### Команды:

```bash
/v2add main 45.144.54.117 root pass          # Добавить сервер
/v2add main 45.144.54.117 root pass youtube.com  # С кастомным SNI
/v2setup main                                # Установить Xray (2-3 мин)
/v2user main @user Вася                      # Добавить пользователя
/v2sni main youtube.com                      # Изменить SNI
/v2stats main                                # Статистика
/v2list                                      # Список серверов
/v2remove main uuid                          # Удалить пользователя
```

---

## 🚀 Быстрый старт

### Установка:

```bash
cd /opt/club_assistant

# Бэкап
systemctl stop club_assistant
cp club_manager.py club_manager.py.backup
cp knowledge.db knowledge.db.backup

# Обновление
git pull origin main

# Зависимости
source venv/bin/activate
pip install paramiko
deactivate

# Запуск
systemctl start club_assistant
journalctl -u club_assistant -f
```

### Использование:

**Расходы:**
```
/report Центральный

Вечер 15.10
Факт нал 3940

зп вика 4500
зп ваня 4500
закупка 1500 monster
инкассация 10000
```

**V2Ray:**
```
/v2add main 45.144.54.117 root MyPass123
/v2setup main
/v2user main @username Вася
```

---

## 📊 Примеры

### Пример 1: Отчет с расходами

**Вход:**
```
Вечер 15.10
Факт нал 3,940 / 20,703
Наличка в сейфе 927

- 4500 вика зп
- 4500 ваня зп
закупка 1500 monster
инкассация 10000
```

**Выход:**
```
╔═══════════════════════════════
║ 🌆 Отчёт смены
╠═══════════════════════════════
║ 🏢 Клуб: Центральный
║ 📅 Дата: 2025-10-15
║ 👤 Админ: Вася
╚═══════════════════════════════

💰 ФИНАНСЫ
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 Наличные:
   Факт:      3,940 ₽
   План:     20,703 ₽
   📉 Разница: -16,763 ₽
   
   Сейф:        927 ₽

💸 РАСХОДЫ
━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 Зарплата:
  👤 зп (вика): 4,500 ₽
  👤 зп (ваня): 4,500 ₽

🛒 Закупки:
  🛒 закупка monster: 1,500 ₽

🏦 Инкассация:
  🏦 инкассация: 10,000 ₽

📊 Всего расходов: 20,500 ₽

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Отчёт #42
```

### Пример 2: V2Ray REALITY

**Команды:**
```
Owner: /v2add main 45.144.54.117 root MySecretPass

Bot:   ✅ Сервер 'main' добавлен!
       
       🖥 Host: 45.144.54.117
       👤 User: root
       🌐 SNI: rutube.ru
       
       Теперь выполни: /v2setup main

Owner: /v2setup main

Bot:   ⏳ Подключаюсь к серверу main...
       📥 Устанавливаю Xray (2-3 минуты)...
       ⚙️ Создаю REALITY конфигурацию...
       
       ✅ Xray установлен на main!
       
       🔐 Протокол: REALITY
       🌐 Маскировка: rutube.ru
       
       Теперь можешь добавлять пользователей:
       /v2user main <user_id> [email]

Owner: /v2user main @username Вася

Bot:   ⏳ Добавляю пользователя на main...
       
       ✅ Пользователь добавлен!
       
       👤 ID: @username
       📧 Email: Вася
       🔑 UUID: d25e2d90-2ee8-48a2-83f4-5af0bff8e82f
       🌐 SNI: rutube.ru
       
       🔗 VLESS ссылка (REALITY):
       vless://d25e2d90-2ee8-48a2-83f4-5af0bff8e82f@45.144.54.117:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=rutube.ru&fp=chrome&type=tcp&pbk=tC5EjUIeCYfMPp-cPfteC_3GuRG3fFG_cnwOAri_E04&sid=42b4137294a4fc79#Вася

Owner: /v2sni main youtube.com

Bot:   ⏳ Изменяю маскировку на youtube.com...
       
       ✅ Маскировка изменена на youtube.com!
       
       ⚠️ Все пользователи должны обновить свои ссылки.
       Создай новые: /v2user main <user_id>
```

---

## 🔍 Тестирование

### Тест 1: Расходы

```bash
# Отправь разные форматы
- 4500 вика зп           # ✅
( - 3000 ваня зп)        # ✅
зп петя 2000             # ✅
закупка 1500 monster     # ✅
инкассация 10000         # ✅

# Проверь, что все распарсилось правильно
```

### Тест 2: V2Ray

```bash
/v2list                  # Должен показать серверы
/v2stats main            # Статистика
/v2user main @test Test  # Создать пользователя
# Подключись к серверу с полученной ссылкой
```

---

## 📋 Чеклист обновления

- [ ] Бэкап сделан
- [ ] Git pull выполнен
- [ ] paramiko установлен
- [ ] База обновлена (recipient, notes в shift_expenses)
- [ ] Таблицы V2Ray созданы
- [ ] Бот запускается
- [ ] /v2ray команды работают
- [ ] Расходы парсятся
- [ ] Логи чистые

---

## ⚠️ Важно

1. **Требуется paramiko:** `pip install paramiko`
2. **SSH доступ к серверам:** Убедись, что можешь подключиться по SSH
3. **Порт 443 свободен:** На сервере не должно быть другого сервиса на порту 443
4. **Права root:** Установка Xray требует root доступа

---

## 📈 Статистика

### Новые возможности аналитики:

```python
# Статистика расходов за 30 дней
stats = club_manager.get_expenses_stats(club_id=1, days=30)
print(stats)
# {
#   'by_category': {
#     'salary': {'total': 90000, 'count': 20, 'average': 4500},
#     'purchase': {'total': 30000, 'count': 15, 'average': 2000},
#     ...
#   },
#   'total': 150000,
#   'count': 50
# }

# История расходов
history = club_manager.get_expenses_history(club_id=1, days=7)
# [
#   {
#     'description': 'зп',
#     'amount': 4500,
#     'recipient': 'вика',
#     'club_name': 'Центральный',
#     'admin_name': 'Вася',
#     'shift_date': '2025-10-15'
#   },
#   ...
# ]

# Статистика клуба с расходами
stats = club_manager.get_club_stats(club_id=1, days=7)
print(stats)
# {
#   'total_revenue': 150000,
#   'total_expenses': 50000,
#   'net_revenue': 100000,
#   ...
# }
```

---

## ✨ Что дальше?

**v4.14 (в планах):**
- Inline кнопки для ввода расходов
- Напоминания о сдаче отчетов
- Графики расходов (matplotlib)
- Экспорт в Excel
- Telegram Web App

---

## 🎯 Итого v4.13:

**Club Manager:**
- 5+ форматов парсинга расходов
- Автоопределение получателя
- 6 категорий
- Аналитика и история
- Красивое форматирование

**V2Ray Manager:**
- SSH управление
- REALITY протокол
- Автоустановка Xray
- Генерация ключей
- База данных серверов

**Готово к продакшену!** 🚀

---

**Версия:** v4.13  
**Дата:** 2025-10-16  
**Авторы:** Claude AI  
**GitHub:** https://github.com/nik45114/Bot_Claude
