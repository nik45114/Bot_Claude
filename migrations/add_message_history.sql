-- Migration: Add message history table for /summary command
-- Description: Store last 1000 messages in "общение" section for AI summarization
-- Date: 2025-11-01

-- Message history table (rolling buffer, max 1000 messages)
CREATE TABLE IF NOT EXISTS message_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  username TEXT,
  full_name TEXT,
  message_text TEXT NOT NULL,
  message_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups by chat and date
CREATE INDEX IF NOT EXISTS idx_message_history_chat_date ON message_history(chat_id, message_date DESC);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_message_history_cleanup ON message_history(chat_id, id);
