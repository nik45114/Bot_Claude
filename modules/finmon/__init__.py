#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinMon Module - Financial Monitoring for Computer Clubs
Telegram bot module for shift reporting with Google Sheets sync
"""

import logging
import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from .db import FinMonDB
from .sheets import GoogleSheetsSync
from .wizard import (
    FinMonWizard,
    SELECT_CLUB, SELECT_TIME, ENTER_FACT_CASH, ENTER_FACT_CARD, ENTER_QR, ENTER_CARD2,
    ENTER_SAFE_CASH, ENTER_BOX_CASH, ENTER_GOODS_CASH,
    ENTER_COMPENSATIONS, ENTER_SALARY, ENTER_OTHER_EXPENSES,
    ENTER_JOYSTICKS_TOTAL, ENTER_JOYSTICKS_REPAIR, ENTER_JOYSTICKS_NEED, ENTER_GAMES,
    SELECT_TOILET_PAPER, SELECT_PAPER_TOWELS,
    ENTER_NOTES, CONFIRM_SHIFT
)

logger = logging.getLogger(__name__)


def register_finmon(application: Application, config: dict = None):
    """
    Регистрация модуля FinMon в приложении
    
    Args:
        application: Telegram Application instance
        config: Configuration dictionary with:
            - db_path: Path to SQLite database (default: 'knowledge.db')
            - google_sa_json: Path to Google Service Account JSON (optional)
            - sheet_name: Google Sheets name (default: 'ClubFinance')
            - owner_ids: List of owner telegram IDs (default: [])
    """
    if config is None:
        config = {}
    
    # Конфигурация
    db_path = config.get('db_path', os.getenv('FINMON_DB_PATH', 'knowledge.db'))
    google_sa_json = config.get('google_sa_json', os.getenv('GOOGLE_SA_JSON'))
    sheet_name = config.get('sheet_name', os.getenv('FINMON_SHEET_NAME', 'ClubFinance'))
    owner_ids_str = config.get('owner_ids', os.getenv('OWNER_TG_IDS', ''))
    
    # Парсинг owner_ids
    owner_ids = []
    if owner_ids_str:
        try:
            owner_ids = [int(id.strip()) for id in owner_ids_str.split(',') if id.strip()]
        except ValueError:
            logger.error("❌ Invalid OWNER_TG_IDS format")
    
    logger.info(f"📊 Initializing FinMon module...")
    logger.info(f"   DB: {db_path}")
    logger.info(f"   Sheet: {sheet_name}")
    logger.info(f"   Owners: {len(owner_ids)}")
    
    # Инициализация компонентов
    db = FinMonDB(db_path)
    
    # Google Sheets (опционально)
    sheets = None
    if google_sa_json and os.path.exists(google_sa_json):
        try:
            sheets = GoogleSheetsSync(google_sa_json, sheet_name)
            logger.info(f"✅ Google Sheets sync enabled")
        except Exception as e:
            logger.warning(f"⚠️ Google Sheets sync disabled: {e}")
            sheets = GoogleSheetsSync(google_sa_json, sheet_name)  # Will be in disabled mode
    else:
        logger.warning(f"⚠️ Google Sheets sync disabled - no credentials")
        # Create dummy sheets object
        sheets = GoogleSheetsSync.__new__(GoogleSheetsSync)
        sheets.credentials_path = None
        sheets.sheet_name = sheet_name
        sheets.client = None
        sheets.spreadsheet = None
    
    # Wizard
    wizard = FinMonWizard(db, sheets, owner_ids)
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("balances", wizard.cmd_balances))
    application.add_handler(CommandHandler("shifts", wizard.cmd_shifts))
    
    # Chat-club mapping commands (owner only)
    application.add_handler(CommandHandler("finmon_map", wizard.cmd_finmon_map))
    application.add_handler(CommandHandler("finmon_bind", wizard.cmd_finmon_bind))
    application.add_handler(CommandHandler("finmon_bind_here", wizard.cmd_finmon_bind_here))
    application.add_handler(CommandHandler("finmon_unbind", wizard.cmd_finmon_unbind))
    
    # ConversationHandler для сдачи смены
    shift_handler = ConversationHandler(
        entry_points=[
            CommandHandler("shift", wizard.cmd_shift)
        ],
        states={
            SELECT_CLUB: [
                CallbackQueryHandler(wizard.select_club, pattern="^finmon_club_"),
            ],
            SELECT_TIME: [
                CallbackQueryHandler(wizard.select_time, pattern="^finmon_time_"),
                CallbackQueryHandler(wizard.close_auto, pattern="^finmon_close_auto$"),
                CallbackQueryHandler(wizard.close_manual_morning, pattern="^finmon_close_manual_morning$"),
                CallbackQueryHandler(wizard.close_manual_evening, pattern="^finmon_close_manual_evening$"),
                CallbackQueryHandler(wizard.close_early, pattern="^finmon_close_early$"),
                CallbackQueryHandler(wizard.choose_manual, pattern="^finmon_choose_manual$"),
                CallbackQueryHandler(wizard.early_shift_selected, pattern="^finmon_early_"),
                CallbackQueryHandler(wizard.back_to_shift_select, pattern="^finmon_back_to_shift_select$"),
            ],
            ENTER_FACT_CASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_fact_cash)
            ],
            ENTER_FACT_CARD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_fact_card)
            ],
            ENTER_QR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_qr)
            ],
            ENTER_CARD2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_card2)
            ],
            ENTER_SAFE_CASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_safe_cash)
            ],
            ENTER_BOX_CASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_box_cash)
            ],
            ENTER_GOODS_CASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_goods_cash)
            ],
            ENTER_COMPENSATIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_compensations)
            ],
            ENTER_SALARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_salary)
            ],
            ENTER_OTHER_EXPENSES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_other_expenses)
            ],
            ENTER_JOYSTICKS_TOTAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_joysticks_total)
            ],
            ENTER_JOYSTICKS_REPAIR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_joysticks_repair)
            ],
            ENTER_JOYSTICKS_NEED: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_joysticks_need)
            ],
            ENTER_GAMES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_games)
            ],
            SELECT_TOILET_PAPER: [
                CallbackQueryHandler(wizard.select_toilet_paper, pattern="^finmon_toilet_"),
            ],
            SELECT_PAPER_TOWELS: [
                CallbackQueryHandler(wizard.select_paper_towels, pattern="^finmon_towels_"),
            ],
            ENTER_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wizard.enter_notes)
            ],
            CONFIRM_SHIFT: [
                CallbackQueryHandler(wizard.confirm_shift, pattern="^finmon_confirm$"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(wizard.cancel, pattern="^finmon_cancel$"),
            CommandHandler("cancel", wizard.cancel)
        ]
    )
    
    application.add_handler(shift_handler)
    
    logger.info("✅ FinMon module registered")


__all__ = ['register_finmon', 'FinMonDB', 'GoogleSheetsSync', 'FinMonWizard']
