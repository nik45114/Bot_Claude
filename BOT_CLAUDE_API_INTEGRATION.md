# 📡 Интеграция Bot_Claude с Бухгалтерским API

## 🎯 Новые возможности

**3 новых endpoint'а для автоматизации:**

1. **POST /api/receipt** - Прием чеков по QR-коду ФНС
2. **POST /api/cash-withdrawal** - Выдача наличных под отчет
3. **POST /api/accountable-report** - Отчет по подотчету (несколько чеков)

---

## 🔧 Настройки

**API URL:** `http://64.188.83.12:8000`
**API Key:** `f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c`

---

## 📝 Готовый код для Bot_Claude

Добавьте этот файл в `/opt/club_assistant/accounting_integration.py`:

```python
"""
Интеграция с бухгалтерским API
Автоматическая отправка чеков и подотчетных сумм
"""

import aiohttp
from datetime import date
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# Настройки API
ACCOUNTING_API_URL = "http://64.188.83.12:8000"
API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"


async def send_receipt(
    qr_data: str,
    accountable_id: Optional[int] = None,
    category: Optional[str] = None,
    notes: Optional[str] = None
) -> dict:
    """
    Отправить чек в бухгалтерию (QR-код с чека ФНС)

    Args:
        qr_data: Данные QR-кода (строка)
        accountable_id: ID подотчета (если это отчет)
        category: Категория расхода
        notes: Примечания

    Returns:
        Результат обработки чека

    Пример QR-кода:
        t=20240115T1530&s=1500.00&fn=9999078900004792&i=12345&fp=3522207165&n=1
    """
    url = f"{ACCOUNTING_API_URL}/api/receipt"

    payload = {
        "qr_data": qr_data,
        "accountable_id": accountable_id,
        "category": category,
        "notes": notes
    }

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Receipt sent: {result}")
                    return result
                else:
                    error = await resp.text()
                    logger.error(f"Error sending receipt {resp.status}: {error}")
                    return {"status": "error", "message": error}

    except Exception as e:
        logger.error(f"Exception sending receipt: {e}")
        return {"status": "error", "message": str(e)}


async def register_cash_withdrawal(
    employee_name: str,
    amount: float,
    purpose: str,
    report_deadline_days: int = 3,
    notes: Optional[str] = None
) -> dict:
    """
    Зарегистрировать выдачу налички под отчет

    Args:
        employee_name: ФИО сотрудника
        amount: Сумма выдачи
        purpose: Назначение (на что выдано)
        report_deadline_days: Срок отчета (дней, по умолчанию 3)
        notes: Примечания

    Returns:
        Результат с accountable_id
    """
    url = f"{ACCOUNTING_API_URL}/api/cash-withdrawal"

    payload = {
        "employee_name": employee_name,
        "amount": amount,
        "purpose": purpose,
        "report_deadline_days": report_deadline_days,
        "notes": notes
    }

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Cash withdrawal registered: {result}")
                    return result
                else:
                    error = await resp.text()
                    logger.error(f"Error registering withdrawal {resp.status}: {error}")
                    return {"status": "error", "message": error}

    except Exception as e:
        logger.error(f"Exception registering withdrawal: {e}")
        return {"status": "error", "message": str(e)}


async def submit_accountable_report(
    accountable_id: int,
    receipts: List[str],
    notes: Optional[str] = None
) -> dict:
    """
    Отчитаться по подотчету (прислать чеки)

    Args:
        accountable_id: ID подотчета
        receipts: Список QR-кодов чеков
        notes: Примечания

    Returns:
        Результат обработки отчета
    """
    url = f"{ACCOUNTING_API_URL}/api/accountable-report"

    payload = {
        "accountable_id": accountable_id,
        "receipts": receipts,
        "notes": notes
    }

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Accountable report submitted: {result}")
                    return result
                else:
                    error = await resp.text()
                    logger.error(f"Error submitting report {resp.status}: {error}")
                    return {"status": "error", "message": error}

    except Exception as e:
        logger.error(f"Exception submitting report: {e}")
        return {"status": "error", "message": str(e)}


async def send_to_accounting(
    cash: float,
    cashless: float = 0.0,
    qr: float = 0.0,
    shift_type: str = "evening",
    expenses_list: list = None,
    workers_list: list = None
):
    """
    Отправить данные смены (СТАРЫЙ ENDPOINT - уже работает)
    """
    url = f"{ACCOUNTING_API_URL}/api/shift-report"

    payload = {
        "date": date.today().isoformat(),
        "shift": shift_type,
        "cash_fact": cash,
        "cashless_fact": cashless,
        "qr_payments": qr,
        "expenses": expenses_list or [],
        "workers": workers_list or []
    }

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Shift report sent: {result}")
                    return result
                else:
                    error = await resp.text()
                    logger.error(f"Error sending shift {resp.status}: {error}")
                    return None

    except Exception as e:
        logger.error(f"Exception sending shift: {e}")
        return None
```

