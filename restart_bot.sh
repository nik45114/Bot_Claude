#!/bin/bash
cd /opt/club_assistant

# Stop systemd service to prevent auto-restart conflicts
echo "🛑 Stopping systemd service..."
sudo systemctl stop club_assistant.service

# Kill any running bot processes
echo "🔪 Killing existing bot processes..."
sudo pkill -9 -f "python.*bot.py"
sleep 3

# Start bot manually
echo "🚀 Starting bot..."
nohup python3 bot.py > bot.log 2>&1 &
BOT_PID=$!
echo "✅ Bot restarted with PID: $BOT_PID"
sleep 2

# Check if bot is running
if ps -p $BOT_PID > /dev/null; then
   echo "✅ Bot is running successfully"
   tail -20 bot.log | grep -E "запущен|ERROR"
else
   echo "❌ Bot failed to start. Check bot.log for errors"
   tail -30 bot.log
fi
