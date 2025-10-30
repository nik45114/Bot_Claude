#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebApp Server - Flask сервер для Telegram WebApp финансовой аналитики
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import logging
import sys
import os
from datetime import datetime, timedelta

# Добавить родительскую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finance_analytics import FinanceAnalytics
from modules.admins.db import AdminDB

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Инициализация модулей
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'club_assistant.db')
analytics = FinanceAnalytics(db_path=DB_PATH)
admin_db = AdminDB(DB_PATH)


# ============================================
# HTML ROUTES
# ============================================

@app.route('/')
def index():
    """Главная страница WebApp"""
    return render_template('analytics.html')


# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/analytics/overview')
def api_overview():
    """
    Обзор финансов за период

    Query params:
    - period: day|week|month (default: week)
    - user_id: Telegram user ID для проверки прав
    """
    period = request.args.get('period', 'week')
    user_id = request.args.get('user_id', type=int)

    # Определить даты периода
    end_date = datetime.now()
    if period == 'day':
        start_date = end_date - timedelta(days=1)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    else:  # week
        start_date = end_date - timedelta(days=7)

    try:
        # Получить движения средств
        movements = analytics.get_cash_movements(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

        # Подсчитать статистику
        total_revenue = 0
        total_expenses = 0
        expenses_count = 0
        shifts_count = len(movements)

        clubs_data = {}

        for m in movements:
            # Выручка (TODO: добавить поле revenue в БД)
            # Пока считаем 0, когда будет поле - заменим
            revenue = 0
            total_revenue += revenue

            # Расходы
            for exp in m.get('expenses', []):
                total_expenses += exp.get('total_expenses', 0) or 0
                expenses_count += 1

            # По клубам
            club = m.get('club', 'Неизвестно')
            if club not in clubs_data:
                clubs_data[club] = {'revenue': 0, 'shifts': 0}
            clubs_data[club]['revenue'] += revenue
            clubs_data[club]['shifts'] += 1

        # Зарплаты
        salaries = analytics.calculate_net_salaries()
        total_salaries = sum(s['net_salary'] for s in salaries.values())
        admins_count = len(salaries)

        # Прибыль
        net_profit = total_revenue - total_expenses - total_salaries
        profit_margin = round((net_profit / total_revenue * 100) if total_revenue > 0 else 0, 1)

        # Данные по клубам для графика
        clubs = [
            {'club': club, 'revenue': data['revenue']}
            for club, data in clubs_data.items()
        ]

        # Динамика за период (заглушка - TODO: реализовать по дням)
        trend = [
            {'date': (start_date + timedelta(days=i)).strftime('%d.%m'), 'revenue': 0}
            for i in range((end_date - start_date).days + 1)
        ]

        return jsonify({
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'total_salaries': total_salaries,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'shifts_count': shifts_count,
            'expenses_count': expenses_count,
            'admins_count': admins_count,
            'clubs': clubs,
            'trend': trend
        })

    except Exception as e:
        logger.error(f"Error in overview API: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/revenue')
def api_revenue():
    """
    Выручка за период

    Query params:
    - period: day|week|month
    - user_id: Telegram user ID
    """
    period = request.args.get('period', 'week')

    # TODO: Реализовать получение выручки из БД
    # Сейчас заглушка

    return jsonify({
        'total': 150000,
        'payment_types': {
            'cash': 50000,
            'card': 80000,
            'qr': 20000
        },
        'by_club': [
            {'club': 'Рио', 'revenue': 80000},
            {'club': 'Север', 'revenue': 70000}
        ]
    })


@app.route('/api/analytics/admins')
def api_admins():
    """
    Рейтинг администраторов

    Query params:
    - period: day|week|month
    - user_id: Telegram user ID
    """
    period = request.args.get('period', 'week')

    # Определить даты периода
    end_date = datetime.now()
    if period == 'day':
        start_date = end_date - timedelta(days=1)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    else:  # week
        start_date = end_date - timedelta(days=7)

    try:
        # Получить реальных админов из БД
        with analytics._get_db() as conn:
            cursor = conn.cursor()

            # Получить статистику смен каждого админа за период
            cursor.execute("""
                SELECT
                    a.user_id,
                    a.full_name,
                    COUNT(s.shift_id) as shifts_count,
                    SUM(s.total_revenue) as total_revenue,
                    AVG(s.total_revenue) as avg_revenue
                FROM admins a
                LEFT JOIN finmon_shifts s ON a.user_id = s.admin_id
                    AND s.closed_at IS NOT NULL
                    AND DATE(s.closed_at) BETWEEN ? AND ?
                GROUP BY a.user_id, a.full_name
                HAVING shifts_count > 0
                ORDER BY total_revenue DESC
            """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

            rows = cursor.fetchall()

            admins_list = []
            for row in rows:
                user_id, full_name, shifts_count, total_revenue, avg_revenue = row
                admins_list.append({
                    'name': full_name or f'Админ #{user_id}',
                    'shifts': shifts_count,
                    'revenue': int(total_revenue or 0),
                    'avg_revenue': int(avg_revenue or 0)
                })

            return jsonify({'admins': admins_list})

    except Exception as e:
        logger.error(f"Ошибка в api_admins: {e}")
        return jsonify({'error': str(e), 'admins': []}), 500


@app.route('/api/analytics/salaries')
def api_salaries():
    """
    Зарплаты администраторов

    Query params:
    - user_id: Telegram user ID
    """
    user_id = request.args.get('user_id', type=int)

    # Проверка прав (только владелец)
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    try:
        # Получить зарплаты
        salaries = analytics.calculate_net_salaries()

        # Форматировать для фронтенда
        salaries_list = []
        total_to_pay = 0

        for admin_id, data in salaries.items():
            salaries_list.append({
                'admin_id': admin_id,
                'name': data['name'],
                'gross': data['gross_salary'],
                'withdrawn': data['cash_withdrawals'],
                'net': data['net_salary']
            })
            total_to_pay += data['net_salary']

        # Сортировка по сумме к выплате
        salaries_list.sort(key=lambda x: x['net'], reverse=True)

        return jsonify({
            'salaries': salaries_list,
            'total_to_pay': total_to_pay,
            'admins_count': len(salaries_list)
        })

    except Exception as e:
        logger.error(f"Error in salaries API: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/efficiency')
def api_efficiency():
    """
    Анализ эффективности по дням недели

    Query params:
    - user_id: Telegram user ID
    """
    user_id = request.args.get('user_id', type=int)

    try:
        # Получить анализ эффективности
        performance = analytics.analyze_admin_performance_by_weekday()

        # Форматировать для графика
        by_weekday = []
        top_performers = []

        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        for admin_id, data in list(performance.items())[:5]:  # Топ 5 админов
            # Получить имя админа
            admin_name = f'Админ {admin_id}'

            # Данные по дням недели
            values = [
                data['by_weekday'].get(day, {}).get('avg_revenue', 0)
                for day in weekdays
            ]

            by_weekday.append({
                'name': admin_name,
                'values': values
            })

            # Лучшие показатели
            if data['best_day']:
                best_revenue = data['by_weekday'][data['best_day']]['avg_revenue']
                top_performers.append({
                    'name': admin_name,
                    'best_day': data['best_day'],
                    'best_revenue': best_revenue
                })

        # Сортировка топа по лучшей выручке
        top_performers.sort(key=lambda x: x['best_revenue'], reverse=True)

        return jsonify({
            'by_weekday': by_weekday,
            'top_performers': top_performers[:5]
        })

    except Exception as e:
        logger.error(f"Error in efficiency API: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# HEALTH CHECK
# ============================================

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Запуск сервера
    port = int(os.environ.get('WEBAPP_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    logger.info(f"🌐 Starting WebApp server on port {port}")
    logger.info(f"📊 Analytics module initialized with DB: {DB_PATH}")

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
