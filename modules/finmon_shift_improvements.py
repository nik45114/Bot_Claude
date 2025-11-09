#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшения для FinMon Shift Wizard
Содержит методы для:
- Сохранения данных в finmon_shifts
- Получения предыдущей смены
- Загрузки z-отчетов
- OCR через OpenAI Vision
- Уведомлений контролеру
"""

import logging
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any
import base64
import requests

logger = logging.getLogger(__name__)


class FinMonShiftImprovements:
    """Улучшения для финмониторинга смен"""

    def __init__(self, db_path: str, openai_api_key: str, controller_id: int):
        self.db_path = db_path
        self.openai_api_key = openai_api_key
        self.controller_id = controller_id

    def get_previous_shift_cash(self, club: str, shift_type: str) -> Optional[float]:
        """
        Получить остаток наличных за предыдущую смену того же типа в том же клубе

        Args:
            club: Название клуба
            shift_type: 'morning' или 'evening'

        Returns:
            Остаток наличных или None если предыдущей смены нет
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получить последнюю закрытую смену того же типа в том же клубе
            # Note: knowledge.db uses different column names (fact_cash not cash_revenue, shift_time not shift_type)
            cursor.execute("""
                SELECT safe_cash_end, box_cash_end
                FROM finmon_shifts
                WHERE shift_time = ? AND club = ?
                ORDER BY shift_date DESC, id DESC
                LIMIT 1
            """, (shift_type, club))

            row = cursor.fetchone()
            conn.close()

            if row:
                safe_end, box_end = row
                # Возвращаем сумму остатков сейфа и бокса
                return (safe_end or 0) + (box_end or 0)

            return None

        except Exception as e:
            logger.error(f"❌ Error getting previous shift cash: {e}")
            return None

    def get_previous_shift_balances(self, club: str, shift_type: str) -> tuple[float, float]:
        """
        Получить остатки сейфа и бокса за предыдущую смену того же типа в том же клубе

        Args:
            club: Название клуба
            shift_type: 'morning' или 'evening'

        Returns:
            Кортеж (safe_cash_end, box_cash_end) или (0, 0) если предыдущей смены нет
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT safe_cash_end, box_cash_end
                FROM finmon_shifts
                WHERE shift_time = ? AND club = ?
                ORDER BY shift_date DESC, id DESC
                LIMIT 1
            """, (shift_type, club))

            row = cursor.fetchone()
            conn.close()

            if row:
                safe_end = row[0] or 0
                box_end = row[1] or 0
                return (safe_end, box_end)

            return (0, 0)

        except Exception as e:
            logger.error(f"❌ Error getting previous shift balances: {e}")
            return (0, 0)

    def save_shift_to_db(self, shift_data: Dict[str, Any]) -> Optional[int]:
        """
        Сохранить закрытую смену в finmon_shifts

        Args:
            shift_data: Словарь с данными смены

        Returns:
            ID созданной записи или None при ошибке
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получить данные активной смены для opened_at
            cursor.execute("""
                SELECT opened_at FROM active_shifts
                WHERE id = ?
            """, (shift_data.get('active_shift_id'),))

            row = cursor.fetchone()
            opened_at = row[0] if row else datetime.now().isoformat()

            # Вычислить total_revenue
            total_revenue = (
                (shift_data.get('fact_cash', 0) if not shift_data.get('cash_disabled') else 0) +
                (shift_data.get('fact_card', 0) if not shift_data.get('card_disabled') else 0) +
                (shift_data.get('qr', 0) if not shift_data.get('qr_disabled') else 0) +
                (shift_data.get('card2', 0) if not shift_data.get('card2_disabled') else 0)
            )

            # Вставить данные
            cursor.execute("""
                INSERT INTO finmon_shifts (
                    admin_id, club, shift_type, opened_at, closed_at,
                    cash_revenue, card_revenue, qr_revenue, card2_revenue, total_revenue,
                    safe_cash_start, safe_cash_end, box_cash_start, box_cash_end,
                    total_expenses,
                    z_report_cash_photo, z_report_card_photo, z_report_qr_photo, z_report_card2_photo,
                    z_report_cash_ocr, z_report_card_ocr, z_report_qr_ocr, z_report_card2_ocr,
                    cash_disabled, card_disabled, qr_disabled, card2_disabled,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                shift_data.get('admin_id'),
                shift_data.get('club'),
                shift_data.get('shift_type'),
                opened_at,
                datetime.now().isoformat(),
                shift_data.get('fact_cash', 0),
                shift_data.get('fact_card', 0),
                shift_data.get('qr', 0),
                shift_data.get('card2', 0),
                total_revenue,
                shift_data.get('safe_cash_start', 0),
                shift_data.get('safe_cash_end', 0),
                shift_data.get('box_cash_start', 0),
                shift_data.get('box_cash_end', 0),
                sum(exp['amount'] for exp in shift_data.get('expenses', [])),
                shift_data.get('z_cash_photo'),
                shift_data.get('z_card_photo'),
                shift_data.get('z_qr_photo'),
                shift_data.get('z_card2_photo'),
                shift_data.get('z_cash_ocr'),
                shift_data.get('z_card_ocr'),
                shift_data.get('z_qr_ocr'),
                shift_data.get('z_card2_ocr'),
                shift_data.get('cash_disabled', False),
                shift_data.get('card_disabled', False),
                shift_data.get('qr_disabled', False),
                shift_data.get('card2_disabled', False),
                shift_data.get('notes')
            ))

            shift_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"✅ Shift saved to finmon_shifts: ID={shift_id}")
            return shift_id

        except Exception as e:
            logger.error(f"❌ Error saving shift to DB: {e}")
            return None

    async def process_z_report_ocr(self, photo_file, bot) -> Optional[Dict[str, Any]]:
        """
        Обработать z-отчет через OpenAI Vision API

        Args:
            photo_file: Telegram photo file object
            bot: Telegram bot instance

        Returns:
            Словарь с распознанными данными или None
        """
        try:
            # Скачать фото
            file = await bot.get_file(photo_file.file_id)
            file_bytes = await file.download_as_bytearray()

            # Конвертировать в base64
            base64_image = base64.b64encode(file_bytes).decode('utf-8')

            # Запрос к OpenAI Vision
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }

            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Распознай данные из z-отчета кассы. Верни JSON с полями:
- total: общая сумма
- cash: наличные (если есть)
- card: безнал/карта (если есть)
- date: дата отчета
- time: время отчета
- register_number: номер кассы (если есть)

Если какого-то поля нет - не включай его в ответ. Верни только JSON, без дополнительного текста."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            }

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']

                # Попробовать распарсить JSON из ответа
                try:
                    # Убрать markdown если есть
                    if '```json' in content:
                        content = content.split('```json')[1].split('```')[0]
                    elif '```' in content:
                        content = content.split('```')[1].split('```')[0]

                    ocr_data = json.loads(content.strip())
                    logger.info(f"✅ OCR successful: {ocr_data}")
                    return ocr_data

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse OCR JSON: {e}, content: {content}")
                    return {"raw_text": content}
            else:
                logger.error(f"❌ OpenAI API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Error processing OCR: {e}")
            return None

    async def send_shift_notification_to_controller(
        self,
        bot,
        shift_data: Dict[str, Any],
        admin_name: str,
        is_opening: bool = False
    ):
        """
        Отправить уведомление контролеру о закрытии смены

        Args:
            bot: Telegram bot instance
            shift_data: Данные смены
            admin_name: Имя админа
            is_opening: Ignored (kept for compatibility)
        """
        try:
            # Only send notification when shift is closing
            total_revenue = (
                (shift_data.get('fact_cash', 0) if not shift_data.get('cash_disabled') else 0) +
                (shift_data.get('fact_card', 0) if not shift_data.get('card_disabled') else 0) +
                (shift_data.get('qr', 0) if not shift_data.get('qr_disabled') else 0) +
                (shift_data.get('card2', 0) if not shift_data.get('card2_disabled') else 0)
            )

            expenses_total = sum(exp['amount'] for exp in shift_data.get('expenses', []))

            msg = f"🔒 *Закрыта смена*\n\n"
            msg += f"👤 Админ: {admin_name}\n"
            msg += f"🏢 Клуб: {shift_data.get('club', 'N/A')}\n"
            msg += f"⏰ Смена: {'☀️ Дневная' if shift_data.get('shift_type') == 'morning' else '🌙 Ночная'}\n\n"

            msg += f"💰 *Выручка:*\n"
            if not shift_data.get('cash_disabled'):
                msg += f"  • Наличные: {shift_data.get('fact_cash', 0):,.0f} ₽\n"
            else:
                msg += f"  • Наличные: ❌ Не работала\n"

            if not shift_data.get('card_disabled'):
                msg += f"  • Карта: {shift_data.get('fact_card', 0):,.0f} ₽\n"
            else:
                msg += f"  • Карта: ❌ Не работала\n"

            if not shift_data.get('qr_disabled'):
                msg += f"  • QR: {shift_data.get('qr', 0):,.0f} ₽\n"
            else:
                msg += f"  • QR: ❌ Не работал\n"

            if not shift_data.get('card2_disabled'):
                msg += f"  • Карта 2: {shift_data.get('card2', 0):,.0f} ₽\n"
            else:
                msg += f"  • Карта 2: ❌ Не работала\n"

            msg += f"\n📊 Итого: {total_revenue:,.0f} ₽\n"

            if expenses_total > 0:
                msg += f"💸 Расходы: {expenses_total:,.0f} ₽\n"

            msg += f"\n🏦 *Остатки:*\n"
            msg += f"  • Сейф: {shift_data.get('safe_cash_end', 0):,.0f} ₽\n"
            msg += f"  • Бокс: {shift_data.get('box_cash_end', 0):,.0f} ₽\n"

            msg += f"\n🕐 Время закрытия: {datetime.now().strftime('%H:%M:%S')}"

            # Analyze OCR data and compare with entered values
            ocr_warnings = []

            # Check cash OCR
            if shift_data.get('z_cash_ocr') and not shift_data.get('cash_disabled'):
                try:
                    cash_ocr = json.loads(shift_data.get('z_cash_ocr'))
                    ocr_total = cash_ocr.get('total')
                    entered_cash = shift_data.get('fact_cash', 0)

                    if ocr_total is not None:
                        # Try to parse OCR total (could be string or number)
                        try:
                            ocr_total_value = float(str(ocr_total).replace(' ', '').replace(',', '.').replace('₽', '').strip())
                            difference = abs(ocr_total_value - entered_cash)

                            if difference > 0.01:  # Allow small floating point differences
                                percentage = (difference / max(entered_cash, ocr_total_value)) * 100 if max(entered_cash, ocr_total_value) > 0 else 0
                                ocr_warnings.append(
                                    f"⚠️ *Наличные:* Расхождение!\n"
                                    f"  - OCR распознал: {ocr_total_value:,.0f} ₽\n"
                                    f"  - Введено вручную: {entered_cash:,.0f} ₽\n"
                                    f"  - Разница: {difference:,.0f} ₽ ({percentage:.1f}%)"
                                )
                        except (ValueError, TypeError) as e:
                            logger.error(f"Failed to parse cash OCR total: {ocr_total}, error: {e}")
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to parse cash OCR JSON: {e}")

            # Check card OCR
            if shift_data.get('z_card_ocr') and not shift_data.get('card_disabled'):
                try:
                    card_ocr = json.loads(shift_data.get('z_card_ocr'))
                    ocr_total = card_ocr.get('total')
                    entered_card = shift_data.get('fact_card', 0)

                    if ocr_total is not None:
                        try:
                            ocr_total_value = float(str(ocr_total).replace(' ', '').replace(',', '.').replace('₽', '').strip())
                            difference = abs(ocr_total_value - entered_card)

                            if difference > 0.01:
                                percentage = (difference / max(entered_card, ocr_total_value)) * 100 if max(entered_card, ocr_total_value) > 0 else 0
                                ocr_warnings.append(
                                    f"⚠️ *Карта:* Расхождение!\n"
                                    f"  - OCR распознал: {ocr_total_value:,.0f} ₽\n"
                                    f"  - Введено вручную: {entered_card:,.0f} ₽\n"
                                    f"  - Разница: {difference:,.0f} ₽ ({percentage:.1f}%)"
                                )
                        except (ValueError, TypeError) as e:
                            logger.error(f"Failed to parse card OCR total: {ocr_total}, error: {e}")
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to parse card OCR JSON: {e}")

            # Add OCR status to message
            if ocr_warnings:
                msg += f"\n\n⚠️ *ВНИМАНИЕ: Обнаружены расхождения!*\n\n"
                msg += "\n\n".join(ocr_warnings)
                msg += f"\n\n❗ Проверьте данные!"
            else:
                msg += f"\n\n✅ *OCR проверка:* Все совпадает"

            await bot.send_message(
                chat_id=self.controller_id,
                text=msg,
                parse_mode='Markdown'
            )

            # Send X-report photos (only cash and card, not QR and card2)
            for report_type, photo_key in [
                ('Наличные', 'z_cash_photo'),
                ('Карта', 'z_card_photo')
            ]:
                photo_id = shift_data.get(photo_key)
                if photo_id:
                    await bot.send_photo(
                        chat_id=self.controller_id,
                        photo=photo_id,
                        caption=f"📸 X-отчет: {report_type}"
                    )

            logger.info(f"✅ Notification sent to controller: {self.controller_id}")

        except Exception as e:
            logger.error(f"❌ Error sending notification to controller: {e}")