---

## 💡 Примеры использования в Bot_Claude

### 1. Сканирование QR-кода с чека

```python
from aiogram import Router, F
from aiogram.types import Message
from accounting_integration import send_receipt

router = Router()

@router.message(F.text.startswith("t="))
async def handle_qr_code(message: Message):
    """
    Обработка QR-кода с чека

    Пользователь сканирует QR → отправляет строку → автоматически в бухгалтерию
    """
    qr_data = message.text.strip()

    await message.answer("📝 Обрабатываю чек...")

    # Отправляем в бухгалтерию
    result = await send_receipt(
        qr_data=qr_data,
        category="Расходы на офис",
        notes=f"Чек от {message.from_user.full_name}"
    )

    if result.get("status") == "success":
        data = result.get("data", {})
        await message.answer(
            f"✅ Чек принят!\n\n"
            f"💰 Сумма: {data.get('total_amount')} ₽\n"
            f"🏪 Продавец: {data.get('seller')}\n"
            f"🔗 Ссылка на чек: {data.get('fns_url')}\n\n"
            f"Чек добавлен в бухгалтерию."
        )
    else:
        await message.answer(f"❌ Ошибка: {result.get('message')}")
```

---

### 2. Выдача наличных под отчет

```python
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from accounting_integration import register_cash_withdrawal

router = Router()

@router.message(Command("cash"))
async def cash_withdrawal_handler(message: Message):
    """
    Команда для выдачи налички под отчет

    Использование: /cash 5000 Вода и канцтовары
    """
    try:
        # Парсинг команды
        parts = message.text.split(maxsplit=2)

        if len(parts) < 3:
            await message.answer(
                "Использование: /cash <сумма> <назначение>\n"
                "Пример: /cash 5000 Вода и канцтовары"
            )
            return

        amount = float(parts[1])
        purpose = parts[2]
        employee_name = message.from_user.full_name

        await message.answer("📝 Регистрирую выдачу наличных...")

        # Регистрируем в бухгалтерии
        result = await register_cash_withdrawal(
            employee_name=employee_name,
            amount=amount,
            purpose=purpose,
            report_deadline_days=3
        )

        if result.get("status") == "success":
            data = result.get("data", {})
            await message.answer(
                f"✅ Выдача зарегистрирована!\n\n"
                f"💰 Сумма: {data.get('amount')} ₽\n"
                f"👤 Сотрудник: {data.get('employee')}\n"
                f"📅 Отчитаться до: {data.get('report_deadline')}\n"
                f"🆔 ID подотчета: {data.get('accountable_id')}\n\n"
                f"❗ Сохраните чеки и отчитайтесь в срок!"
            )

            # Сохраняем accountable_id для будущих отчетов
            # (можно в БД или в состояние FSM)

        else:
            await message.answer(f"❌ Ошибка: {result.get('message')}")

    except ValueError:
        await message.answer("❌ Неправильная сумма. Используйте число.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
```

---

### 3. Отчет по подотчету (несколько чеков)

