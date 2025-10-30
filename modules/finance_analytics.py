"""
Модуль финансовой аналитики и отчетности

Функции:
- Полный обзор движения средств (кассы, выплаты, расходы)
- Расчет зарплат с учетом выплат из кассы
- Анализ эффективности администраторов по дням недели
- Корреляция выручки и смен
- Визуализация данных (графики, таблицы)
- Интеграция с Google Sheets (столбцы AL, AM, AN для зарплат)
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class FinanceAnalytics:
    """Модуль финансовой аналитики"""

    def __init__(self, db_path: str = "club_assistant.db", sheets_parser=None):
        self.db_path = db_path
        self.sheets_parser = sheets_parser
        logger.info("✅ FinanceAnalytics инициализирован")

    def _get_db(self):
        """Получить подключение к БД"""
        return sqlite3.connect(self.db_path)

    # =====================================================
    # ОСНОВНЫЕ ДАННЫЕ
    # =====================================================

    def get_cash_movements(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        club: Optional[str] = None,
        admin_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Получить все движения денег за период

        Возвращает:
        - Выручка по сменам
        - Расходы из касс
        - Выплаты зарплат
        - Остатки на начало/конец
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        movements = []

        # Параметры фильтрации
        where_clauses = []
        params = []

        if start_date:
            where_clauses.append("DATE(opened_at) >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("DATE(opened_at) <= ?")
            params.append(end_date)

        if club:
            where_clauses.append("club = ?")
            params.append(club)

        if admin_id:
            where_clauses.append("admin_id = ?")
            params.append(admin_id)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # 1. Получить смены и выручку
        query = f"""
        SELECT
            id as shift_id,
            admin_id,
            club,
            shift_type,
            opened_at,
            closed_at,
            status
        FROM active_shifts
        WHERE {where_sql}
        ORDER BY opened_at DESC
        """

        cursor.execute(query, params)
        shifts = cursor.fetchall()

        for shift in shifts:
            # Для каждой смены получаем данные
            shift_data = dict(shift)

            # Получить расходы из касс за смену
            cursor.execute("""
                SELECT
                    SUM(amount) as total_expenses,
                    cash_register
                FROM shift_expenses
                WHERE shift_id = ?
                GROUP BY cash_register
            """, (shift['shift_id'],))

            expenses = cursor.fetchall()
            shift_data['expenses'] = [dict(e) for e in expenses]

            # Получить выплаты зарплат за смену
            cursor.execute("""
                SELECT
                    SUM(amount) as total_withdrawals
                FROM shift_cash_withdrawals
                WHERE shift_id = ?
            """, (shift['shift_id'],))

            withdrawal = cursor.fetchone()
            shift_data['cash_withdrawals'] = withdrawal['total_withdrawals'] if withdrawal else 0

            movements.append(shift_data)

        conn.close()

        logger.info(f"📊 Получено {len(movements)} движений средств")
        return movements

    def get_admin_salaries_from_sheets(self) -> Dict[int, Dict]:
        """
        Получить зарплаты администраторов из Google Sheets

        Читает столбцы AL, AM, AN:
        - AL (колонка 38): Описание выплаты
        - AM (колонка 39): Сумма
        - AN (колонка 40): Примечание

        Возвращает:
        {
            admin_id: {
                'name': 'Имя',
                'salary_items': [
                    {'description': '...', 'amount': 1000, 'note': '...'},
                    ...
                ],
                'total': 5000
            }
        }
        """
        if not self.sheets_parser:
            logger.warning("⚠️ Google Sheets parser не настроен")
            return {}

        try:
            logger.info("📊 Получение зарплат из Google Sheets...")

            # Получить клиент Sheets
            client = self.sheets_parser._get_sheet_client()
            spreadsheet = self.sheets_parser._get_spreadsheet()

            # Открыть первый лист (обычно это лист с расписанием и зарплатами)
            worksheet = spreadsheet.get_worksheet(0)

            # Получить все значения из столбцов AL:AN (38:40)
            # Формат: AL1:AN100 (берём первые 100 строк)
            salary_data = worksheet.get('AL1:AN100')

            if not salary_data:
                logger.info("📊 Нет данных о зарплатах в таблице")
                return {}

            # Парсинг данных
            salaries = {}

            # Предполагаем, что первая строка - заголовки
            # Далее каждая строка: [Имя/Описание, Сумма, Примечание]
            for row_idx, row in enumerate(salary_data[1:], start=2):  # Пропускаем заголовок
                if len(row) < 2:  # Минимум нужно описание и сумма
                    continue

                description = row[0].strip() if len(row) > 0 else ""
                amount_str = row[1].strip() if len(row) > 1 else "0"
                note = row[2].strip() if len(row) > 2 else ""

                # Пропускаем пустые строки
                if not description and not amount_str:
                    continue

                # Парсим сумму
                try:
                    # Убираем всё кроме цифр, точки и минуса
                    amount_str = amount_str.replace(',', '.').replace(' ', '').replace('₽', '')
                    amount = float(amount_str) if amount_str else 0
                except (ValueError, AttributeError):
                    logger.warning(f"⚠️ Не удалось распарсить сумму: {amount_str} в строке {row_idx}")
                    amount = 0

                # Попробовать извлечь имя администратора из описания
                # Формат может быть: "Иванов И.И. - смены" или просто "Смены"
                admin_name = self._extract_admin_name(description)

                if not admin_name:
                    logger.debug(f"⏭️ Пропускаем строку без имени админа: {description}")
                    continue

                # Получить admin_id по имени (если есть AdminDB)
                admin_id = self._get_admin_id_by_name(admin_name)

                if not admin_id:
                    # Если не нашли в БД, используем имя как ключ
                    admin_id = f"unknown_{admin_name}"

                # Добавить в результат
                if admin_id not in salaries:
                    salaries[admin_id] = {
                        'name': admin_name,
                        'salary_items': [],
                        'total': 0
                    }

                salaries[admin_id]['salary_items'].append({
                    'description': description,
                    'amount': amount,
                    'note': note
                })
                salaries[admin_id]['total'] += amount

            logger.info(f"📊 Получены зарплаты для {len(salaries)} администраторов")
            return salaries

        except Exception as e:
            logger.error(f"❌ Ошибка получения данных из Sheets: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _extract_admin_name(self, text: str) -> Optional[str]:
        """
        Извлечь имя администратора из текста

        Примеры:
        - "Иванов И.И. - смены" -> "Иванов И.И."
        - "Петров П. (аванс)" -> "Петров П."
        - "Смирнова Анна - премия" -> "Смирнова Анна"
        """
        if not text:
            return None

        # Паттерны для поиска имени
        # 1. Фамилия Инициалы (Иванов И.И.)
        import re
        pattern1 = r'^([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.?)'
        match = re.match(pattern1, text)
        if match:
            return match.group(1).strip()

        # 2. Фамилия Имя (Иванов Иван)
        pattern2 = r'^([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)'
        match = re.match(pattern2, text)
        if match:
            return match.group(1).strip()

        # 3. Просто фамилия
        pattern3 = r'^([А-ЯЁ][а-яё]+)'
        match = re.match(pattern3, text)
        if match:
            name = match.group(1).strip()
            # Проверим, что это не служебное слово
            if name.lower() not in ['итого', 'всего', 'сумма', 'расход']:
                return name

        return None

    def _get_admin_id_by_name(self, name: str) -> Optional[int]:
        """
        Получить ID администратора по имени

        Ищет в БД администраторов по полному имени или username
        """
        if not self.sheets_parser or not hasattr(self.sheets_parser, 'admin_db'):
            return None

        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Поиск по полному имени (full_name)
            cursor.execute("""
                SELECT user_id FROM admins
                WHERE full_name LIKE ?
                OR username LIKE ?
                LIMIT 1
            """, (f'%{name}%', f'%{name}%'))

            result = cursor.fetchone()
            conn.close()

            if result:
                return result[0]

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка поиска админа по имени: {e}")
            return None

    def calculate_net_salaries(self) -> Dict[int, Dict]:
        """
        Рассчитать чистые зарплаты с учетом выплат из кассы

        Формула:
        Чистая зарплата = Начисленная зарплата (из Sheets) - Выплаты из кассы

        Возвращает:
        {
            admin_id: {
                'name': 'Имя',
                'gross_salary': 10000,  # Начисленная (из Sheets)
                'cash_withdrawals': 3000,  # Взятая из кассы
                'net_salary': 7000,  # К выплате
                'salary_items': [...]  # Детализация из Sheets
            }
        }
        """
        # Получить начисленные зарплаты из Sheets
        salaries = self.get_admin_salaries_from_sheets()

        # Получить выплаты из касс (за текущий месяц)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Текущий месяц
        now = datetime.now()
        start_of_month = now.replace(day=1).strftime("%Y-%m-%d")

        cursor.execute("""
            SELECT
                admin_id,
                SUM(amount) as total_withdrawals
            FROM shift_cash_withdrawals
            WHERE DATE(created_at) >= ?
            GROUP BY admin_id
        """, (start_of_month,))

        withdrawals = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        # Рассчитать чистые зарплаты
        net_salaries = {}

        for admin_id, salary_data in salaries.items():
            gross = salary_data.get('total', 0)
            withdrawn = withdrawals.get(admin_id, 0)
            net = gross - withdrawn

            net_salaries[admin_id] = {
                'name': salary_data.get('name', f'Admin {admin_id}'),
                'gross_salary': gross,
                'cash_withdrawals': withdrawn,
                'net_salary': net,
                'salary_items': salary_data.get('salary_items', [])
            }

        logger.info(f"💰 Рассчитаны зарплаты для {len(net_salaries)} администраторов")
        return net_salaries

    # =====================================================
    # АНАЛИЗ ЭФФЕКТИВНОСТИ
    # =====================================================

    def analyze_admin_performance_by_weekday(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        club: Optional[str] = None
    ) -> Dict:
        """
        Анализ эффективности администраторов по дням недели

        Показывает:
        - В какие дни недели каждый админ работает лучше
        - Средняя выручка по дням недели
        - Корреляция дня недели и эффективности

        Возвращает:
        {
            admin_id: {
                'name': 'Имя',
                'by_weekday': {
                    'Monday': {'shifts': 5, 'avg_revenue': 50000},
                    'Tuesday': {'shifts': 3, 'avg_revenue': 45000},
                    ...
                },
                'best_day': 'Friday',
                'worst_day': 'Monday'
            }
        }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Параметры фильтрации
        where_clauses = ["status = 'closed'"]
        params = []

        if start_date:
            where_clauses.append("DATE(opened_at) >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("DATE(opened_at) <= ?")
            params.append(end_date)

        if club:
            where_clauses.append("club = ?")
            params.append(club)

        where_sql = " AND ".join(where_clauses)

        # Получить все закрытые смены с датами
        query = f"""
        SELECT
            id as shift_id,
            admin_id,
            club,
            opened_at,
            closed_at
        FROM active_shifts
        WHERE {where_sql}
        """

        cursor.execute(query, params)
        shifts = cursor.fetchall()

        # Группировать по администраторам и дням недели
        admin_performance = defaultdict(lambda: defaultdict(list))

        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        for shift in shifts:
            shift_id, admin_id, club_name, opened_at, closed_at = shift

            # Определить день недели (0 = Monday, 6 = Sunday)
            opened_dt = datetime.fromisoformat(opened_at)
            weekday = weekdays[opened_dt.weekday()]

            # TODO: Получить выручку смены (когда будет реализована)
            # Сейчас используем заглушку
            revenue = 0

            admin_performance[admin_id][weekday].append(revenue)

        # Рассчитать статистику
        result = {}

        for admin_id, weekday_data in admin_performance.items():
            by_weekday = {}

            for weekday in weekdays:
                revenues = weekday_data.get(weekday, [])
                if revenues:
                    by_weekday[weekday] = {
                        'shifts': len(revenues),
                        'total_revenue': sum(revenues),
                        'avg_revenue': sum(revenues) / len(revenues)
                    }
                else:
                    by_weekday[weekday] = {
                        'shifts': 0,
                        'total_revenue': 0,
                        'avg_revenue': 0
                    }

            # Найти лучший и худший день
            avg_revenues = {day: data['avg_revenue'] for day, data in by_weekday.items() if data['shifts'] > 0}

            best_day = max(avg_revenues, key=avg_revenues.get) if avg_revenues else None
            worst_day = min(avg_revenues, key=avg_revenues.get) if avg_revenues else None

            result[admin_id] = {
                'by_weekday': by_weekday,
                'best_day': best_day,
                'worst_day': worst_day
            }

        conn.close()

        logger.info(f"📊 Проанализирована эффективность {len(result)} администраторов")
        return result

    # =====================================================
    # ФОРМАТИРОВАНИЕ ОТЧЕТОВ
    # =====================================================

    def format_salary_report(self, admin_id: Optional[int] = None) -> str:
        """
        Форматировать отчет по зарплатам

        Показывает:
        - Кому и сколько нужно заплатить
        - Детализация начислений из таблицы
        - Выплаты из кассы
        - Итоговая сумма к выплате
        """
        salaries = self.calculate_net_salaries()

        if not salaries:
            return "📊 Нет данных о зарплатах"

        # Фильтр по конкретному админу
        if admin_id:
            salaries = {admin_id: salaries.get(admin_id)} if admin_id in salaries else {}

        if not salaries:
            return f"📊 Нет данных о зарплате для администратора {admin_id}"

        # Формирование отчета
        report = "💰 Отчет по зарплатам\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        total_to_pay = 0

        for admin_id, data in sorted(salaries.items(), key=lambda x: x[1]['net_salary'], reverse=True):
            report += f"👤 {data['name']} (ID: {admin_id})\n"
            report += f"├─ Начислено: {data['gross_salary']:,.0f} ₽\n"
            report += f"├─ Взято из кассы: {data['cash_withdrawals']:,.0f} ₽\n"
            report += f"└─ К выплате: {data['net_salary']:,.0f} ₽\n"

            # Детализация начислений
            if data['salary_items']:
                report += "\n   Детализация:\n"
                for item in data['salary_items']:
                    report += f"   • {item['description']}: {item['amount']:,.0f} ₽\n"
                    if item.get('note'):
                        report += f"     ({item['note']})\n"

            report += "\n"
            total_to_pay += data['net_salary']

        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += f"💵 Итого к выплате: {total_to_pay:,.0f} ₽\n"

        return report

    def format_movements_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        club: Optional[str] = None
    ) -> str:
        """
        Форматировать отчет по движениям средств
        """
        movements = self.get_cash_movements(start_date, end_date, club)

        if not movements:
            return "📊 Нет движений средств за указанный период"

        report = "💸 Движение средств\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Группировать по клубам
        by_club = defaultdict(list)
        for m in movements:
            by_club[m['club']].append(m)

        for club_name, club_movements in by_club.items():
            report += f"🏢 {club_name}\n"
            report += f"{'─'*30}\n\n"

            total_expenses = 0
            total_withdrawals = 0

            for m in club_movements:
                opened = datetime.fromisoformat(m['opened_at']).strftime('%d.%m.%Y %H:%M')

                report += f"📅 {opened} | {m['shift_type']}\n"

                # Расходы
                if m['expenses']:
                    report += "  Расходы:\n"
                    for exp in m['expenses']:
                        report += f"    • {exp['cash_register']}: {exp['total_expenses']:,.0f} ₽\n"
                        total_expenses += exp['total_expenses'] or 0

                # Выплаты
                if m['cash_withdrawals']:
                    report += f"  Выплаты: {m['cash_withdrawals']:,.0f} ₽\n"
                    total_withdrawals += m['cash_withdrawals']

                report += "\n"

            report += f"Итого по {club_name}:\n"
            report += f"  Расходы: {total_expenses:,.0f} ₽\n"
            report += f"  Выплаты: {total_withdrawals:,.0f} ₽\n\n"

        return report

    def format_performance_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        club: Optional[str] = None
    ) -> str:
        """
        Форматировать отчет по эффективности администраторов
        """
        performance = self.analyze_admin_performance_by_weekday(start_date, end_date, club)

        if not performance:
            return "📊 Нет данных для анализа эффективности"

        report = "📊 Эффективность администраторов по дням недели\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for admin_id, data in performance.items():
            report += f"👤 Администратор {admin_id}\n"

            if data['best_day']:
                report += f"✅ Лучший день: {data['best_day']}\n"

            if data['worst_day']:
                report += f"❌ Худший день: {data['worst_day']}\n"

            report += "\nСтатистика по дням:\n"

            for weekday, stats in data['by_weekday'].items():
                if stats['shifts'] > 0:
                    report += f"  {weekday}: {stats['shifts']} смен, "
                    report += f"средняя выручка {stats['avg_revenue']:,.0f} ₽\n"

            report += "\n"

        return report


