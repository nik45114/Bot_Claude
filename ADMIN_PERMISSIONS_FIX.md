# Исправление управления правами администраторов

## Дата: 29 октября 2025

## Проблемы

### 1. Кнопки управления правами не работали (неактивные)

**Причина:** Двойной вызов `query.answer()` вызывал ошибку Telegram API
**Файл:** `modules/admins/wizard.py`

#### Затронутые функции:
- `set_role()` - изменение роли (строка 344-371)
- `toggle_permission()` - переключение прав (строка 434-475)
- `reset_permissions()` - сброс прав (строка 477-495)
- `activate_admin()` - активация админа (строка 500-513)
- `deactivate_admin()` - деактивация админа (строка 515-528)

### 2. Права не обновлялись при смене роли

**Причина:** При изменении роли не сбрасывались кастомные права
**Результат:** Админ сохранял старые права после смены роли

---

## Исправления

### 1. Убраны двойные вызовы query.answer()

**Было:**
```python
async def set_role(self, update, context, user_id, role):
    query = update.callback_query
    await query.answer()  # ❌ Первый вызов

    if self.db.set_role(user_id, role):
        await query.answer("✅ Роль изменена", show_alert=True)  # ❌ Второй вызов

    await self.show_admin_view(update, context, user_id)
```

**Стало:**
```python
async def set_role(self, update, context, user_id, role):
    query = update.callback_query
    # ✅ НЕТ раннего query.answer()

    if self.db.set_role(user_id, role):
        # Сначала обновить интерфейс
        await self.show_admin_view(update, context, user_id)
        # Потом уведомление
        await query.answer("✅ Роль изменена", show_alert=True)
```

### 2. Добавлен сброс прав при смене роли

**Было:**
```python
if self.db.set_role(user_id, role):
    # Роль изменена, но кастомные права остались!
    pass
```

**Стало:**
```python
if self.db.set_role(user_id, role):
    # ВАЖНО: Сбросить кастомные права!
    self.db.reset_permissions(user_id)
    # Теперь права будут браться из новой роли
```

### 3. Добавлена проверка прав владельца

**Добавлено в `set_role()`:**
```python
# Проверка прав - только owner может менять роли
if not self.is_owner(update.effective_user.id):
    await query.answer("❌ Только владелец может изменять роли", show_alert=True)
    return
```

---

## Затронутые функции (детально)

### set_role() - Изменение роли

**Строка:** 344-371

**Изменения:**
1. ✅ Убран ранний `await query.answer()`
2. ✅ Добавлена проверка `is_owner()`
3. ✅ Добавлен сброс прав `reset_permissions()`
4. ✅ Изменен порядок: сначала обновление UI, потом уведомление

**До:**
```python
await query.answer()  # ❌ Ранний вызов
if self.db.set_role(user_id, role):
    self.db.log_action(...)
    await query.answer("✅", show_alert=True)  # ❌ Двойной вызов
await self.show_admin_view(...)  # Обновление в конце
```

**После:**
```python
# Проверка прав
if not self.is_owner(...):
    await query.answer("❌ Только владелец", show_alert=True)
    return

if self.db.set_role(user_id, role):
    self.db.reset_permissions(user_id)  # ✅ Сброс прав
    self.db.log_action(...)
    await self.show_admin_view(...)  # ✅ Сначала обновить UI
    await query.answer("✅", show_alert=True)  # ✅ Потом уведомление
```

### toggle_permission() - Переключение права

**Строка:** 434-475

**Изменения:**
1. ✅ Убран ранний `await query.answer()`
2. ✅ Изменен порядок: сначала UI, потом уведомление

**До:**
```python
await query.answer()  # ❌ Ранний вызов

# Проверки...

if self.db.set_permissions(...):
    await query.answer("✅", show_alert=False)  # ❌ Двойной вызов
else:
    await query.answer("❌", show_alert=True)

await self.show_permissions(...)  # Обновление в конце
```

**После:**
```python
# Проверки...

if self.db.set_permissions(...):
    await self.show_permissions(...)  # ✅ Сначала обновить UI
    await query.answer("✅", show_alert=False)  # ✅ Потом уведомление
else:
    await query.answer("❌", show_alert=True)
```

### reset_permissions() - Сброс прав

**Строка:** 477-495

**Изменения:**
1. ✅ Убран ранний `await query.answer()`
2. ✅ Изменен порядок: сначала UI, потом уведомление

