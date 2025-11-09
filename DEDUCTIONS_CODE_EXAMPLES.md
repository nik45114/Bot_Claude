# Примеры кода функциональности списания денег

## 1. ПРОЦЕСС СПИСАНИЯ РАСХОДОВ (EXPENSE)

### Начало диалога - cmd_expense() [строка 1743]

```python
async def cmd_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start expense tracking conversation"""
    user_id = update.effective_user.id
    
    # Проверка доступности модуля
    if not self.shift_manager:
        await update.message.reply_text("❌ Модуль управления сменами недоступен")
        return ConversationHandler.END
    
    # Получение активной смены
    active_shift = self.shift_manager.get_active_shift(user_id)
    
    if not active_shift:
        await update.message.reply_text(
            "❌ У вас нет открытой смены\n\n"
            "Сначала откройте смену через:\n"
            "🔓 Открыть смену"
        )
        return ConversationHandler.END
    
    # Сохранение данных в контекст для диалога
    context.user_data['expense_shift_id'] = active_shift['id']
    context.user_data['expense_club'] = active_shift['club']
    
    # Предложение выбрать источник кассы
    shift_label = "☀️ Утро" if active_shift['shift_type'] == 'morning' else "🌙 Вечер"
    
    msg = f"💸 Списание с кассы\n\n"
    msg += f"🏢 Клуб: {active_shift['club']}\n"
    msg += f"⏰ Смена: {shift_label}\n\n"
    msg += "Выберите откуда списать деньги:"
    
    keyboard = [
        [InlineKeyboardButton("💰 Основная касса", callback_data="expense_main")],
        [InlineKeyboardButton("📦 Коробка", callback_data="expense_box")],
        [InlineKeyboardButton("❌ Отменить", callback_data="expense_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup)
    return EXPENSE_SELECT_CASH_SOURCE
```

### Выбор источника кассы - expense_select_cash_source() [строка 1785]

```python
async def expense_select_cash_source(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cash source selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "expense_cancel":
        await query.edit_message_text("❌ Списание отменено")
        context.user_data.pop('expense_shift_id', None)
        context.user_data.pop('expense_club', None)
        return ConversationHandler.END
    
    # Определение источника кассы
    if query.data == "expense_main":
        cash_source = "main"
        source_label = "💰 Основная касса"
    elif query.data == "expense_box":
        cash_source = "box"
        source_label = "📦 Коробка"
    else:
        await query.edit_message_text("❌ Неверный выбор")
        return ConversationHandler.END
    
    # Сохранение выбора
    context.user_data['expense_cash_source'] = cash_source
    context.user_data['expense_source_label'] = source_label
    
    # Запрос суммы
    msg = f"💸 Списание с кассы\n\n"
    msg += f"Касса: {source_label}\n\n"
    msg += "Введите сумму списания:\n\n"
    msg += "Пример: 1500"
    
    await query.edit_message_text(msg)
    return EXPENSE_ENTER_AMOUNT
```

### Получение и подтверждение - expense_confirm() [строка 1883]

```python
async def expense_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and save expense"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "expense_cancel":
        await query.edit_message_text("❌ Списание отменено")
        # Очистка данных
        for key in list(context.user_data.keys()):
            if key.startswith('expense_'):
                context.user_data.pop(key)
        return ConversationHandler.END
    
    # Получение данных
    shift_id = context.user_data.get('expense_shift_id')
    cash_source = context.user_data.get('expense_cash_source')
    amount = context.user_data.get('expense_amount')
    reason = context.user_data.get('expense_reason')
    source_label = context.user_data.get('expense_source_label')
    
    # СОХРАНЕНИЕ В БД - ГЛАВНАЯ ОПЕРАЦИЯ
    success = self.shift_manager.add_expense(shift_id, cash_source, amount, reason)
    
    if success:
        await query.edit_message_text(
            f"✅ Списание сохранено!\n\n"
            f"Касса: {source_label}\n"
            f"💰 Сумма: {amount:,.0f} ₽\n"
            f"📝 {reason}"
        )
        
        # УВЕДОМЛЕНИЕ ВЛАДЕЛЬЦУ
        if self.owner_ids:
            for owner_id in self.owner_ids:
                try:
                    club = context.user_data.get('expense_club')
                    user = query.from_user
                    notify_msg = f"💸 Списание в смене #{shift_id}\n\n"
                    notify_msg += f"🏢 {club} | {source_label}\n"
                    notify_msg += f"💰 {amount:,.0f} ₽\n"
                    notify_msg += f"📝 {reason}\n\n"
                    notify_msg += f"👤 {user.full_name or 'Неизвестно'}"
                    if user.username:
                        notify_msg += f" (@{user.username})"
                    
                    await context.bot.send_message(chat_id=owner_id, text=notify_msg)
                except:
                    pass
    else:
        await query.edit_message_text("❌ Не удалось сохранить списание. Попробуйте позже.")
    
    # Очистка данных
    for key in list(context.user_data.keys()):
        if key.startswith('expense_'):
            context.user_data.pop(key)
    
    return ConversationHandler.END
```

