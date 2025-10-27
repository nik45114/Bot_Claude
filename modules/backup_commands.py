#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backup and Migration Commands
Owner-only commands for database backups and migration file distribution
"""

import os
import logging
import tarfile
import shutil
from datetime import datetime
from pathlib import Path
from telegram import Update, Document
from telegram.ext import ContextTypes
from .runtime_migrator import RuntimeMigrator

logger = logging.getLogger(__name__)


class BackupCommands:
    """Commands for backup and migration management"""
    
    def __init__(self, db_path: str = 'knowledge.db', backup_dir: str = './backups', owner_ids: list = None):
        """
        Initialize backup commands
        
        Args:
            db_path: Path to SQLite database
            backup_dir: Directory for backup files
            owner_ids: List of owner telegram IDs
        """
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.owner_ids = owner_ids or []
        self.migrations_dir = './migrations'
        
        # Ensure backup directory exists
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize runtime migrator
        self.migrator = RuntimeMigrator(db_path, self.migrations_dir)
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        if not self.owner_ids:
            logger.warning("⚠️ OWNER_TG_IDS not configured, denying access")
            return False
        return user_id in self.owner_ids
    
    async def cmd_apply_migrations(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Apply pending migrations and runtime fixes
        Usage: /apply_migrations
        """
        user_id = update.effective_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ Эта команда доступна только владельцу бота")
            return
        
        try:
            await update.message.reply_text("🔄 Применяю миграции...")
            
            # Apply migrations
            success, messages = self.migrator.apply_all_migrations()
            
            # Format response
            if not messages:
                response = "ℹ️ Нет доступных миграций"
            else:
                response = "📋 Результаты миграции:\n\n" + "\n".join(messages)
            
            if success:
                response += "\n\n✅ Миграции применены успешно"
            else:
                response += "\n\n⚠️ Некоторые миграции завершились с ошибками"
            
            await update.message.reply_text(response)
            logger.info(f"✅ Migrations applied by user {user_id}")
            
        except Exception as e:
            logger.error(f"Error applying migrations: {e}")
            await update.message.reply_text(f"❌ Ошибка применения миграций: {e}")
    
    async def cmd_migration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Send migration SQL file(s) to owner
        Usage: /migration
        """
        user_id = update.effective_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ Эта команда доступна только владельцу бота")
            return
        
        try:
            # Create tar archive with all migration files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f'migrations_{timestamp}.tar.gz'
            archive_path = os.path.join(self.backup_dir, archive_name)
            
            migrations_path = Path(self.migrations_dir)
            if not migrations_path.exists() or not any(migrations_path.glob('*.sql')):
                await update.message.reply_text("❌ Файлы миграций не найдены")
                return
            
            # Create tar archive
            with tarfile.open(archive_path, 'w:gz') as tar:
                for sql_file in migrations_path.glob('*.sql'):
                    tar.add(sql_file, arcname=sql_file.name)
            
            # Send archive
            await update.message.reply_text("📦 Отправляю архив с файлами миграций...")
            
            with open(archive_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=archive_name,
                    caption=f"📋 Миграции БД\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
            
            # Clean up archive
            os.remove(archive_path)
            
            logger.info(f"✅ Migration files sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending migration files: {e}")
            await update.message.reply_text(f"❌ Ошибка отправки файлов миграций: {e}")
    
    async def cmd_backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Create and send backup archive
        Usage: /backup
        """
        user_id = update.effective_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ Эта команда доступна только владельцу бота")
            return
        
        try:
            # Create timestamped backup archive
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f'backup_{timestamp}.tar.gz'
            archive_path = os.path.join(self.backup_dir, archive_name)
            
            await update.message.reply_text("🔄 Создаю резервную копию...")
            
            # Create tar archive
            with tarfile.open(archive_path, 'w:gz') as tar:
                # Add SQLite database if exists
                if os.path.exists(self.db_path):
                    tar.add(self.db_path, arcname=os.path.basename(self.db_path))
                
                # Add JSON/CSV files from modules/finmon_simple if they exist
                finmon_data_dir = './finmon_data'
                if os.path.exists(finmon_data_dir):
                    for root, dirs, files in os.walk(finmon_data_dir):
                        for file in files:
                            if file.endswith(('.json', '.csv')):
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, '.')
                                tar.add(file_path, arcname=arcname)
                
                # Add config.json if exists (without sensitive data we'll warn about this)
                if os.path.exists('config.json'):
                    # Note: In production, you might want to sanitize sensitive data
                    tar.add('config.json', arcname='config.json')
            
            # Get archive size
            archive_size = os.path.getsize(archive_path)
            size_mb = archive_size / (1024 * 1024)
            
            # Send archive
            await update.message.reply_text(f"📦 Отправляю архив ({size_mb:.2f} МБ)...")
            
            with open(archive_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=archive_name,
                    caption=f"💾 Резервная копия\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n📊 Размер: {size_mb:.2f} МБ"
                )
            
            # Clean up archive
            os.remove(archive_path)
            
            logger.info(f"✅ Backup sent to user {user_id}, size: {size_mb:.2f} MB")
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            await update.message.reply_text(f"❌ Ошибка создания резервной копии: {e}")
    
    async def send_scheduled_migration(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Scheduled job to send migration files to all owners
        Called by JobQueue every N days
        """
        try:
            # Create tar archive with all migration files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f'migrations_scheduled_{timestamp}.tar.gz'
            archive_path = os.path.join(self.backup_dir, archive_name)
            
            migrations_path = Path(self.migrations_dir)
            if not migrations_path.exists() or not any(migrations_path.glob('*.sql')):
                logger.warning("No migration files found for scheduled send")
                return
            
            # Create tar archive
            with tarfile.open(archive_path, 'w:gz') as tar:
                for sql_file in migrations_path.glob('*.sql'):
                    tar.add(sql_file, arcname=sql_file.name)
            
            # Send to all owners
            for owner_id in self.owner_ids:
                try:
                    with open(archive_path, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=owner_id,
                            document=f,
                            filename=archive_name,
                            caption=f"📋 Автоматическая отправка миграций\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\nПлановая отправка файлов миграций БД."
                        )
                    
                    logger.info(f"✅ Scheduled migration files sent to owner {owner_id}")
                    
                except Exception as e:
                    logger.error(f"Error sending scheduled migration to owner {owner_id}: {e}")
            
            # Clean up archive
            if os.path.exists(archive_path):
                os.remove(archive_path)
            
        except Exception as e:
            logger.error(f"Error in scheduled migration send: {e}")
    
    async def send_weekly_backup(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Scheduled job to send weekly backup to all owners
        Called by JobQueue every 7 days
        """
        try:
            # Create timestamped backup archive
            timestamp = datetime.now().strftime('%Y%m%d')
            archive_name = f'backup_weekly_{timestamp}.tar.gz'
            archive_path = os.path.join(self.backup_dir, archive_name)
            
            logger.info(f"📦 Creating weekly backup: {archive_name}")
            
            # Create tar archive with important files
            with tarfile.open(archive_path, 'w:gz') as tar:
                # Add SQLite database
                if os.path.exists(self.db_path):
                    tar.add(self.db_path, arcname=os.path.basename(self.db_path))
                    logger.info(f"  Added: {self.db_path}")
                
                # Add FinMon data files
                finmon_files = ['finmon_balances.json', 'finmon_log.csv']
                for file in finmon_files:
                    if os.path.exists(file):
                        tar.add(file, arcname=file)
                        logger.info(f"  Added: {file}")
                
                # Add vector store if exists
                vector_files = ['vector_index.faiss', 'vector_metadata.pkl']
                for file in vector_files:
                    if os.path.exists(file):
                        tar.add(file, arcname=file)
                        logger.info(f"  Added: {file}")
            
            # Get archive size
            archive_size = os.path.getsize(archive_path)
            size_mb = archive_size / (1024 * 1024)
            
            # Send to all owners
            for owner_id in self.owner_ids:
                try:
                    with open(archive_path, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=owner_id,
                            document=f,
                            filename=archive_name,
                            caption=(
                                f"💾 Еженедельный автобэкап\n"
                                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                                f"📊 Размер: {size_mb:.2f} МБ\n\n"
                                f"Включено:\n"
                                f"• База данных (knowledge.db)\n"
                                f"• Финансовые данные (finmon_*.json/csv)\n"
                                f"• Векторное хранилище"
                            )
                        )
                    
                    logger.info(f"✅ Weekly backup sent to owner {owner_id}, size: {size_mb:.2f} MB")
                    
                except Exception as e:
                    logger.error(f"❌ Error sending weekly backup to owner {owner_id}: {e}")
            
            # Clean up archive
            if os.path.exists(archive_path):
                os.remove(archive_path)
            
        except Exception as e:
            logger.error(f"❌ Error in weekly backup: {e}")


def register_backup_commands(application, config: dict = None):
    """
    Register backup commands in the application
    
    Args:
        application: Telegram Application instance
        config: Configuration dictionary
    """
    from telegram.ext import CommandHandler
    
    if config is None:
        config = {}
    
    # Get configuration
    db_path = config.get('db_path', os.getenv('DB_PATH', 'knowledge.db'))
    backup_dir = config.get('backup_dir', os.getenv('BACKUP_DIR', './backups'))
    owner_ids_str = config.get('owner_ids', os.getenv('OWNER_TG_IDS', ''))
    backup_interval_days = int(config.get('backup_interval_days', os.getenv('BACKUP_INTERVAL_DAYS', '14')))
    
    # Parse owner IDs
    owner_ids = []
    if owner_ids_str:
        try:
            owner_ids = [int(id.strip()) for id in owner_ids_str.split(',') if id.strip()]
        except ValueError:
            logger.error("❌ Invalid OWNER_TG_IDS format")
    
    if not owner_ids:
        logger.warning("⚠️ No owner IDs configured for backup commands")
        return
    
    logger.info(f"📦 Initializing Backup commands...")
    logger.info(f"   DB: {db_path}")
    logger.info(f"   Backup dir: {backup_dir}")
    logger.info(f"   Owners: {len(owner_ids)}")
    logger.info(f"   Interval: {backup_interval_days} days")
    
    # Initialize backup commands
    backup_commands = BackupCommands(db_path, backup_dir, owner_ids)
    
    # Register commands
    application.add_handler(CommandHandler("apply_migrations", backup_commands.cmd_apply_migrations))
    application.add_handler(CommandHandler("migration", backup_commands.cmd_migration))
    application.add_handler(CommandHandler("backup", backup_commands.cmd_backup))
    
    # Schedule periodic migration file sending
    if application.job_queue:
        # Send migrations every N days
        application.job_queue.run_repeating(
            backup_commands.send_scheduled_migration,
            interval=backup_interval_days * 24 * 60 * 60,  # Convert days to seconds
            first=10,  # First run after 10 seconds
            name='scheduled_migration_send'
        )
        logger.info(f"✅ Scheduled migration sending enabled (every {backup_interval_days} days)")
        
        # Send weekly backup every 7 days
        application.job_queue.run_repeating(
            backup_commands.send_weekly_backup,
            interval=7 * 24 * 60 * 60,  # 7 days in seconds
            first=3600,  # First run after 1 hour (3600 seconds)
            name='weekly_backup'
        )
        logger.info(f"✅ Weekly backup enabled (every 7 days, starts in 1 hour)")
    else:
        logger.warning("⚠️ JobQueue not available, scheduled backups disabled")
    
    logger.info("✅ Backup commands registered")


__all__ = ['BackupCommands', 'register_backup_commands']
