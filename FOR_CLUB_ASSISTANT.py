"""
ГОТОВЫЙ КОД ДЛЯ /opt/club_assistant (Bot_Claude)
==================================================

✅ IP и API Key уже настроены
✅ Готово к использованию
✅ Копировать этот файл в /opt/club_assistant/
"""

import aiohttp
import asyncio
import sqlite3
import json
import logging
from datetime import date
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

# ============= НАСТРОЙКИ (УЖЕ ГОТОВЫ!) =============

ACCOUNTING_API_URL = "http://64.188.83.12:8000"
API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"
DB_PATH = "knowledge.db"


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

def check_if_already_sent(shift_date: str, shift_type: str, club: str = None) -> Tuple[bool, Optional[Dict]]:
    """
    Проверить, была ли смена уже отправлена в бухгалтерию

    Returns:
        (already_sent, previous_data)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM accounting_sync_log
            WHERE shift_date = ? AND shift_type = ? AND club = ?
            AND sync_status = 'success'
            ORDER BY sent_at DESC
            LIMIT 1
        ''', (shift_date, shift_type, club))

        row = cursor.fetchone()
        conn.close()

        if row:
            return True, dict(row)
        return False, None

    except Exception as e:
        logger.error(f"❌ Error checking sync log: {e}")
        return False, None


def log_accounting_sync(
    shift_date: str,
    shift_type: str,
    club: str,
    cash: float,
    cashless: float,
    qr: float,
    status: str,
    response_data: Optional[Dict] = None,
    error_message: Optional[str] = None
) -> bool:
    """Записать отправку в лог"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Try to insert, if duplicate - update
        cursor.execute('''
            INSERT INTO accounting_sync_log
            (shift_date, shift_type, club, cash_amount, cashless_amount, qr_amount,
             sync_status, response_data, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(shift_date, shift_type, club)
            DO UPDATE SET
                cash_amount = excluded.cash_amount,
                cashless_amount = excluded.cashless_amount,
                qr_amount = excluded.qr_amount,
                sync_status = excluded.sync_status,
                response_data = excluded.response_data,
                error_message = excluded.error_message,
                updated_at = CURRENT_TIMESTAMP
        ''', (shift_date, shift_type, club, cash, cashless, qr, status,
              json.dumps(response_data) if response_data else None, error_message))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error logging sync: {e}")
        return False


# ============= ОСНОВНАЯ ФУНКЦИЯ =============

async def send_to_accounting(
    cash: float,
    cashless: float = 0.0,
    qr: float = 0.0,
    shift_type: str = "evening",
    club: str = None,
    expenses_list: Optional[List[Dict]] = None,
    workers_list: Optional[List[str]] = None,
    force_resend: bool = False,
    shift_date: Optional[date] = None
) -> bool:
    """
    📤 Отправить данные смены в бухгалтерию

    Args:
        cash: Наличные
        cashless: Безналичные
        qr: QR платежи
        shift_type: "morning" или "evening"
        club: Название клуба (опционально)
        expenses_list: [{"amount": 500, "description": "Вода"}, ...]
        workers_list: ["Иван", "Мария"]
        force_resend: Принудительно отправить даже если уже отправляли (default: False)
        shift_date: Дата смены (опционально, по умолчанию - сегодня)

    Returns:
        True - успешно отправлено
        False - ошибка или уже было отправлено

    Пример использования:
        await send_to_accounting(
            cash=15000,
            cashless=8000,
            qr=3500,
            shift_type="evening",
            club="rio",
            workers_list=["Иван Иванов"],
            shift_date=date(2025, 11, 1)
        )
    """

    # Use provided shift_date or default to today
    if shift_date is None:
        shift_date = date.today()

    shift_date_str = shift_date.isoformat()

    # Check if already sent (unless force_resend)
    if not force_resend:
        already_sent, prev_data = check_if_already_sent(shift_date_str, shift_type, club)
        if already_sent:
            logger.info(f"⏭️ Shift {shift_date_str} {shift_type} already sent to accounting, skipping")
            logger.info(f"   Previous: cash={prev_data.get('cash_amount')}, "
                       f"cashless={prev_data.get('cashless_amount')}, "
                       f"qr={prev_data.get('qr_amount')}")
            logger.info(f"   Current:  cash={cash}, cashless={cashless}, qr={qr}")

            # Check if data changed significantly
            prev_cash = prev_data.get('cash_amount', 0) or 0
            prev_cashless = prev_data.get('cashless_amount', 0) or 0
            prev_qr = prev_data.get('qr_amount', 0) or 0

            if (abs(prev_cash - cash) > 1 or
                abs(prev_cashless - cashless) > 1 or
                abs(prev_qr - qr) > 1):
                logger.warning("⚠️ Shift data changed! Consider using force_resend=True to update")

            return False  # Already sent, don't send again

    url = f"{ACCOUNTING_API_URL}/api/shift-report"

    payload = {
        "date": shift_date_str,
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
                    logger.info(f"✅ Данные отправлены в бухгалтерию: {result}")

                    # Log successful sync
                    log_accounting_sync(
                        shift_date_str, shift_type, club,
                        cash, cashless, qr,
                        status='success',
                        response_data=result
                    )
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"❌ Ошибка {resp.status}: {error}")

                    # Log failed sync
                    log_accounting_sync(
                        shift_date_str, shift_type, club,
                        cash, cashless, qr,
                        status='failed',
                        error_message=f"HTTP {resp.status}: {error}"
                    )
                    return False

    except Exception as e:
        logger.error(f"❌ Не удалось отправить в бухгалтерию: {e}")

        # Log failed sync
        log_accounting_sync(
            shift_date_str, shift_type, club,
            cash, cashless, qr,
            status='failed',
            error_message=str(e)
        )
        return False


