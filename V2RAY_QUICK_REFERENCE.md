# V2Ray User Management - Quick Reference

## 🚀 Quick Start Guide

### View All Users
1. Send `/v2ray` to the bot
2. Click "📡 Серверы"
3. Select your server
4. Click "👥 Пользователи"

**Result**: See ALL users from the actual Xray server configuration

---

## 👤 User Management

### View User Details
- Click on any user in the list
- See complete information: email, UUID, flow type, expiration

### Delete a User
1. Click on user → "🗑️ Удалить"
2. Confirm with "✅ Да, удалить"
3. User removed from both server and database

### Add Temporary Access
1. Click on user
2. Click "⏰ Временный доступ"
3. Select duration (1, 3, 7, 14, 30, 60, or 90 days)
4. User will be auto-deleted after expiration

### Change Expiration
- If temp access already set, click "🔄 Изменить срок"
- Select new duration

### Remove Time Limit
- Click "♾️ Убрать ограничение"
- User now has permanent access

---

## 📋 Command Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/v2ray` | Main V2Ray menu | `/v2ray` |
| `/v2add` | Add server | `/v2add main 185.123.45.67 root pass123` |
| `/v2setup` | Install Xray on server | `/v2setup main` |
| `/v2user` | Add user | `/v2user main 1 Nikita` |
| `/v2list` | List servers | `/v2list` |
| `/v2stats` | Server statistics | `/v2stats main` |

---

## 🎯 Common Tasks

### Grant 7-Day Trial Access
```
1. /v2ray → Серверы → [Server] → Пользователи
2. Click on user
3. ⏰ Временный доступ → 7 дней
```

### Check Who Has Expired Access
```
1. /v2ray → Серверы → [Server] → Пользователи
2. Look for users with red "⚠️ Доступ истёк" indicator
```

### Extend User's Access
```
1. Click on user
2. 🔄 Изменить срок
3. Select new duration
```

### Permanently Remove Time Limit
```
1. Click on user
2. ♾️ Убрать ограничение
```

---

## 🔍 Troubleshooting

### "User list is empty but I know there are users"
**Solution**: The server might be down or SSH connection failed. Check:
- Server is running: `/v2stats <server_name>`
- SSH credentials are correct
- Xray service is active

### "User still appears after deletion"
**Solution**: 
- Click "🔄 Обновить" to refresh from server
- If still present, check Xray service: `/v2stats <server_name>`

### "Can't set temporary access"
**Check**:
- You are the bot owner (only owner can manage users)
- User exists on the server
- Database connection is working

---

## ⚡ Tips & Best Practices

### 1. Regular Cleanup
Check expired users regularly:
- Old expired users will be auto-deleted
- Keep user list clean for better performance

### 2. Use Descriptive Names
When adding users, use clear comments:
```bash
# Good
/v2user main 1 "John - Trial - expires 2024-10"

# Better
/v2user main 1 "John Smith - Company XYZ"
```

### 3. Set Appropriate Durations
- **1 day**: Quick tests
- **7 days**: Trial access
- **30 days**: Monthly subscriptions
- **90 days**: Quarterly access

### 4. Monitor Your Servers
- Check stats regularly: `/v2stats <server>`
- Keep track of user count
- Watch for unusual activity

### 5. Refresh User List
- Click "🔄 Обновить" after making changes
- Ensures you see current server state
- Helps identify sync issues

---

## 📊 User Information Display

When viewing a user, you'll see:

```
👤 Детали пользователя

━━━━━━━━━━━━━━━━━━━━━━
📧 Email: user@example.com
🔑 UUID: 12345678-1234-1234-1234-123456789abc
⚡ Flow: xtls-rprx-vision
🖥️ Сервер: main

⏰ Временный доступ:
   Истекает: 2024-10-25 12:00
   Осталось: 7 дней
━━━━━━━━━━━━━━━━━━━━━━
```

### Field Meanings

- **📧 Email**: User identifier/comment
- **🔑 UUID**: Unique user ID in Xray
- **⚡ Flow**: Connection flow type (usually `xtls-rprx-vision`)
- **🖥️ Сервер**: Server name
- **⏰ Временный доступ**: Expiration info (if set)

---

## 🔐 Security Notes

1. **Owner Only**: Only the bot owner can manage V2Ray users
2. **Confirmation Required**: Deletions require confirmation
3. **Secure Connections**: All server operations use SSH
4. **Audit Trail**: All changes are logged with timestamps

---

## 📱 Mobile Usage

The bot works great on mobile:
- Tap buttons instead of typing commands
- Swipe to see long UUIDs
- Easy one-handed operation
- Quick access to common tasks

---

## ❓ FAQ

**Q: Can I see deleted users?**
A: No, deleted users are permanently removed from both server and database.

**Q: What happens when temp access expires?**
A: User is automatically deleted from the server at the next cleanup cycle.

**Q: Can I cancel a scheduled deletion?**
A: Yes! Click "♾️ Убрать ограничение" before expiration.

**Q: Do I need to restart anything?**
A: No, the bot handles all Xray service restarts automatically.

**Q: Can I bulk delete users?**
A: Not currently. Each user must be deleted individually for safety.

---

## 📞 Support

For issues or questions:
1. Check this guide first
2. Review V2RAY_GUIDE.md for detailed documentation
3. Check logs: `journalctl -u club_assistant -n 100`
4. Contact bot administrator

---

## 🎉 Happy Managing!

Remember:
- ✅ All users visible from server config
- ✅ Complete deletion (server + database)
- ✅ Automatic expiration handling
- ✅ Interactive and easy to use

Enjoy the improved V2Ray user management! 🚀