### activate_admin() / deactivate_admin()

**Строки:** 500-528

**Изменения:**
1. ✅ Убран ранний `await query.answer()`
2. ✅ Изменен порядок: сначала UI, потом уведомление

---

## Результат

### ✅ Что исправлено:

1. **Кнопки управления правами теперь работают** - нет ошибок Telegram API
2. **Права обновляются при смене роли** - сбрасываются кастомные права
3. **Добавлена проверка прав владельца** - только owner может менять роли
4. **Правильный порядок обновления** - сначала UI, потом уведомление

### 🎯 Проверьте:

1. Откройте `/admins` в боте
2. Выберите любого админа
3. Нажмите "🔐 Права"
4. Попробуйте переключить любое право → ✅ Должно работать!
5. Вернитесь назад и нажмите "🔖 Изменить роль"
6. Выберите новую роль → ✅ Роль должна измениться!
7. Зайдите снова в "🔐 Права" → ✅ Права должны обновиться по новой роли!

---

## Дополнительные улучшения

### Проверки добавленные ранее (в предыдущем коммите)

В `toggle_permission()` также были добавлены:

1. **Проверка владельца:**
   ```python
   if not self.is_owner(update.effective_user.id):
       await query.answer("❌ Только владелец может изменять права", show_alert=True)
       return
   ```

2. **Проверка существования админа:**
   ```python
   admin = self.db.get_admin(user_id)
   if not admin:
       await query.answer("❌ Админ не найден", show_alert=True)
       return
   ```

3. **Валидация права:**
   ```python
   from .db import PERMISSIONS
   if permission not in PERMISSIONS:
       await query.answer("❌ Неверное право", show_alert=True)
       return
   ```

---

## Технические детали

### Почему двойной query.answer() вызывал ошибку?

Telegram Bot API позволяет ответить на callback query **только один раз**. При повторном вызове возникает ошибка:

```
telegram.error.BadRequest: Query is too old and response timeout expired or query ID is invalid
```

### Почему порядок важен?

1. `show_admin_view()` или `show_permissions()` вызывает `query.edit_message_text()`
2. Это обновляет сообщение с кнопками
3. ЗАТЕМ можно вызвать `query.answer()` для показа уведомления
4. Если вызвать `query.answer()` ДО `edit_message_text()`, callback уже обработан и нельзя редактировать сообщение

### Почему нужно сбрасывать права при смене роли?

Права хранятся в двух местах:
1. **Роль по умолчанию** - ROLE_PERMISSIONS в `db.py`
2. **Кастомные права** - в поле `permissions` в БД (JSON)

Если у админа есть кастомные права, они **переопределяют** роль:

```python
def get_permissions(self, user_id):
    admin = self.get_admin(user_id)

    if admin['permissions']:  # Если есть кастомные
        return admin['permissions']  # Вернуть кастомные

    # Иначе вернуть по роли
    return ROLE_PERMISSIONS[admin['role']]
```

Поэтому при смене роли нужно **обнулить** кастомные права:

```python
self.db.reset_permissions(user_id)  # SET permissions = NULL
```

---

## Коммиты

1. **Первый коммит** (c72fa71):
   - Исправлен `toggle_permission()`
   - Добавлены проверки и валидация

2. **Этот коммит**:
   - Исправлены `set_role()`, `reset_permissions()`, `activate_admin()`, `deactivate_admin()`
   - Добавлен сброс прав при смене роли
   - Добавлена проверка владельца в `set_role()`

---

## Для будущего

### Шаблон для функций с callback query:

```python
async def some_action(self, update, context, user_id, value):
    """Описание действия"""
    query = update.callback_query

    # ❌ НЕ ДЕЛАТЬ: await query.answer() здесь!

    # Проверки (если нужны)
    if not self.has_permission(...):
        await query.answer("❌ Ошибка", show_alert=True)
        return

    # Выполнить действие
    if self.db.some_action(user_id, value):
        # ✅ ПРАВИЛЬНО: сначала обновить UI
        await self.show_updated_view(update, context, user_id)

        # ✅ ПОТОМ уведомление
        await query.answer("✅ Успешно", show_alert=True)
    else:
        await query.answer("❌ Ошибка", show_alert=True)
```

**Правило:** `query.answer()` вызывается **ОДИН РАЗ** и **ПОСЛЕ** обновления интерфейса!

---

**Автор:** Claude Code
**Дата:** 29 октября 2025