# ============= КАК ИСПОЛЬЗОВАТЬ В CLUB_ASSISTANT =============

"""
ШАГ 1: Найти обработчик закрытия смены
---------------------------------------

Найдите в /opt/club_assistant/ файл, где обрабатывается закрытие смены.
Обычно это:
- handlers/shift.py
- handlers/admin.py
- handlers/close_shift.py
или похожий файл


ШАГ 2: Добавить импорт
-----------------------

В начале файла добавьте:

    from FOR_CLUB_ASSISTANT import send_to_accounting


ШАГ 3: Добавить вызов после закрытия смены
--------------------------------------------

Найдите функцию закрытия смены, например:

    @router.message(Command("close_shift"))
    async def close_shift_handler(message: Message):
        # Существующий код расчета смены
        cash_today = calculate_cash()
        card_today = calculate_card()
        qr_today = calculate_qr()

        # ДОБАВИТЬ ЭТО:
        await send_to_accounting(
            cash=cash_today,
            cashless=card_today,
            qr=qr_today,
            shift_type="evening",  # или определять динамически
            workers_list=["Имя сотрудника"]  # если есть данные
        )

        await message.answer("✅ Смена закрыта и отправлена в бухгалтерию!")


ПОЛНЫЙ ПРИМЕР:
--------------
"""

# Пример полного обработчика с интеграцией
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from FOR_CLUB_ASSISTANT import send_to_accounting  # ← ИМПОРТ

router = Router()

@router.message(Command("close_shift"))
async def close_shift(message: Message, session):
    # Ваш существующий код
    cash_total = await get_cash_from_db(session)
    card_total = await get_card_from_db(session)
    qr_total = await get_qr_from_db(session)

    # Расходы (если есть)
    expenses = await get_expenses_from_db(session)
    expenses_list = [
        {"amount": e.amount, "description": e.description}
        for e in expenses
    ]

    # Работники смены (если есть)
    workers = await get_workers_from_db(session)
    workers_list = [w.name for w in workers]

    # ОТПРАВКА В БУХГАЛТЕРИЮ
    success = await send_to_accounting(
        cash=cash_total,
        cashless=card_total,
        qr=qr_total,
        shift_type="evening",
        expenses_list=expenses_list,
        workers_list=workers_list
    )

    if success:
        await message.answer("✅ Смена закрыта и данные отправлены в бухгалтерию!")
    else:
        await message.answer("⚠️ Смена закрыта, но не удалось отправить данные в бухгалтерию")
"""


# ============= ТЕСТ =============

async def test():
    """Тестовая отправка для проверки работоспособности"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ ИНТЕГРАЦИИ /opt/club_assistant → БУХГАЛТЕРИЯ")
    print("="*60)

    print(f"\n📡 API Сервер: {ACCOUNTING_API_URL}")
    print(f"🔑 API Key: {API_KEY[:20]}...")

    print("\n📤 Отправка тестовых данных...")

    success = await send_to_accounting(
        cash=15000.0,
        cashless=8000.0,
        qr=3500.0,
        shift_type="evening",
        expenses_list=[
            {"amount": 500, "description": "Вода"},
            {"amount": 1200, "description": "Канцтовары"}
        ],
        workers_list=["Тестовый Сотрудник"]
    )

    print("\n" + "="*60)
    if success:
        print("✅ ТЕСТ ПРОЙДЕН!")
        print("\n📋 Проверьте в Telegram боте @Buh45114_bot:")
        print("   /today - транзакции за сегодня")
        print("   /balance - текущий баланс")
    else:
        print("❌ ТЕСТ ПРОВАЛЕН!")
        print("\n🔍 Проверьте:")
        print("   1. Доступен ли сервер 64.188.83.12")
        print("   2. Запущен ли бухгалтерский API")
        print("   3. Правильный ли API ключ")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Запуск теста
    print("Для теста запустите:")
    print("cd /opt/club_assistant")
    print("python3 FOR_CLUB_ASSISTANT.py")
    print()
    asyncio.run(test())


# ============= ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ =============

"""
ПРИМЕР 1: Минимальный (только наличка)
---------------------------------------
await send_to_accounting(cash=15000)


ПРИМЕР 2: Все способы оплаты
------------------------------
await send_to_accounting(
    cash=15000,
    cashless=8000,
    qr=3500
)


ПРИМЕР 3: С расходами
----------------------
await send_to_accounting(
    cash=15000,
    cashless=8000,
    expenses_list=[
        {"amount": 500, "description": "Вода 5л x10"},
        {"amount": 1200, "description": "Канцтовары"},
        {"amount": 300, "description": "Чистящие средства"}
    ]
)


ПРИМЕР 4: Полный (все данные)
-------------------------------
await send_to_accounting(
    cash=15000.0,
    cashless=8000.0,
    qr=3500.0,
    shift_type="evening",
    expenses_list=[
        {"amount": 500, "description": "Вода"},
        {"amount": 1200, "description": "Канцтовары"}
    ],
    workers_list=["Иван Иванов", "Мария Петрова"]
)


ПРИМЕР 5: С проверкой ошибок
------------------------------
success = await send_to_accounting(cash=15000, cashless=8000)

if success:
    print("✅ Данные отправлены!")
else:
    print("❌ Ошибка отправки!")
    # Можно отправить уведомление администратору
"""
