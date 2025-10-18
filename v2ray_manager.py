#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2Ray Manager с REALITY протоколом
Управление V2Ray/Xray серверами через SSH
"""

import sqlite3
import json
import paramiko
import uuid
import base64
import subprocess
import logging
import urllib.parse
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class V2RayServer:
    """Класс для работы с V2Ray сервером"""
    
    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.ssh_client = None
    
    def connect(self) -> bool:
        """Подключение к серверу по SSH"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10
            )
            logger.info(f"✅ Подключен к {self.host}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к {self.host}: {e}")
            return False
    
    def disconnect(self):
        """Отключение от сервера"""
        if self.ssh_client:
            self.ssh_client.close()
            logger.info(f"🔌 Отключен от {self.host}")
    
    def _exec_command(self, command: str, timeout: int = 30) -> tuple:
        """Выполнение команды на сервере"""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode('utf-8')
            err = stderr.read().decode('utf-8')
            return exit_code, out, err
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения команды: {e}")
            return 1, "", str(e)
    
    def install_v2ray(self, force: bool = False) -> bool:
        """Установка Xray на сервер"""
        try:
            # Проверка существующей установки
            if not force:
                logger.info("🔍 Проверяю установку Xray...")
                exit_code, out, err = self._exec_command('xray version', timeout=5)
                if exit_code == 0:
                    version_info = out.strip().split('\n')[0] if out else "Unknown"
                    logger.info(f"✅ Xray уже установлен: {version_info}")
                    logger.info("   Пропускаю установку. Используйте force=True для переустановки")
                    return True
                logger.info("📥 Xray не найден, начинаю установку...")
            
            logger.info("📥 Устанавливаю Xray...")
            
            # Установка Xray
            install_script = '''
#!/bin/bash
set -e

# Обновление системы
apt-get update

# Установка зависимостей
apt-get install -y curl unzip

# Установка Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Проверка установки
if command -v xray &> /dev/null; then
    echo "Xray установлен успешно"
    xray version
else
    echo "Ошибка установки Xray"
    exit 1
fi
'''
            
            # Загружаем скрипт на сервер
            sftp = self.ssh_client.open_sftp()
            with sftp.file('/tmp/install_xray.sh', 'w') as f:
                f.write(install_script)
            sftp.close()
            
            # Делаем скрипт исполняемым
            self._exec_command('chmod +x /tmp/install_xray.sh')
            
            # Запускаем установку
            exit_code, out, err = self._exec_command('bash /tmp/install_xray.sh', timeout=180)
            
            if exit_code == 0:
                logger.info("✅ Xray установлен успешно")
                return True
            else:
                logger.error(f"❌ Ошибка установки: {err}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка установки Xray: {e}")
            return False
    
    def generate_reality_keys(self) -> Dict:
        """Генерация ключей для REALITY"""
        try:
            # Генерируем ключи локально используя xray
            result = subprocess.run(
                ['xray', 'x25519'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                private_key = lines[0].split(':')[1].strip()
                public_key = lines[1].split(':')[1].strip()
                
                # Генерируем short ID (8 байт в hex = 16 символов)
                short_id = uuid.uuid4().hex[:16]
                
                return {
                    'private_key': private_key,
                    'public_key': public_key,
                    'short_id': short_id
                }
            else:
                # Если xray не установлен локально, генерируем на сервере
                return self._generate_keys_on_server()
                
        except FileNotFoundError:
            # xray не установлен локально
            return self._generate_keys_on_server()
        except Exception as e:
            logger.error(f"❌ Ошибка генерации ключей: {e}")
            return None
    
    def _generate_keys_on_server(self) -> Dict:
        """Генерация ключей на сервере"""
        try:
            exit_code, out, err = self._exec_command('xray x25519')
            
            if exit_code == 0:
                lines = out.strip().split('\n')
                private_key = lines[0].split(':')[1].strip()
                public_key = lines[1].split(':')[1].strip()
                short_id = uuid.uuid4().hex[:16]
                
                return {
                    'private_key': private_key,
                    'public_key': public_key,
                    'short_id': short_id
                }
            else:
                logger.error(f"❌ Ошибка генерации ключей на сервере: {err}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации ключей на сервере: {e}")
            return None
    
    def create_reality_config(self, port: int = 443, sni: str = "rutube.ru") -> Dict:
        """Создание конфигурации Xray с REALITY"""
        try:
            # Генерируем ключи
            keys = self.generate_reality_keys()
            if not keys:
                logger.error("❌ Не удалось сгенерировать ключи")
                return None
            
            config = {
                "log": {
                    "loglevel": "warning"
                },
                "inbounds": [
                    {
                        "port": port,
                        "protocol": "vless",
                        "settings": {
                            "clients": [],
                            "decryption": "none"
                        },
                        "streamSettings": {
                            "network": "tcp",
                            "security": "reality",
                            "realitySettings": {
                                "dest": f"{sni}:443",
                                "serverNames": [sni],
                                "privateKey": keys['private_key'],
                                "shortIds": [keys['short_id'], ""],
                                "spiderX": ""
                            },
                            "tcpSettings": {
                                "header": {
                                    "type": "none"
                                }
                            }
                        }
                    }
                ],
                "outbounds": [
                    {
                        "protocol": "freedom",
                        "tag": "direct"
                    },
                    {
                        "protocol": "blackhole",
                        "tag": "block"
                    }
                ]
            }
            
            # Сохраняем ключи для клиента (они понадобятся для генерации ссылок)
            config['_client_keys'] = {
                'public_key': keys['public_key'],
                'private_key': keys['private_key'],
                'short_id': keys['short_id']
            }
            
            return config
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания конфигурации: {e}")
            return None
    
    def deploy_config(self, config: Dict) -> bool:
        """Развёртывание конфигурации на сервере"""
        try:
            # Сохраняем ключи для клиента перед удалением
            client_keys = config.get('_client_keys', {})
            
            # Убираем служебные ключи перед сохранением
            config_to_save = config.copy()
            if '_client_keys' in config_to_save:
                del config_to_save['_client_keys']
            
            config_json = json.dumps(config_to_save, indent=2)
            
            # Загружаем конфигурацию на сервер
            sftp = self.ssh_client.open_sftp()
            with sftp.file('/usr/local/etc/xray/config.json', 'w') as f:
                f.write(config_json)
            
            # Сохраняем ключи в отдельный файл keys.json
            if client_keys:
                keys_json = json.dumps(client_keys, indent=2)
                try:
                    # Создаем директорию, если не существует
                    self._exec_command('mkdir -p /root/Xray-core')
                    with sftp.file('/root/Xray-core/keys.json', 'w') as f:
                        f.write(keys_json)
                    # Устанавливаем права доступа
                    self._exec_command('chmod 600 /root/Xray-core/keys.json')
                    logger.info("✅ Ключи сохранены в /root/Xray-core/keys.json")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось сохранить keys.json: {e}")
            
            sftp.close()
            
            # Перезапускаем Xray
            exit_code, out, err = self._exec_command('systemctl restart xray')
            
            if exit_code == 0:
                # Проверяем статус
                exit_code, out, err = self._exec_command('systemctl is-active xray')
                if 'active' in out:
                    logger.info("✅ Xray запущен успешно")
                    return True
                else:
                    logger.error(f"❌ Xray не запустился: {err}")
                    return False
            else:
                logger.error(f"❌ Ошибка перезапуска Xray: {err}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка развёртывания конфигурации: {e}")
            return False
    
    def add_user_reality(self, user_id: str, email: str = "", sni: str = "rutube.ru") -> str:
        """Добавление пользователя и генерация VLESS ссылки"""
        try:
            # Генерируем UUID на сервере командой xray uuid
            logger.info("🔑 Generating UUID on server...")
            exit_code, user_uuid, err = self._exec_command('/usr/local/bin/xray uuid')
            user_uuid = user_uuid.strip()
            
            # Если не сработало, пробуем другой путь
            if not user_uuid or exit_code != 0:
                logger.info("⚠️ /usr/local/bin/xray not found, trying ./xray...")
                exit_code, user_uuid, err = self._exec_command('./xray uuid')
                user_uuid = user_uuid.strip()
            
            # Если всё равно не сработало, пробуем python
            if not user_uuid or exit_code != 0:
                logger.info("⚠️ xray uuid failed, using python fallback...")
                exit_code, user_uuid, err = self._exec_command('python3 -c "import uuid; print(uuid.uuid4())"')
                user_uuid = user_uuid.strip()
            
            if not user_uuid:
                logger.error("❌ Failed to generate UUID on server")
                return None
            
            logger.info(f"✅ UUID generated on server: {user_uuid}")
            
            # Читаем текущую конфигурацию
            sftp = self.ssh_client.open_sftp()
            with sftp.file('/usr/local/etc/xray/config.json', 'r') as f:
                config = json.load(f)
            
            # Добавляем пользователя
            new_client = {
                "id": user_uuid,
                "email": email or user_id,
                "flow": "xtls-rprx-vision"
            }
            
            config['inbounds'][0]['settings']['clients'].append(new_client)
            
            # Сохраняем обновлённую конфигурацию
            with sftp.file('/usr/local/etc/xray/config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            sftp.close()
            
            # Перезапускаем Xray
            self._exec_command('systemctl restart xray')
            
            # Получаем публичный ключ из конфигурации
            reality_settings = config['inbounds'][0]['streamSettings']['realitySettings']
            
            # Генерируем публичный ключ из приватного (если его нет)
            # Для этого нужно выполнить xray x25519 на сервере
            exit_code, out, err = self._exec_command('xray x25519')
            
            # Парсим вывод для получения публичного ключа
            # Но проще сохранить его при создании конфигурации
            # Поэтому будем требовать, чтобы он был в БД
            
            # Формируем VLESS ссылку
            # Формат: vless://uuid@host:port?param=value#name
            
            params = [
                "encryption=none",
                "flow=xtls-rprx-vision",
                "security=reality",
                f"sni={sni}",
                "fp=chrome",
                # Публичный ключ и short_id нужно получить из БД
                # Они сохраняются при setup сервера
                "type=tcp"
            ]
            
            # Базовая ссылка без pbk и sid (они добавятся позже из БД)
            vless_link = f"vless://{user_uuid}@{self.host}:443?{'&'.join(params)}#{email or user_id}"
            
            logger.info(f"✅ Пользователь {user_id} добавлен")
            return vless_link
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления пользователя: {e}")
            return None
    
    def remove_user(self, user_uuid: str) -> bool:
        """Удаление пользователя"""
        try:
            # Читаем текущую конфигурацию
            sftp = self.ssh_client.open_sftp()
            with sftp.file('/usr/local/etc/xray/config.json', 'r') as f:
                config = json.load(f)
            
            # Удаляем пользователя
            clients = config['inbounds'][0]['settings']['clients']
            config['inbounds'][0]['settings']['clients'] = [
                c for c in clients if c['id'] != user_uuid
            ]
            
            # Сохраняем обновлённую конфигурацию
            with sftp.file('/usr/local/etc/xray/config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            sftp.close()
            
            # Перезапускаем Xray
            self._exec_command('systemctl restart xray')
            
            logger.info(f"✅ Пользователь {user_uuid} удалён")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления пользователя: {e}")
            return False
    
    def change_sni(self, new_sni: str) -> bool:
        """Изменение SNI (маскировки)"""
        try:
            # Читаем текущую конфигурацию
            sftp = self.ssh_client.open_sftp()
            with sftp.file('/usr/local/etc/xray/config.json', 'r') as f:
                config = json.load(f)
            
            # Изменяем SNI
            reality_settings = config['inbounds'][0]['streamSettings']['realitySettings']
            reality_settings['dest'] = f"{new_sni}:443"
            reality_settings['serverNames'] = [new_sni]
            
            # Сохраняем обновлённую конфигурацию
            with sftp.file('/usr/local/etc/xray/config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            sftp.close()
            
            # Перезапускаем Xray
            self._exec_command('systemctl restart xray')
            
            logger.info(f"✅ SNI изменён на {new_sni}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка изменения SNI: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Получение статистики сервера"""
        try:
            # Проверяем статус Xray
            exit_code, out, err = self._exec_command('systemctl is-active xray')
            is_running = 'active' in out
            
            # Читаем конфигурацию
            sftp = self.ssh_client.open_sftp()
            with sftp.file('/usr/local/etc/xray/config.json', 'r') as f:
                config = json.load(f)
            sftp.close()
            
            # Получаем информацию о пользователях
            clients = config['inbounds'][0]['settings']['clients']
            users_count = len(clients)
            
            # Получаем настройки
            inbound = config['inbounds'][0]
            port = inbound.get('port', 443)
            protocol = inbound.get('protocol', 'vless')
            
            reality_settings = inbound['streamSettings']['realitySettings']
            sni = reality_settings['serverNames'][0] if reality_settings['serverNames'] else 'unknown'
            
            return {
                'running': is_running,
                'host': self.host,
                'port': port,
                'protocol': protocol,
                'sni': sni,
                'users': users_count
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {
                'running': False,
                'host': self.host,
                'port': 443,
                'protocol': 'vless',
                'sni': 'unknown',
                'users': 0
            }


class V2RayManager:
    """Менеджер V2Ray серверов"""
    
    def __init__(self, db_path: str = 'knowledge.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица серверов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS v2ray_servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                host TEXT NOT NULL,
                port INTEGER DEFAULT 22,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                sni TEXT DEFAULT 'rutube.ru',
                public_key TEXT,
                private_key TEXT,
                short_id TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Проверяем и добавляем колонку private_key если её нет (для существующих БД)
        cursor.execute("PRAGMA table_info(v2ray_servers)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'private_key' not in columns:
            logger.info("🔧 Adding private_key column to v2ray_servers table")
            cursor.execute('ALTER TABLE v2ray_servers ADD COLUMN private_key TEXT')
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS v2ray_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                uuid TEXT NOT NULL UNIQUE,
                comment TEXT DEFAULT '',
                sni TEXT DEFAULT 'rutube.ru',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (server_name) REFERENCES v2ray_servers(name)
            )
        ''')
        
        # Таблица временного доступа
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS v2ray_temp_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name TEXT NOT NULL,
                uuid TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(server_name, uuid),
                FOREIGN KEY (server_name) REFERENCES v2ray_servers(name)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_server(self, name: str, host: str, username: str, password: str, 
                   port: int = 22, sni: str = "rutube.ru") -> bool:
        """Добавление сервера"""
        try:
            logger.info(f"🔍 add_server called with:")
            logger.info(f"  • name: {name}")
            logger.info(f"  • host: {host}")
            logger.info(f"  • port: {port}")
            logger.info(f"  • username: {username}")
            logger.info(f"  • sni: {sni}")
            
            logger.info(f"📂 Opening database: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            logger.info(f"📝 Executing INSERT query...")
            cursor.execute('''
                INSERT INTO v2ray_servers (name, host, port, username, password, sni)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, host, port, username, password, sni))
            
            logger.info(f"💾 Committing transaction...")
            conn.commit()
            
            logger.info(f"🔒 Closing connection...")
            conn.close()
            
            logger.info(f"✅ Сервер {name} добавлен успешно")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.error(f"❌ Database integrity error: {e}")
            logger.error(f"   Possible duplicate server name: {name}")
            return False
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Database operational error: {e}")
            logger.error(f"   Check if database file exists: {self.db_path}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error in add_server: {e}", exc_info=True)
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
                return V2RayServer(row[0], row[2], row[3], row[1])
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения сервера: {e}")
            return None
    
    def list_servers(self) -> List[Dict]:
        """Список серверов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, host, port, sni, username
                FROM v2ray_servers
                WHERE is_active = 1
            ''')
            
            servers = []
            for row in cursor.fetchall():
                servers.append({
                    'name': row[0],
                    'host': row[1],
                    'port': row[2],
                    'sni': row[3],
                    'username': row[4]
                })
            
            conn.close()
            return servers
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка серверов: {e}")
            return []
    
    def save_server_keys(self, server_name: str, public_key: str, short_id: str, private_key: str = '') -> bool:
        """Сохранение ключей сервера"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE v2ray_servers
                SET public_key = ?, private_key = ?, short_id = ?
                WHERE name = ?
            ''', (public_key, private_key, short_id, server_name))
            conn.commit()
            conn.close()
            logger.info(f"✅ Ключи сервера {server_name} сохранены")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения ключей: {e}")
            return False
    
    def get_server_keys(self, server_name: str) -> Dict:
        """Получение ключей сервера"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT public_key, short_id, sni
                FROM v2ray_servers
                WHERE name = ?
            ''', (server_name,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'public_key': row[0],
                    'short_id': row[1],
                    'sni': row[2] or 'rutube.ru'
                }
            else:
                return {}
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения ключей: {e}")
            return {}
    
    def save_user(self, server_name: str, user_id: str, user_uuid: str, 
                 vless_link: str, email: str = "") -> bool:
        """
        Сохранение пользователя (УСТАРЕВШИЙ МЕТОД - используйте add_user)
        
        ВАЖНО: vless_link должен уже содержать все необходимые параметры,
        включая pbk и sid. Этот метод больше не добавляет ключи.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем ID сервера
            cursor.execute('SELECT id FROM v2ray_servers WHERE name = ?', (server_name,))
            server_id = cursor.fetchone()[0]
            
            # Сохраняем пользователя с уже готовой ссылкой
            # Ключи должны быть добавлены до вызова этого метода
            cursor.execute('''
                INSERT INTO v2ray_users (server_id, user_id, uuid, email, vless_link)
                VALUES (?, ?, ?, ?, ?)
            ''', (server_id, user_id, user_uuid, email, vless_link))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ Пользователь {user_id} сохранён")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя: {e}")
            return False
    
    def add_user(self, server_name: str, user_id: str, comment: str = "") -> dict:
        """Добавление пользователя на сервер"""
        try:
            logger.info(f"🔍 add_user called:")
            logger.info(f"  • server_name: {server_name}")
            logger.info(f"  • user_id: {user_id}")
            logger.info(f"  • comment: {comment}")
            
            # Получаем информацию о сервере
            logger.info(f"📂 Getting server info...")
            server_info = self.get_server_info(server_name)
            
            if not server_info:
                logger.error(f"❌ Server {server_name} not found")
                return None
            
            logger.info(f"✅ Server found: {server_info['host']}")
            
            # Подключаемся к серверу
            logger.info(f"📝 Connecting to server...")
            server = V2RayServer(
                server_info['host'],
                server_info['username'],
                server_info['password'],
                server_info['port']
            )
            
            if not server.connect():
                logger.error(f"❌ Failed to connect to server")
                return None
            
            # Генерируем UUID НА СЕРВЕРЕ
            logger.info("🔑 Generating UUID on server...")
            exit_code, user_uuid, err = server._exec_command('/usr/local/bin/xray uuid')
            user_uuid = user_uuid.strip()
            
            # Если не сработало, пробуем другой путь
            if not user_uuid or exit_code != 0:
                logger.info("⚠️ /usr/local/bin/xray not found, trying ./xray...")
                exit_code, user_uuid, err = server._exec_command('./xray uuid')
                user_uuid = user_uuid.strip()
            
            # Если всё равно не сработало, пробуем python
            if not user_uuid or exit_code != 0:
                logger.info("⚠️ xray uuid failed, using python fallback...")
                exit_code, user_uuid, err = server._exec_command('python3 -c "import uuid; print(uuid.uuid4())"')
                user_uuid = user_uuid.strip()
            
            if not user_uuid:
                logger.error("❌ Failed to generate UUID on server")
                server.disconnect()
                return None
            
            logger.info(f"✅ UUID generated on server: {user_uuid}")
            
            # Читаем текущую конфигурацию
            sftp = server.ssh_client.open_sftp()
            with sftp.file('/usr/local/etc/xray/config.json', 'r') as f:
                config = json.load(f)
            
            # Добавляем пользователя
            sni = server_info.get('sni', 'rutube.ru')
            new_client = {
                "id": user_uuid,
                "email": comment or user_id,
                "flow": "xtls-rprx-vision"
            }
            
            config['inbounds'][0]['settings']['clients'].append(new_client)
            
            # Сохраняем обновлённую конфигурацию
            with sftp.file('/usr/local/etc/xray/config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            sftp.close()
            
            # Перезапускаем Xray
            server._exec_command('systemctl restart xray')
            
            server.disconnect()
            
            logger.info(f"✅ User added to Xray config")
            
            # Сохраняем в БД
            logger.info(f"💾 Saving to database...")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO v2ray_users (server_name, user_id, uuid, comment, sni)
                VALUES (?, ?, ?, ?, ?)
            ''', (server_name, user_id, user_uuid, comment, sni))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ User saved to database")
            
            # Генерируем VLESS ссылку с ключами
            vless_link = self._generate_vless_link(server_name, user_uuid, comment)
            
            if not vless_link:
                logger.error(f"❌ Failed to generate VLESS link")
                return None
            
            logger.info(f"✅ User added successfully")
            
            return {
                'uuid': user_uuid,
                'vless': vless_link,
                'sni': sni,
                'comment': comment
            }
            
        except Exception as e:
            logger.error(f"❌ add_user error: {e}", exc_info=True)
            return None
    
    def _generate_vless_link(self, server_name: str, uuid: str, comment: str = "") -> Optional[str]:
        """Генерация VLESS ссылки с REALITY ключами"""
        try:
            # Получаем информацию о сервере
            server = self.get_server_info(server_name)
            
            if not server:
                logger.error(f"❌ Server {server_name} not found")
                return None
            
            host = server['host']
            port = 443  # REALITY always uses port 443
            sni = server.get('sni', 'rutube.ru')
            public_key = server.get('public_key', '')
            short_id = server.get('short_id', '')
            
            # Если ключи не найдены в БД, пробуем получить с сервера
            if not public_key or not short_id:
                logger.warning(f"⚠️ Keys not found in DB for {server_name}, fetching from server...")
                ssh = self._connect_ssh(server)
                if ssh:
                    try:
                        # Пробуем получить из keys.json
                        logger.info("🔍 Trying to read /root/Xray-core/keys.json...")
                        stdin, stdout, stderr = ssh.exec_command('cat /root/Xray-core/keys.json')
                        keys_content = stdout.read().decode().strip()
                        
                        if keys_content:
                            keys = json.loads(keys_content)
                            public_key = keys.get('public_key', '')
                            short_id = keys.get('short_id', '')
                            logger.info(f"✅ Keys loaded from keys.json")
                            
                            # Сохраняем в БД для будущего использования
                            private_key = keys.get('private_key', '')
                            self.save_keys_to_db(server_name, public_key, private_key, short_id)
                        else:
                            # Пробуем парсить из config.json
                            logger.info("🔍 Trying to read from config.json...")
                            config_paths = [
                                '/usr/local/etc/xray/config.json',
                                '/root/Xray-core/config.json',
                                '/etc/xray/config.json'
                            ]
                            
                            for config_path in config_paths:
                                stdin, stdout, stderr = ssh.exec_command(f'cat {config_path}')
                                config_content = stdout.read().decode().strip()
                                
                                if config_content and 'realitySettings' in config_content:
                                    config = json.loads(config_content)
                                    reality_settings = config.get('inbounds', [{}])[0].get('streamSettings', {}).get('realitySettings', {})
                                    
                                    # Note: publicKey не хранится в config.json, только privateKey
                                    # Нужно сгенерировать публичный ключ из приватного
                                    private_key = reality_settings.get('privateKey', '')
                                    short_ids = reality_settings.get('shortIds', [])
                                    if short_ids:
                                        short_id = short_ids[0] if short_ids[0] else ''
                                    
                                    logger.info(f"✅ Found private key and short_id in config")
                                    break
                    
                    except Exception as e:
                        logger.error(f"❌ Error fetching keys from server: {e}")
                    finally:
                        ssh.close()
            
            if not public_key:
                logger.warning(f"⚠️ Public key not found for {server_name}!")
            
            if not short_id:
                logger.warning(f"⚠️ Short ID not found for {server_name}!")
            
            # Формируем параметры в правильном порядке для VLESS REALITY
            params = [
                'encryption=none',
                'security=reality',
                f'sni={sni}',
                'fp=chrome',
                'type=tcp',
                'flow=xtls-rprx-vision'
            ]
            
            # Add REALITY keys - КРИТИЧЕСКИ ВАЖНО для работы REALITY
            if public_key:
                params.append(f'pbk={public_key}')
            if short_id:
                params.append(f'sid={short_id}')
            
            params_str = '&'.join(params)
            comment_encoded = urllib.parse.quote(comment)
            
            vless = f"vless://{uuid}@{host}:{port}?{params_str}#{comment_encoded}"
            
            logger.info(f"✅ Generated VLESS link with REALITY keys")
            logger.info(f"  • pbk: {public_key[:20] if public_key else 'MISSING'}...")
            logger.info(f"  • sid: {short_id if short_id else 'MISSING'}")
            
            return vless
            
        except Exception as e:
            logger.error(f"❌ _generate_vless_link error: {e}", exc_info=True)
            return None
    
    def get_server_info(self, server_name: str) -> Optional[Dict]:
        """Получение полной информации о сервере"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, host, port, username, password, sni, public_key, private_key, short_id
                FROM v2ray_servers
                WHERE name = ? AND is_active = 1
            ''', (server_name,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'name': row[0],
                    'host': row[1],
                    'port': row[2],
                    'username': row[3],
                    'password': row[4],
                    'sni': row[5] or 'rutube.ru',
                    'public_key': row[6],
                    'private_key': row[7],
                    'short_id': row[8]
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о сервере: {e}")
            return None
    
    def get_users(self, server_name: str) -> List[Dict]:
        """Получает список пользователей С СЕРВЕРА из config.json"""
        try:
            logger.info(f"📋 Getting users from server {server_name}...")
            server = self.get_server_info(server_name)
            if not server:
                logger.error(f"❌ Server {server_name} not found")
                return []
            
            ssh = self._connect_ssh(server)
            if not ssh:
                logger.error(f"❌ Failed to connect to {server_name}")
                return []
            
            # Ищем config.json в разных местах
            config_paths = [
                '/usr/local/etc/xray/config.json',
                '/root/Xray-core/config.json',
                '/etc/xray/config.json'
            ]
            
            config_content = None
            config_path_used = None
            for path in config_paths:
                logger.info(f"🔍 Checking {path}...")
                stdin, stdout, stderr = ssh.exec_command(f'cat {path}')
                content = stdout.read().decode()
                if content and 'inbounds' in content:
                    config_content = content
                    config_path_used = path
                    logger.info(f"✅ Found config at {path}")
                    break
            
            if not config_content:
                logger.error(f"❌ Config not found on {server_name}")
                ssh.close()
                return []
            
            config = json.loads(config_content)
            
            # Парсим пользователей из первого inbound
            users = []
            if 'inbounds' in config and len(config['inbounds']) > 0:
                clients = config['inbounds'][0].get('settings', {}).get('clients', [])
                logger.info(f"📊 Found {len(clients)} users in config")
                for client in clients:
                    users.append({
                        'uuid': client.get('id'),
                        'email': client.get('email', 'unknown'),
                        'flow': client.get('flow', 'xtls-rprx-vision')
                    })
            
            ssh.close()
            logger.info(f"✅ Retrieved {len(users)} users from {server_name}")
            return users
            
        except Exception as e:
            logger.error(f"❌ Error getting users from {server_name}: {e}", exc_info=True)
            return []
    
    def get_server_users(self, server_name: str) -> list:
        """Получить список пользователей сервера (из БД для обратной совместимости)"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM v2ray_users
                WHERE server_name = ? AND is_active = 1
                ORDER BY created_at DESC
            ''', (server_name,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ get_server_users error: {e}")
            return []
    
    def delete_user(self, server_name: str, uuid: str) -> bool:
        """Удалить пользователя с сервера и из БД"""
        try:
            logger.info(f"🗑️ Deleting user {uuid} from {server_name}")
            
            # Удаляем из конфига Xray на сервере
            server_info = self.get_server_info(server_name)
            if not server_info:
                logger.error(f"❌ Server {server_name} not found")
                return False
            
            ssh = self._connect_ssh(server_info)
            if not ssh:
                logger.error(f"❌ Failed to connect to {server_name}")
                return False
            
            try:
                # Читаем конфигурацию
                config_paths = [
                    '/usr/local/etc/xray/config.json',
                    '/root/Xray-core/config.json',
                    '/etc/xray/config.json'
                ]
                
                config_content = None
                config_path_used = None
                for path in config_paths:
                    stdin, stdout, stderr = ssh.exec_command(f'cat {path}')
                    content = stdout.read().decode()
                    if content and 'inbounds' in content:
                        config_content = content
                        config_path_used = path
                        break
                
                if not config_content:
                    logger.error(f"❌ Config not found on {server_name}")
                    ssh.close()
                    return False
                
                config = json.loads(config_content)
                
                # Удаляем пользователя из конфига
                clients = config['inbounds'][0]['settings']['clients']
                original_count = len(clients)
                config['inbounds'][0]['settings']['clients'] = [
                    c for c in clients if c['id'] != uuid
                ]
                new_count = len(config['inbounds'][0]['settings']['clients'])
                
                if original_count == new_count:
                    logger.warning(f"⚠️ User {uuid} not found in config")
                else:
                    logger.info(f"✅ User removed from config ({original_count} -> {new_count})")
                
                # Сохраняем обновлённую конфигурацию
                sftp = ssh.open_sftp()
                with sftp.file(config_path_used, 'w') as f:
                    json.dump(config, f, indent=2)
                sftp.close()
                
                # Перезапускаем Xray
                ssh.exec_command('systemctl restart xray')
                logger.info(f"🔄 Xray restarted")
                
            finally:
                ssh.close()
            
            # Удаляем из БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM v2ray_users WHERE server_name = ? AND uuid = ?', (server_name, uuid))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ User {uuid} deleted from server and DB")
            return True
        except Exception as e:
            logger.error(f"❌ delete_user error: {e}", exc_info=True)
            return False
    
    def delete_server(self, server_name: str) -> bool:
        """Удаляет сервер из БД вместе со всеми пользователями"""
        try:
            logger.info(f"🗑️ Deleting server {server_name}...")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Удаляем пользователей сервера
            cursor.execute('DELETE FROM v2ray_users WHERE server_name = ?', (server_name,))
            deleted_users = cursor.rowcount
            logger.info(f"  • Deleted {deleted_users} users")
            
            # Удаляем сервер
            cursor.execute('DELETE FROM v2ray_servers WHERE name = ?', (server_name,))
            deleted_servers = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted_servers > 0:
                logger.info(f"✅ Сервер {server_name} и его пользователи удалены из БД")
                return True
            else:
                logger.warning(f"⚠️ Сервер {server_name} не найден")
                return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления сервера {server_name}: {e}", exc_info=True)
            return False
    
    def check_xray_status(self, server_name: str) -> bool:
        """Проверка запущен ли Xray"""
        try:
            server = self.get_server_info(server_name)
            if not server:
                return False
            
            ssh = self._connect_ssh(server)
            if not ssh:
                return False
            
            stdin, stdout, stderr = ssh.exec_command('systemctl is-active xray')
            status = stdout.read().decode().strip()
            ssh.close()
            
            return status == 'active'
        except Exception as e:
            logger.error(f"❌ check_xray_status error: {e}")
            return False
    
    def get_keys_from_server(self, server_name: str) -> Optional[dict]:
        """Получить ключи с сервера"""
        try:
            server = self.get_server_info(server_name)
            if not server:
                return None
            
            ssh = self._connect_ssh(server)
            if not ssh:
                return None
            
            stdin, stdout, stderr = ssh.exec_command('cat /root/Xray-core/keys.json')
            keys_json = stdout.read().decode().strip()
            ssh.close()
            
            if keys_json:
                return json.loads(keys_json)
            
            return None
        except Exception as e:
            logger.error(f"❌ get_keys_from_server error: {e}")
            return None
    
    def save_keys_to_db(self, server_name: str, public_key: str, private_key: str, short_id: str) -> bool:
        """Сохранить ключи в БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE v2ray_servers 
                SET public_key = ?, private_key = ?, short_id = ?
                WHERE name = ?
            ''', (public_key, private_key, short_id, server_name))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Keys saved to DB for {server_name}")
            return True
        except Exception as e:
            logger.error(f"❌ save_keys_to_db error: {e}")
            return False
    
    def _connect_ssh(self, server: dict) -> Optional[paramiko.SSHClient]:
        """Подключение по SSH к серверу"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=server['host'],
                port=server['port'],
                username=server['username'],
                password=server['password'],
                timeout=10
            )
            return ssh
        except Exception as e:
            logger.error(f"❌ SSH connection error: {e}")
            return None
    
    def set_temp_access(self, server_name: str, uuid: str, expires_at) -> bool:
        """Установить временный доступ для пользователя"""
        try:
            from datetime import datetime
            
            # Преобразуем expires_at в строку, если это datetime объект
            if isinstance(expires_at, datetime):
                expires_str = expires_at.isoformat()
            else:
                expires_str = expires_at
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Используем INSERT OR REPLACE для обновления существующей записи
            cursor.execute('''
                INSERT OR REPLACE INTO v2ray_temp_access (server_name, uuid, expires_at)
                VALUES (?, ?, ?)
            ''', (server_name, uuid, expires_str))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Temporary access set for {uuid} on {server_name} until {expires_str}")
            return True
        except Exception as e:
            logger.error(f"❌ set_temp_access error: {e}", exc_info=True)
            return False
    
    def get_temp_access(self, server_name: str, uuid: str) -> Optional[dict]:
        """Получить информацию о временном доступе пользователя"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM v2ray_temp_access
                WHERE server_name = ? AND uuid = ?
            ''', (server_name, uuid))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"❌ get_temp_access error: {e}")
            return None
    
    def remove_temp_access(self, server_name: str, uuid: str) -> bool:
        """Убрать временное ограничение доступа"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM v2ray_temp_access
                WHERE server_name = ? AND uuid = ?
            ''', (server_name, uuid))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Temporary access removed for {uuid} on {server_name}")
            return True
        except Exception as e:
            logger.error(f"❌ remove_temp_access error: {e}")
            return False
    
    def get_expired_users(self) -> List[Dict]:
        """Получить список пользователей с истёкшим доступом"""
        try:
            from datetime import datetime
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                SELECT * FROM v2ray_temp_access
                WHERE expires_at < ?
            ''', (now,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ get_expired_users error: {e}")
            return []
    
    def cleanup_expired_users(self) -> int:
        """Очистить пользователей с истёкшим доступом"""
        try:
            expired = self.get_expired_users()
            deleted_count = 0
            
            for user in expired:
                server_name = user['server_name']
                uuid = user['uuid']
                
                logger.info(f"🗑️ Cleaning up expired user {uuid} on {server_name}")
                
                # Удаляем пользователя
                if self.delete_user(server_name, uuid):
                    deleted_count += 1
                    logger.info(f"✅ Deleted expired user {uuid}")
                else:
                    logger.error(f"❌ Failed to delete expired user {uuid}")
            
            logger.info(f"✅ Cleanup completed: {deleted_count} expired users deleted")
            return deleted_count
        except Exception as e:
            logger.error(f"❌ cleanup_expired_users error: {e}", exc_info=True)
            return 0
