#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2Ray Server Manager
Модуль для управления V2Ray серверами через бота
"""

import paramiko
import json
import uuid
import logging
from typing import Optional, Dict, List
import sqlite3

logger = logging.getLogger(__name__)


class V2RayServer:
    """Класс для работы с одним V2Ray сервером"""
    
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssh = None
    
    def connect(self) -> bool:
        """Подключение к серверу по SSH"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10
            )
            logger.info(f"✅ Подключено к {self.host}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к {self.host}: {e}")
            return False
    
    def disconnect(self):
        """Отключение от сервера"""
        if self.ssh:
            self.ssh.close()
            self.ssh = None
    
    def execute_command(self, command: str) -> tuple:
        """Выполнение команды на сервере"""
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            return exit_status, output, error
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения команды: {e}")
            return 1, "", str(e)
    
    def install_v2ray(self) -> bool:
        """Установка V2Ray на сервер"""
        try:
            logger.info(f"📥 Установка V2Ray на {self.host}...")
            
            # Установка V2Ray
            commands = [
                "apt update",
                "apt install -y curl",
                "bash <(curl -L https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh)"
            ]
            
            for cmd in commands:
                status, output, error = self.execute_command(cmd)
                if status != 0:
                    logger.error(f"Ошибка: {error}")
                    return False
            
            logger.info("✅ V2Ray установлен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки V2Ray: {e}")
            return False
    
    def create_config(self, port: int = 443, traffic_type: str = "tls") -> Dict:
        """Создание конфигурации V2Ray"""
        
        config = {
            "inbounds": [{
                "port": port,
                "protocol": "vless",
                "settings": {
                    "clients": [],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "tcp"
                }
            }],
            "outbounds": [{
                "protocol": "freedom",
                "settings": {}
            }]
        }
        
        # Настройка маскировки трафика
        if traffic_type == "tls":
            config["inbounds"][0]["streamSettings"]["security"] = "tls"
            config["inbounds"][0]["streamSettings"]["tlsSettings"] = {
                "certificates": [{
                    "certificateFile": "/etc/v2ray/cert.crt",
                    "keyFile": "/etc/v2ray/cert.key"
                }]
            }
        elif traffic_type == "ws":
            config["inbounds"][0]["streamSettings"]["network"] = "ws"
            config["inbounds"][0]["streamSettings"]["wsSettings"] = {
                "path": "/v2ray"
            }
        elif traffic_type == "grpc":
            config["inbounds"][0]["streamSettings"]["network"] = "grpc"
            config["inbounds"][0]["streamSettings"]["grpcSettings"] = {
                "serviceName": "v2ray"
            }
        
        return config
    
    def deploy_config(self, config: Dict) -> bool:
        """Загрузка конфигурации на сервер"""
        try:
            config_json = json.dumps(config, indent=2)
            
            # Создаём временный файл
            temp_file = "/tmp/v2ray_config.json"
            self.execute_command(f"echo '{config_json}' > {temp_file}")
            
            # Перемещаем в /etc/v2ray/
            self.execute_command("mkdir -p /etc/v2ray")
            self.execute_command(f"mv {temp_file} /etc/v2ray/config.json")
            
            # Перезапускаем V2Ray
            self.execute_command("systemctl restart v2ray")
            self.execute_command("systemctl enable v2ray")
            
            logger.info("✅ Конфигурация применена")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка применения конфигурации: {e}")
            return False
    
    def add_user(self, user_id: str, email: str = "") -> Optional[str]:
        """Добавление пользователя и генерация VLESS ссылки"""
        try:
            # Генерируем UUID
            user_uuid = str(uuid.uuid4())
            
            # Читаем текущую конфигурацию
            status, config_text, error = self.execute_command("cat /etc/v2ray/config.json")
            
            if status != 0:
                logger.error("Не удалось прочитать конфигурацию")
                return None
            
            config = json.loads(config_text)
            
            # Добавляем пользователя
            new_client = {
                "id": user_uuid,
                "email": email or f"user_{user_id}"
            }
            
            config["inbounds"][0]["settings"]["clients"].append(new_client)
            
            # Сохраняем конфигурацию
            if not self.deploy_config(config):
                return None
            
            # Генерируем VLESS ссылку
            port = config["inbounds"][0]["port"]
            network = config["inbounds"][0]["streamSettings"]["network"]
            security = config["inbounds"][0]["streamSettings"].get("security", "none")
            
            vless_link = f"vless://{user_uuid}@{self.host}:{port}"
            vless_link += f"?type={network}&security={security}"
            
            if network == "ws":
                path = config["inbounds"][0]["streamSettings"]["wsSettings"]["path"]
                vless_link += f"&path={path}"
            elif network == "grpc":
                service = config["inbounds"][0]["streamSettings"]["grpcSettings"]["serviceName"]
                vless_link += f"&serviceName={service}"
            
            vless_link += f"#{email or user_id}"
            
            logger.info(f"✅ Пользователь {user_id} добавлен")
            return vless_link
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления пользователя: {e}")
            return None
    
    def remove_user(self, user_uuid: str) -> bool:
        """Удаление пользователя"""
        try:
            # Читаем конфигурацию
            status, config_text, error = self.execute_command("cat /etc/v2ray/config.json")
            config = json.loads(config_text)
            
            # Удаляем пользователя
            clients = config["inbounds"][0]["settings"]["clients"]
            config["inbounds"][0]["settings"]["clients"] = [
                c for c in clients if c["id"] != user_uuid
            ]
            
            # Сохраняем
            if self.deploy_config(config):
                logger.info(f"✅ Пользователь {user_uuid} удалён")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления пользователя: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Получение статистики сервера"""
        try:
            # Статус сервиса
            status, output, _ = self.execute_command("systemctl status v2ray")
            is_running = "active (running)" in output
            
            # Количество пользователей
            status, config_text, _ = self.execute_command("cat /etc/v2ray/config.json")
            config = json.loads(config_text)
            user_count = len(config["inbounds"][0]["settings"]["clients"])
            
            # Порт
            port = config["inbounds"][0]["port"]
            
            # Тип трафика
            network = config["inbounds"][0]["streamSettings"]["network"]
            
            return {
                "running": is_running,
                "users": user_count,
                "port": port,
                "network": network,
                "host": self.host
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}
    
    def change_traffic_type(self, traffic_type: str) -> bool:
        """Изменение типа маскировки трафика"""
        try:
            # Читаем конфигурацию
            status, config_text, _ = self.execute_command("cat /etc/v2ray/config.json")
            config = json.loads(config_text)
            
            # Меняем тип трафика
            if traffic_type == "tcp":
                config["inbounds"][0]["streamSettings"]["network"] = "tcp"
                config["inbounds"][0]["streamSettings"].pop("security", None)
                config["inbounds"][0]["streamSettings"].pop("wsSettings", None)
                config["inbounds"][0]["streamSettings"].pop("grpcSettings", None)
            
            elif traffic_type == "ws":
                config["inbounds"][0]["streamSettings"]["network"] = "ws"
                config["inbounds"][0]["streamSettings"]["wsSettings"] = {
                    "path": "/v2ray"
                }
            
            elif traffic_type == "grpc":
                config["inbounds"][0]["streamSettings"]["network"] = "grpc"
                config["inbounds"][0]["streamSettings"]["grpcSettings"] = {
                    "serviceName": "v2ray"
                }
            
            elif traffic_type == "tls":
                config["inbounds"][0]["streamSettings"]["security"] = "tls"
            
            # Сохраняем
            if self.deploy_config(config):
                logger.info(f"✅ Тип трафика изменён на {traffic_type}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка изменения типа трафика: {e}")
            return False


class V2RayManager:
    """Менеджер V2Ray серверов"""
    
    def __init__(self, db_path: str = 'knowledge.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация таблицы серверов"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS v2ray_servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                host TEXT NOT NULL,
                port INTEGER DEFAULT 22,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                v2ray_port INTEGER DEFAULT 443,
                traffic_type TEXT DEFAULT 'tcp',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS v2ray_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                uuid TEXT NOT NULL,
                email TEXT,
                vless_link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (server_id) REFERENCES v2ray_servers(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_server(self, name: str, host: str, username: str, password: str, 
                   port: int = 22, v2ray_port: int = 443) -> bool:
        """Добавление сервера в базу"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO v2ray_servers (name, host, port, username, password, v2ray_port)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, host, port, username, password, v2ray_port))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Сервер {name} добавлен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления сервера: {e}")
            return False
    
    def get_server(self, name: str) -> Optional[V2RayServer]:
        """Получение сервера по имени"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT host, port, username, password 
                FROM v2ray_servers 
                WHERE name = ? AND is_active = 1
            ''', (name,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return V2RayServer(row[0], row[1], row[2], row[3])
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сервера: {e}")
            return None
    
    def list_servers(self) -> List[Dict]:
        """Список всех серверов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, host, v2ray_port, traffic_type 
                FROM v2ray_servers 
                WHERE is_active = 1
            ''')
            
            servers = []
            for row in cursor.fetchall():
                servers.append({
                    'id': row[0],
                    'name': row[1],
                    'host': row[2],
                    'port': row[3],
                    'traffic_type': row[4]
                })
            
            conn.close()
            return servers
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка серверов: {e}")
            return []
    
    def save_user(self, server_name: str, user_id: str, uuid: str, 
                  vless_link: str, email: str = "") -> bool:
        """Сохранение пользователя в базу"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем server_id
            cursor.execute('SELECT id FROM v2ray_servers WHERE name = ?', (server_name,))
            server_id = cursor.fetchone()[0]
            
            cursor.execute('''
                INSERT INTO v2ray_users (server_id, user_id, uuid, email, vless_link)
                VALUES (?, ?, ?, ?, ?)
            ''', (server_id, user_id, uuid, email, vless_link))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя: {e}")
            return False