---

## 2. ПРОЦЕСС СНЯТИЯ НАЛИЧНЫХ (WITHDRAWAL)

### Начало диалога - start_cash_withdrawal() [строка 2428]

```python
async def start_cash_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start cash withdrawal process during shift"""
    query = update.callback_query
    is_callback = query is not None
    
    user_id = update.effective_user.id
    
    # Получение активной смены
    active_shift = None
    if self.shift_manager:
        active_shift = self.shift_manager.get_active_shift(user_id)
    
    if not active_shift:
        error_msg = (
            "❌ У вас нет активной смены\n\n"
            "Сначала откройте смену, чтобы взять зарплату с кассы"
        )
        if is_callback:
            await query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)
        return ConversationHandler.END
    
    # Получение имени администратора
    admin_name = update.effective_user.full_name or "Админ"
    
    # Предложение ввести сумму
    msg = f"💰 Взять зарплату с кассы\n\n"
    msg += f"👤 {admin_name}\n"
    msg += f"🏢 Клуб: {active_shift['club']}\n"
    msg += f"🆔 Смена: #{active_shift['id']}\n\n"
    msg += "Введите сумму для снятия:\n\n"
    msg += "Пример: 5000"
    
    if is_callback:
        await query.answer()
        await query.message.reply_text(msg)
    else:
        await update.message.reply_text(msg)
    
    return WITHDRAWAL_ENTER_AMOUNT
```

### Подтверждение и сохранение - handle_withdrawal_confirmation() [строка 2518]

```python
async def handle_withdrawal_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal confirmation"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "withdrawal_cancel":
        await query.edit_message_text("❌ Снятие отменено")
        return
    
    if query.data == "withdrawal_confirm":
        user_id = query.from_user.id
        amount = context.user_data.get('withdrawal_amount', 0)
        
        if amount <= 0:
            await query.edit_message_text("❌ Неверная сумма")
            return
        
        # Получение активной смены
        active_shift = self.shift_manager.get_active_shift(user_id) if self.shift_manager else None
        if not active_shift:
            await query.edit_message_text("❌ Активная смена не найдена")
            return
        
        # СОХРАНЕНИЕ В БД - ГЛАВНАЯ ОПЕРАЦИЯ
        try:
            from modules.salary_calculator import SalaryCalculator
            salary_calc = SalaryCalculator(
                self.shift_manager.db_path if hasattr(self.shift_manager, 'db_path') else 'club_assistant.db'
            )
            
            withdrawal_id = salary_calc.record_cash_withdrawal(
                shift_id=active_shift['id'],
                admin_id=user_id,
                amount=amount,
                reason='salary'
            )
            
            if withdrawal_id:
                admin_name = query.from_user.full_name or "Админ"
                
                await query.edit_message_text(
                    f"✅ Зарплата снята с кассы\n\n"
                    f"👤 {admin_name}\n"
                    f"🏢 Клуб: {active_shift['club']}\n"
                    f"🆔 Смена: #{active_shift['id']}\n\n"
                    f"💵 Сумма: {amount:,.0f} ₽\n"
                    f"📝 Запись: #{withdrawal_id}\n\n"
                    f"Сумма будет учтена при расчете зарплаты"
                )
                
                # УВЕДОМЛЕНИЕ ВЛАДЕЛЬЦУ
                if self.owner_ids:
                    for owner_id in self.owner_ids:
                        try:
                            notify_msg = f"💰 Снятие зарплаты с кассы\n\n"
                            notify_msg += f"👤 {admin_name} (ID: {user_id})\n"
                            notify_msg += f"🏢 Клуб: {active_shift['club']}\n"
                            notify_msg += f"🆔 Смена: #{active_shift['id']}\n"
                            notify_msg += f"💵 Сумма: {amount:,.0f} ₽\n"
                            notify_msg += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                            
                            await context.bot.send_message(chat_id=owner_id, text=notify_msg)
                        except:
                            pass
            else:
                await query.edit_message_text("❌ Не удалось записать снятие")
                
        except Exception as e:
            logger.error(f"Failed to record cash withdrawal: {e}")
            await query.edit_message_text("❌ Ошибка при записи снятия")
```