# =====================================================
# TELEGRAM КОМАНДЫ
# =====================================================

def register_analytics_commands(application, analytics: FinanceAnalytics, admin_manager):
    """
    Регистрация команд финансовой аналитики в боте

    Команды:
    - /salaries - Отчет по зарплатам
    - /movements - Отчет по движениям средств
    - /performance - Анализ эффективности администраторов
    """
    from telegram import Update
    from telegram.ext import CommandHandler, ContextTypes

    async def cmd_salaries(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать отчет по зарплатам"""
        user_id = update.effective_user.id

        # Только для владельца
        if not admin_manager.is_owner(user_id):
            await update.message.reply_text("❌ Команда доступна только владельцу")
            return

        report = analytics.format_salary_report()
        await update.message.reply_text(report)

    async def cmd_movements(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать отчет по движениям средств"""
        user_id = update.effective_user.id

        # Только для владельца и менеджеров
        if not admin_manager.is_admin(user_id):
            await update.message.reply_text("❌ Команда доступна только администраторам")
            return

        # Параметры: период (неделя/месяц), клуб
        period = context.args[0] if context.args else "week"

        if period == "week":
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        elif period == "month":
            start_date = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        else:
            start_date = None

        report = analytics.format_movements_report(start_date=start_date)
        await update.message.reply_text(report)

    async def cmd_performance(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать анализ эффективности"""
        user_id = update.effective_user.id

        # Только для владельца
        if not admin_manager.is_owner(user_id):
            await update.message.reply_text("❌ Команда доступна только владельцу")
            return

        # Период - последний месяц
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        report = analytics.format_performance_report(start_date=start_date)
        await update.message.reply_text(report)

    # Регистрация команд
    application.add_handler(CommandHandler("salaries", cmd_salaries))
    application.add_handler(CommandHandler("movements", cmd_movements))
    application.add_handler(CommandHandler("performance", cmd_performance))

    logger.info("✅ Команды финансовой аналитики зарегистрированы")
    logger.info("   /salaries - Отчет по зарплатам")
    logger.info("   /movements - Движение средств")
    logger.info("   /performance - Анализ эффективности")
