"""
Патч с обработчиками кнопок для остальных касс
Добавить эти методы в ShiftWizard класс
"""

# === Card handlers ===
async def handle_card_no_change(self, update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['shift_data']['fact_card'] = 0.0

    msg = "✅ Карта факт: 0 ₽ (без изменений)\n\n📱 Введите QR:\n\nПример: 500 (или 0 если нет)"
    keyboard = [
        [InlineKeyboardButton("Без изменений (0)", callback_data="qr_no_change")],
        [InlineKeyboardButton("❌ Касса не работала", callback_data="qr_disabled")],
        [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return ENTER_QR

async def handle_card_disabled(self, update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['shift_data']['fact_card'] = 0.0
    context.user_data['shift_data']['card_disabled'] = True

    msg = "❌ Касса карт не работала\n\n📱 Введите QR:\n\nПример: 500 (или 0 если нет)"
    keyboard = [
        [InlineKeyboardButton("Без изменений (0)", callback_data="qr_no_change")],
        [InlineKeyboardButton("❌ Касса не работала", callback_data="qr_disabled")],
        [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return ENTER_QR

# === QR handlers ===
async def handle_qr_no_change(self, update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['shift_data']['qr'] = 0.0

    msg = "✅ QR: 0 ₽ (без изменений)\n\n💳 Введите карту 2:\n\nПример: 1000 (или 0 если нет)"
    keyboard = [
        [InlineKeyboardButton("Без изменений (0)", callback_data="card2_no_change")],
        [InlineKeyboardButton("❌ Касса не работала", callback_data="card2_disabled")],
        [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return ENTER_CARD2

async def handle_qr_disabled(self, update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['shift_data']['qr'] = 0.0
    context.user_data['shift_data']['qr_disabled'] = True

    msg = "❌ QR не работал\n\n💳 Введите карту 2:\n\nПример: 1000 (или 0 если нет)"
    keyboard = [
        [InlineKeyboardButton("Без изменений (0)", callback_data="card2_no_change")],
        [InlineKeyboardButton("❌ Касса не работала", callback_data="card2_disabled")],
        [InlineKeyboardButton("🚫 Отмена", callback_data="shift_cancel")]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return ENTER_CARD2

# === Card2 handlers ===
async def handle_card2_no_change(self, update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['shift_data']['card2'] = 0.0
    await query.message.reply_text("🏦 Введите остаток в сейфе:\n\nПример: 5000")
    return ENTER_SAFE

async def handle_card2_disabled(self, update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['shift_data']['card2'] = 0.0
    context.user_data['shift_data']['card2_disabled'] = True
    await query.message.reply_text("❌ Карта 2 не работала\n\n🏦 Введите остаток в сейфе:\n\nПример: 5000")
    return ENTER_SAFE
