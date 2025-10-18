# Product Database Tools - Quick Start Guide

## 🚀 Quick Start

### Problem: Missing product tables

```bash
# Run migration to create tables
python3 migrate_product_db.py
```

### Problem: Corrupted database

```bash
# Step 1: Diagnose the issue
python3 diagnose_product_db.py

# Step 2: Reset with data preservation
python3 reset_product_db.py
```

### Problem: Need to start fresh

```bash
# Clean reset (WARNING: Deletes all product data)
python3 reset_product_db.py --clean
```

## 📋 Script Overview

| Script | Purpose | Safe to Run |
|--------|---------|-------------|
| `migrate_product_db.py` | Creates missing tables/indexes | ✅ Yes - Read-only unless tables missing |
| `diagnose_product_db.py` | Diagnoses database issues | ✅ Yes - Read-only |
| `reset_product_db.py` | Resets tables with data backup | ⚠️ Caution - Creates backup first |
| `reset_product_db.py --clean` | Wipes all product data | ❌ Dangerous - Backup recommended |

## 🔍 Common Commands

### Check Database Health
```bash
python3 diagnose_product_db.py
```

### Create Missing Tables
```bash
python3 migrate_product_db.py
```

### Fix Corrupted Tables (Keep Data)
```bash
python3 reset_product_db.py
```

### Fresh Start (Delete Everything)
```bash
python3 reset_product_db.py --clean
```

## 📊 What Gets Created

### Tables
- **products** - Product catalog with prices
- **admin_products** - Admin product assignments and debts

### Indexes (for performance)
- `idx_products_name` - Fast product lookups
- `idx_admin_products_admin_id` - Fast admin queries
- `idx_admin_products_settled` - Fast debt filtering
- `idx_admin_products_admin_settled` - Composite queries

## 🎯 Use Cases

### Initial Setup
```bash
# First time setting up product management
python3 migrate_product_db.py
```

### After Git Pull
```bash
# After pulling updates that add product features
python3 migrate_product_db.py
```

### Database Issues
```bash
# When you see SQLite errors
python3 diagnose_product_db.py
python3 reset_product_db.py
```

### Testing
```bash
# For testing without affecting production
python3 reset_product_db.py --clean --db=test.db
```

## ⚡ Integration with Bot

The ProductManager automatically creates tables when initialized, but you can ensure everything is set up correctly:

```python
from product_manager import ProductManager
from migrate_product_db import ProductDatabaseMigration

# Ensure tables exist before using ProductManager
migration = ProductDatabaseMigration('knowledge.db')
migration.run_migration()

# Now use ProductManager
pm = ProductManager('knowledge.db')
pm.add_product('Test Product', 100.0)
```

## 🔒 Safety Features

### Automatic Backups
All reset operations create timestamped backups:
```
knowledge.db.backup_20251018_115500
```

### Confirmation Prompts
Reset operations require Enter key confirmation.

### Data Preservation
Default reset mode preserves all existing data.

## 📖 Full Documentation

For complete documentation, see:
- [PRODUCT_DB_MIGRATION_GUIDE.md](PRODUCT_DB_MIGRATION_GUIDE.md)

## 🆘 Emergency Recovery

If something goes wrong:

```bash
# 1. Find the most recent backup
ls -lt knowledge.db.backup_* | head -1

# 2. Restore it
cp knowledge.db.backup_YYYYMMDD_HHMMSS knowledge.db

# 3. Verify
python3 diagnose_product_db.py
```

## 🧪 Testing

Run the test suite to verify everything works:

```bash
# Test all migration tools
python3 test_product_migration.py

# Test ProductManager functionality
python3 test_product_fixes.py
```

## 💡 Tips

1. **Always run diagnostics first** when troubleshooting
2. **Check the logs** - all scripts provide detailed output
3. **Backups are automatic** but know where they are
4. **Use --clean sparingly** - it deletes everything
5. **Test in development** before running in production

## 🔗 Related Files

- `product_manager.py` - Main product management class
- `product_commands.py` - Telegram bot commands
- `bot.py` - Main bot integration
- `test_product_fixes.py` - Product functionality tests
- `test_product_migration.py` - Migration tools tests
