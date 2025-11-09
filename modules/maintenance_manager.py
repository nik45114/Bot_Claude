"""
Модуль управления задачами обслуживания оборудования
- Автораспределение задач по админам пропорционально сменам
- Чистка клавиатур/мышей раз в месяц
- Продувка ПК раз в 2 месяца
- Фотоотчеты по выполнению
"""

import sqlite3
import logging
from datetime import datetime, timedelta, date, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))

logger = logging.getLogger(__name__)


class MaintenanceManager:
    """Менеджер задач обслуживания"""

    def __init__(self, db_path: str = "knowledge.db"):
        self.db_path = db_path

    def _get_admin_shift_distribution(self, days_back: int = 60) -> Dict[int, Dict[str, int]]:
        """
        Получить распределение смен по админам и клубам за период
        Использует таблицу duty_schedule (график смен) для подсчета

        Returns:
            {admin_id: {'rio': count, 'sever': count, 'total': count}}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            since_date = (datetime.now(MSK) - timedelta(days=days_back)).strftime('%Y-%m-%d')

            # Получаем смены из графика duty_schedule
            # Присоединяем таблицу admins чтобы получить admin_id по ФИО
            cursor.execute("""
                SELECT ds.admin_id, ds.club, COUNT(*) as shift_count
                FROM duty_schedule ds
                WHERE ds.date >= ?
                AND ds.admin_id IS NOT NULL
                GROUP BY ds.admin_id, ds.club
            """, (since_date,))

            distribution = defaultdict(lambda: {'rio': 0, 'sever': 0, 'total': 0})

            for admin_id, club, count in cursor.fetchall():
                # Нормализуем название клуба
                if club:
                    club_normalized = club.lower()
                    # Приводим русские названия к английским
                    if club_normalized in ['рио', 'rio']:
                        club_key = 'rio'
                    elif club_normalized in ['север', 'sever']:
                        club_key = 'sever'
                    else:
                        club_key = 'rio'  # default
                else:
                    club_key = 'rio'

                distribution[admin_id][club_key] = count
                distribution[admin_id]['total'] += count

            conn.close()
            return dict(distribution)

        except Exception as e:
            logger.error(f"❌ Error getting shift distribution: {e}")
            return {}

    def assign_tasks_proportionally(self, task_type: str = 'all'):
        """
        Автоматически распределить задачи пропорционально сменам

        Args:
            task_type: 'keyboard', 'mouse', 'pc', 'all'
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получить распределение смен
            shift_dist = self._get_admin_shift_distribution()

            if not shift_dist:
                logger.warning("⚠️ No shifts found, cannot assign tasks")
                return

            # Получить типы задач
            task_types_query = "SELECT id, equipment_type, frequency_days FROM maintenance_task_types WHERE is_active = 1"
            if task_type != 'all':
                task_types_query += f" AND equipment_type = '{task_type}'"

            cursor.execute(task_types_query)
            task_types = cursor.fetchall()

            for task_type_id, equipment_type, frequency_days in task_types:
                # Для каждого клуба
                for club in ['rio', 'sever']:
                    # Получить оборудование этого типа в клубе
                    cursor.execute("""
                        SELECT id, inventory_number, pc_number
                        FROM equipment_inventory
                        WHERE club = ? AND equipment_type = ? AND is_active = 1
                        ORDER BY pc_number
                    """, (club, equipment_type))

                    equipment_list = cursor.fetchall()

                    if not equipment_list:
                        continue

                    # Распределить оборудование по админам пропорционально сменам
                    admin_shifts_in_club = [
                        (admin_id, data[club])
                        for admin_id, data in shift_dist.items()
                        if data[club] > 0
                    ]

                    if not admin_shifts_in_club:
                        continue

                    # Сортируем по количеству смен (по убыванию)
                    admin_shifts_in_club.sort(key=lambda x: x[1], reverse=True)

                    total_shifts = sum(shifts for _, shifts in admin_shifts_in_club)
                    equipment_count = len(equipment_list)

                    # Распределяем оборудование
                    equipment_index = 0

                    for admin_id, shifts in admin_shifts_in_club:
                        # Количество оборудования для этого админа
                        equipment_portion = int((shifts / total_shifts) * equipment_count)

                        if equipment_portion == 0 and shifts > 0:
                            equipment_portion = 1  # Хотя бы одно

                        for _ in range(equipment_portion):
                            if equipment_index >= len(equipment_list):
                                break

                            equipment_id, inv_num, pc_num = equipment_list[equipment_index]

                            # Проверить есть ли уже активная задача
                            cursor.execute("""
                                SELECT id FROM maintenance_tasks
                                WHERE admin_id = ?
                                AND equipment_id = ?
                                AND task_type_id = ?
                                AND status IN ('pending', 'in_progress')
                            """, (admin_id, equipment_id, task_type_id))

                            if not cursor.fetchone():
                                # Создать задачу
                                assigned_date = datetime.now(MSK).date()
                                due_date = assigned_date + timedelta(days=frequency_days)

                                cursor.execute("""
                                    INSERT INTO maintenance_tasks
                                    (admin_id, club, equipment_id, task_type_id, assigned_date, due_date, status)
                                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                                """, (admin_id, club, equipment_id, task_type_id, assigned_date, due_date))

                                logger.info(f"✅ Assigned task {equipment_type} {inv_num} to admin {admin_id}")

                            equipment_index += 1

            conn.commit()
            conn.close()
            logger.info("✅ Tasks assigned successfully")

        except Exception as e:
            logger.error(f"❌ Error assigning tasks: {e}")

    def get_admin_tasks(self, admin_id: int, status: str = None) -> List[Dict]:
        """Получить задачи админа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = """
                SELECT
                    mt.id,
                    mt.club,
                    ei.equipment_type,
                    ei.inventory_number,
                    ei.pc_number,
                    mtt.task_name,
                    mt.due_date,
                    mt.status,
                    mt.photo_file_id,
                    mt.notes
                FROM maintenance_tasks mt
                JOIN equipment_inventory ei ON mt.equipment_id = ei.id
                JOIN maintenance_task_types mtt ON mt.task_type_id = mtt.id
                WHERE mt.admin_id = ?
            """

            params = [admin_id]

            if status:
                query += " AND mt.status = ?"
                params.append(status)

            query += " ORDER BY mt.due_date ASC"

            cursor.execute(query, params)

            tasks = []
            for row in cursor.fetchall():
                tasks.append({
                    'id': row[0],
                    'club': row[1],
                    'equipment_type': row[2],
                    'inventory_number': row[3],
                    'pc_number': row[4],
                    'task_name': row[5],
                    'due_date': row[6],
                    'status': row[7],
                    'photo_file_id': row[8],
                    'notes': row[9]
                })

            conn.close()
            return tasks

        except Exception as e:
            logger.error(f"❌ Error getting admin tasks: {e}")
            return []

    def complete_task(self, task_id: int, photo_file_id: str = None, notes: str = None) -> bool:
        """Отметить задачу как выполненную"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получить информацию о задаче
            cursor.execute("""
                SELECT admin_id, equipment_id, task_type_id
                FROM maintenance_tasks
                WHERE id = ?
            """, (task_id,))

            task_info = cursor.fetchone()

            if not task_info:
                return False

            admin_id, equipment_id, task_type_id = task_info

            # Обновить задачу
            cursor.execute("""
                UPDATE maintenance_tasks
                SET status = 'completed',
                    completed_date = ?,
                    photo_file_id = ?,
                    notes = ?
                WHERE id = ?
            """, (datetime.now(MSK), photo_file_id, notes, task_id))

            # Добавить в историю
            cursor.execute("""
                INSERT INTO maintenance_history
                (task_id, admin_id, equipment_id, task_type_id, completed_at, photo_file_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, admin_id, equipment_id, task_type_id, datetime.now(MSK), photo_file_id, notes))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error completing task: {e}")
            return False

    def check_overdue_tasks(self):
        """Проверить просроченные задачи и обновить их статус"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now(MSK).date()

            cursor.execute("""
                UPDATE maintenance_tasks
                SET status = 'overdue'
                WHERE status = 'pending'
                AND due_date < ?
            """, (today,))

            updated = cursor.rowcount

            conn.commit()
            conn.close()

            if updated > 0:
                logger.info(f"⚠️ {updated} tasks marked as overdue")

            return updated

        except Exception as e:
            logger.error(f"❌ Error checking overdue tasks: {e}")
            return 0
