
# 🚀 Bot Claude v4.13 - Улучшения

## 📦 Файлы для обновления

[View club_manager_v2.py](computer:///mnt/user-data/outputs/club_manager_v2.py) - Улучшенный менеджер клубов  
[View v2ray_manager.py](computer:///mnt/user-data/outputs/v2ray_manager.py) - Полный менеджер V2Ray с REALITY  
[View UPDATE_TO_V4.13.md](computer:///mnt/user-data/outputs/UPDATE_TO_V4.13.md) - Подробная инструкция  
[View FINAL_V4.13.md](computer:///mnt/user-data/outputs/FINAL_V4.13.md) - Краткая сводка

---

## ✨ Что нового

### 💸 Улучшенная система расходов

**5+ форматов парсинга:**
- `- 4500 вика зп` ← классический
- `( - 4500 вика зп)` ← в скобках  
- `зп вика 4500` ← тип первым
- `закупка 1500 monster` ← закупка
- `инкассация 10000` ← инкассация/изъятие

**Автоматическое определение:**
- Получатель (вика, ваня, петя)
- Категория (зарплата, закупка, инкассация, ремонт, коммунальные)
- Группировка в отчете по категориям

**Новые методы:**
- `add_expense()` - добавить расход к смене
- `get_expenses_stats()` - статистика за период
- `get_expenses_history()` - история расходов
- Улучшенная `get_club_stats()` с учетом расходов

### 🔐 Полный V2Ray Manager

**Новый модуль `v2ray_manager.py`:**
- SSH управление серверами (paramiko)
- Автоустановка Xray на Ubuntu
- REALITY протокол с генерацией ключей
- Vision flow для обхода DPI
- Управление пользователями (добавление/удаление)
- Изменение SNI маскировки
- База данных серверов и пользователей

**Формат VLESS ссылки:**
```
vless://uuid@ip:443?encryption=none&flow=xtls-rprx-vision
&security=reality&sni=rutube.ru&fp=chrome
&pbk=publicKey&sid=shortId&type=tcp#username
```

---

## 🔧 Быстрая установка

```bash
cd /opt/club_assistant

# Бэкап
systemctl stop club_assistant
cp club_manager.py club_manager.py.backup

# Замена файлов
cp club_manager_v2.py club_manager.py
# Скопируй v2ray_manager.py в директорию бота

# Зависимости
source venv/bin/activate
pip install paramiko
deactivate

# Запуск
systemctl start club_assistant
```

---

## 📋 Примеры

### Отчет с расходами:

**Текст:**
```
Вечер 15.10
Факт нал 3940

зп вика 4500
зп ваня 4500
закупка 1500 monster
инкассация 10000
```

**Результат:**
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

### V2Ray REALITY:

```bash
/v2add main 45.144.54.117 root pass
/v2setup main
/v2user main @username Вася
/v2sni main youtube.com
```

---

## ⚠️ Важно

1. **Требуется paramiko**: `pip install paramiko`
2. **v2ray_manager.py**: Новый файл, без него V2Ray не работает
3. **База данных**: Автоматически обновится при первом запуске
4. **SSH доступ**: Нужен для управления V2Ray серверами

---

## 📖 Документация

- **UPDATE_TO_V4.13.md** - Подробная инструкция с примерами
- **FINAL_V4.13.md** - Краткая сводка изменений

---

**Версия:** v4.13  
**Дата:** 2025-10-16