```python
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from accounting_integration import submit_accountable_report

router = Router()

class AccountableReportStates(StatesGroup):
    waiting_for_receipts = State()

# Хранилище для чеков (можно использовать Redis или БД)
temp_receipts = {}

@router.message(Command("report"))
async def start_report(message: Message, state: FSMContext):
    """
    Начать отчет по подотчету

    Использование: /report <accountable_id>
    """
    try:
        parts = message.text.split()

        if len(parts) < 2:
            await message.answer("Использование: /report <ID подотчета>")
            return

        accountable_id = int(parts[1])

        # Сохраняем ID в состояние
        await state.update_data(accountable_id=accountable_id)
        await state.set_state(AccountableReportStates.waiting_for_receipts)

        temp_receipts[message.from_user.id] = []

        await message.answer(
            f"📝 Начинаем отчет по подотчету #{accountable_id}\n\n"
            f"Отправляйте QR-коды чеков (по одному).\n"
            f"Когда закончите, отправьте /done"
        )

    except ValueError:
        await message.answer("❌ ID подотчета должен быть числом")


@router.message(AccountableReportStates.waiting_for_receipts, F.text.startswith("t="))
async def collect_receipt(message: Message):
    """Сбор чеков"""
    qr_data = message.text.strip()

    user_id = message.from_user.id

    if user_id not in temp_receipts:
        temp_receipts[user_id] = []

    temp_receipts[user_id].append(qr_data)

    await message.answer(
        f"✅ Чек #{len(temp_receipts[user_id])} добавлен\n\n"
        f"Отправьте следующий чек или /done для завершения"
    )


@router.message(AccountableReportStates.waiting_for_receipts, Command("done"))
async def finish_report(message: Message, state: FSMContext):
    """Завершить отчет и отправить в бухгалтерию"""
    user_id = message.from_user.id
    data = await state.get_data()
    accountable_id = data.get("accountable_id")

    receipts = temp_receipts.get(user_id, [])

    if not receipts:
        await message.answer("❌ Нет чеков для отправки")
        return

    await message.answer(f"📤 Отправляю {len(receipts)} чеков в бухгалтерию...")

    # Отправляем отчет
    result = await submit_accountable_report(
        accountable_id=accountable_id,
        receipts=receipts,
        notes=f"Отчет от {message.from_user.full_name}"
    )

    if result.get("status") == "success":
        data = result.get("data", {})
        await message.answer(
            f"✅ Отчет принят!\n\n"
            f"📋 Подотчет #{data.get('accountable_id')}\n"
            f"💰 Выдано: {data.get('amount_issued')} ₽\n"
            f"✅ Отчитано: {data.get('amount_reported')} ₽\n"
            f"💵 Осталось: {data.get('amount_remaining')} ₽\n"
            f"📊 Статус: {data.get('status')}\n\n"
            f"Обработано чеков: {len(receipts)}"
        )
    else:
        await message.answer(f"❌ Ошибка: {result.get('message')}")

    # Очищаем состояние
    await state.clear()
    temp_receipts.pop(user_id, None)
```

---

## 🚀 Внедрение

### Шаг 1: Создайте файл
```bash
nano /opt/club_assistant/accounting_integration.py
```

Вставьте код из раздела "Готовый код для Bot_Claude" выше.

### Шаг 2: Добавьте обработчики

Создайте `/opt/club_assistant/handlers/accounting.py` с примерами использования выше.

### Шаг 3: Зарегистрируйте роутер

В `/opt/club_assistant/bot.py`:

```python
from handlers.accounting import router as accounting_router

dp.include_router(accounting_router)
```

### Шаг 4: Установите зависимость

```bash
pip install aiohttp
```

### Шаг 5: Перезапустите бота

```bash
systemctl restart club_assistant  # или ваш метод перезапуска
```

---

## ✅ Готово!

Теперь Bot_Claude может:
- ✅ Принимать QR-коды чеков → автоматически в бухгалтерию
- ✅ Регистрировать выдачу налички → создавать подотчеты
- ✅ Собирать отчеты по подотчетам → закрывать задолженности

**Вся бухгалтерия автоматизирована!** 🎉
