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
                'short_id': keys['short_id']
            }
            
            return config
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания конфигурации: {e}")
            return None
    
    def deploy_config(self, config: Dict) -> bool:
        """Развёртывание конфигурации на сервере"""
        try:
            # Убираем служебные ключи перед сохранением
            config_to_save = config.copy()
            if '_client_keys' in config_to_save:
                del config_to_save['_client_keys']
            
            config_json = json.dumps(config_to_save, indent=2)
            
            # Загружаем конфигурацию на сервер
            sftp = self.ssh_client.open_sftp()
            with sftp.file('/usr/local/etc/xray/config.json', 'w') as f:
                f.write(config_json)
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
            # Генерируем UUID для пользователя
            user_uuid = str(uuid.uuid4())
            
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
                short_id TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
    
    def save_server_keys(self, server_name: str, public_key: str, short_id: str) -> bool:
        """Сохранение ключей сервера"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE v2ray_servers
                SET public_key = ?, short_id = ?
                WHERE name = ?
            ''', (public_key, short_id, server_name))
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
        """Сохранение пользователя"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем ID сервера
            cursor.execute('SELECT id FROM v2ray_servers WHERE name = ?', (server_name,))
            server_id = cursor.fetchone()[0]
            
            # Получаем ключи сервера для дополнения ссылки
            keys = self.get_server_keys(server_name)
            
            # Дополняем ссылку pbk и sid
            if keys.get('public_key') and keys.get('short_id'):
                vless_link += f"&pbk={keys['public_key']}&sid={keys['short_id']}"
            
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
            
            # Генерируем UUID
            user_uuid = str(uuid.uuid4())
            logger.info(f"🔑 Generated UUID: {user_uuid}")
            
            # Добавляем пользователя в конфиг Xray через существующий метод
            logger.info(f"📝 Adding user to Xray config...")
            server = V2RayServer(
                server_info['host'],
                server_info['username'],
                server_info['password'],
                server_info['port']
            )
            
            if not server.connect():
                logger.error(f"❌ Failed to connect to server")
                return None
            
            # Используем существующий метод add_user_reality
            sni = server_info.get('sni', 'rutube.ru')
            vless_link_partial = server.add_user_reality(user_id, comment or user_id, sni)
            
            server.disconnect()
            
            if not vless_link_partial:
                logger.error(f"❌ Failed to add user to Xray")
                return None
            
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
            
            # Генерируем VLESS ссылку
            # REALITY protocol always uses port 443 to mimic HTTPS traffic
            # This is hardcoded throughout the system (see create_reality_config)
            vless_link = self._generate_vless_link(
                server_info['host'],
                443,
                user_uuid,
                sni,
                comment
            )
            
            # Дополняем ключами
            keys = self.get_server_keys(server_name)
            if keys.get('public_key') and keys.get('short_id'):
                vless_link += f"&pbk={keys['public_key']}&sid={keys['short_id']}"
            
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
    
    def _generate_vless_link(self, host: str, port: int, uuid: str, sni: str, comment: str) -> str:
        """Генерация VLESS ссылки"""
        import urllib.parse
        
        params = {
            'security': 'reality',
            'sni': sni,
            'fp': 'chrome',
            'type': 'tcp',
            'flow': 'xtls-rprx-vision'
        }
        
        params_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        comment_encoded = urllib.parse.quote(comment)
        
        vless = f"vless://{uuid}@{host}:{port}?{params_str}#{comment_encoded}"
        
        return vless
    
    def get_server_info(self, server_name: str) -> Optional[Dict]:
        """Получение полной информации о сервере"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, host, port, username, password, sni
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
                    'sni': row[5] or 'rutube.ru'
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о сервере: {e}")
            return None
    
    def get_server_users(self, server_name: str) -> list:
        """Получить список пользователей сервера"""
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
        """Удалить пользователя"""
        try:
            logger.info(f"🗑️ Deleting user {uuid} from {server_name}")
            
            # Удаляем из БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM v2ray_users WHERE server_name = ? AND uuid = ?', (server_name, uuid))
            conn.commit()
            conn.close()
            
            # TODO: Удалить из конфига Xray через SSH
            
            logger.info(f"✅ User deleted")
            return True
        except Exception as e:
            logger.error(f"❌ delete_user error: {e}")
            return False