---

## 3. ФУНКЦИИ СОХРАНЕНИЯ В БД

### ShiftManager.add_expense() [строка 186 - shift_manager.py]

```python
def add_expense(self, shift_id: int, cash_source: str, amount: float, reason: str) -> bool:
    """
    Add expense to active shift
    
    Args:
        shift_id: Shift ID
        cash_source: 'main' или 'box'
        amount: Amount to deduct
        reason: Reason for expense
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO shift_expenses (shift_id, cash_source, amount, reason)
            VALUES (?, ?, ?, ?)
        ''', (shift_id, cash_source, amount, reason))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Added expense to shift {shift_id}: {amount} from {cash_source} - {reason}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to add expense: {e}")
        return False
```

### SalaryCalculator.record_cash_withdrawal() [строка 384 - salary_calculator.py]

```python
def record_cash_withdrawal(self, shift_id: int, admin_id: int, amount: float, reason: str = 'salary') -> int:
    """
    Record cash withdrawal during shift
    
    Args:
        shift_id: Shift ID
        admin_id: Admin user ID
        amount: Amount withdrawn
        reason: Reason for withdrawal
    
    Returns:
        Withdrawal record ID (0 if failed)
    """
    try:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO shift_cash_withdrawals (shift_id, admin_id, amount, reason)
            VALUES (?, ?, ?, ?)
        ''', (shift_id, admin_id, amount, reason))
        
        withdrawal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Recorded cash withdrawal {withdrawal_id}: {amount} for admin {admin_id}")
        return withdrawal_id
        
    except Exception as e:
        logger.error(f"Failed to record cash withdrawal: {e}")
        return 0
```

---

## 4. РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ В BOT [строки 4770-4813 - bot.py]

```python
# Обработчик списания расходов
expense_handler = ConversationHandler(
    entry_points=[
        CommandHandler("expense", shift_wizard.cmd_expense),
        MessageHandler(filters.TEXT & filters.Regex("^💸 Списать с кассы$"), shift_wizard.cmd_expense),
        CallbackQueryHandler(shift_wizard.start_expense, pattern="^shift_expense$")
    ],
    states={
        EXPENSE_SELECT_CASH_SOURCE: [
            CallbackQueryHandler(shift_wizard.expense_select_cash_source, pattern="^expense_")
        ],
        EXPENSE_ENTER_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.expense_receive_amount)
        ],
        EXPENSE_ENTER_REASON: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.expense_receive_reason)
        ],
        EXPENSE_CONFIRM: [
            CallbackQueryHandler(shift_wizard.expense_confirm, pattern="^expense_")
        ]
    },
    fallbacks=[
        CommandHandler("cancel", shift_wizard.cancel_command)
    ]
)
application.add_handler(expense_handler)

# Обработчик снятия наличных
withdrawal_handler = ConversationHandler(
    entry_points=[
        CommandHandler("withdrawal", shift_wizard.start_cash_withdrawal),
        MessageHandler(filters.TEXT & filters.Regex("^💰 Взять зарплату$"), shift_wizard.start_cash_withdrawal),
        CallbackQueryHandler(shift_wizard.start_cash_withdrawal, pattern="^shift_salary$")
    ],
    states={
        WITHDRAWAL_ENTER_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, shift_wizard.receive_withdrawal_amount)
        ],
        WITHDRAWAL_CONFIRM: [
            CallbackQueryHandler(shift_wizard.handle_withdrawal_confirmation, pattern="^withdrawal_")
        ]
    },
    fallbacks=[
        CommandHandler("cancel", shift_wizard.cancel_command)
    ]
)
application.add_handler(withdrawal_handler)
```
