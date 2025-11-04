# Product Database Migration Guide

This guide covers the new database migration, reset, and diagnostics tools for managing product tables in the Club Assistant Bot.

## Overview

Three new scripts have been added to help manage product database tables:

1. **migrate_product_db.py** - Creates and migrates product tables
2. **reset_product_db.py** - Resets/recreates product tables with or without data preservation
3. **diagnose_product_db.py** - Diagnoses database issues with detailed logging

## Prerequisites

- Python 3.8+
- SQLite 3
- Access to the `knowledge.db` database file

## 1. Migration Script (migrate_product_db.py)

### Purpose
Ensures that product-related tables (`products` and `admin_products`) exist and are properly initialized with appropriate indexes.

### Usage

```bash
# Migrate the default database (knowledge.db)
python3 migrate_product_db.py

# Migrate a custom database
python3 migrate_product_db.py /path/to/custom.db
```

### What it does

1. **Checks database file existence and status**
2. **Creates tables if they don't exist:**
   - `products` - Stores product information
   - `admin_products` - Tracks products taken by admins
3. **Creates indexes for performance:**
   - `idx_products_name` - Index on product name
   - `idx_admin_products_admin_id` - Index on admin_id
   - `idx_admin_products_settled` - Index on settled status
   - `idx_admin_products_admin_settled` - Composite index
4. **Verifies table integrity**
5. **Provides detailed logging throughout**

### Output Example

```
======================================================================
   PRODUCT DATABASE MIGRATION SCRIPT
======================================================================

2025-10-18 11:52:29,862 - INFO - 🔧 Initializing Product Database Migration for: knowledge.db
2025-10-18 11:52:29,862 - INFO - 🚀 Starting Product Database Migration
2025-10-18 11:52:29,862 - INFO - ✅ Database file exists: knowledge.db
2025-10-18 11:52:29,862 - INFO - 📊 Database size: 2,048,576 bytes
...
2025-10-18 11:52:29,873 - INFO - 🎉 Product Database Migration completed successfully!
```

### When to use

- Initial setup of product management
- After database corruption
- When tables are missing
- When upgrading from older versions

## 2. Reset Script (reset_product_db.py)

### Purpose
Resets or recreates product tables with options to preserve or delete existing data.

### Usage

```bash
# Reset with data preservation (default)
python3 reset_product_db.py

# Clean reset (DELETE ALL DATA)
python3 reset_product_db.py --clean

# Reset a custom database
python3 reset_product_db.py --db=/path/to/custom.db

# Show help
python3 reset_product_db.py --help
```

### Options

- `--clean` - Perform clean reset without preserving data
- `--db=PATH` - Use custom database path
- `-h, --help` - Show help message

### What it does

#### With Data Preservation (Default)
1. Creates a timestamped backup of the database
2. Exports existing data from both tables
3. Drops indexes and tables
4. Recreates tables using migration script
5. Restores exported data
6. Provides backup location

#### Clean Mode (--clean)
1. Creates a timestamped backup of the database
2. Drops indexes and tables
3. Recreates empty tables using migration script
4. **WARNING: All product data is permanently deleted**

### Output Example

```
======================================================================
   PRODUCT DATABASE RESET SCRIPT
======================================================================

⚠️  This will reset product tables while preserving existing data.
📂 Database: knowledge.db

Press ENTER to continue, or Ctrl+C to cancel...

2025-10-18 11:55:00,000 - INFO - 🔄 Starting reset WITH data preservation
2025-10-18 11:55:00,001 - INFO - 📦 Creating backup: knowledge.db.backup_20251018_115500
2025-10-18 11:55:00,100 - INFO - ✅ Backup created: knowledge.db.backup_20251018_115500
...
2025-10-18 11:55:01,000 - INFO - 🎉 Database reset completed successfully WITH data preservation!
2025-10-18 11:55:01,000 - INFO - 💾 Backup saved at: knowledge.db.backup_20251018_115500
```

### When to use

- Database schema is corrupted
- Need to rebuild indexes
- Testing or development
- After major errors in product tables
- When switching database formats

### Safety Features

1. **Confirmation prompt** - Requires Enter key to proceed
2. **Automatic backup** - Creates timestamped backup before any changes
3. **Data preservation** - Default mode preserves all existing data
4. **Detailed logging** - Tracks every step of the process

## 3. Diagnostics Script (diagnose_product_db.py)

### Purpose
Comprehensive diagnostics and troubleshooting for product database issues.

### Usage

```bash
# Diagnose the default database
python3 diagnose_product_db.py

# Diagnose a custom database
python3 diagnose_product_db.py /path/to/custom.db
```

### What it checks

1. **Database File Status**
   - File exists
   - File size
   - Read/write permissions

2. **Database Integrity**
   - SQLite integrity check
   - Table structure validation

3. **Table Details** (for both products and admin_products)
   - Table existence
   - Column schema
   - Row count
   - Indexes
   - Foreign keys

4. **Data Integrity**
   - Orphaned admin_products (referencing non-existent products)
   - Products with invalid prices (≤ 0)
   - Admin_products with invalid quantities (≤ 0)
   - Products with empty names

5. **Statistics**
   - Total products
   - Total admin_products records
   - Unsettled records count
   - Total unsettled debt
   - Number of admins with debt
   - Most expensive product
   - Most taken product

### Output Example

```
======================================================================
   PRODUCT DATABASE DIAGNOSTICS
======================================================================

2025-10-18 11:53:41,085 - INFO - 🔍 Initializing Product Database Diagnostics
...
📂 Checking database file...
✅ Database file exists: knowledge.db
📊 File size: 2,048,576 bytes (2000.00 KB)
✅ File is readable
✅ File is writable

🔍 Checking database integrity...
✅ Database integrity check PASSED

📋 Checking table: products
✅ Table 'products' exists
📊 Columns (5):
   id (INTEGER) PRIMARY KEY
   name (TEXT) NOT NULL
   cost_price (REAL) NOT NULL
   created_at (TIMESTAMP) DEFAULT CURRENT_TIMESTAMP
   updated_at (TIMESTAMP) DEFAULT CURRENT_TIMESTAMP
📊 Row count: 15
🔍 Indexes (2):
   idx_products_name
   sqlite_autoindex_products_1 (UNIQUE)

...

📊 Gathering statistics...
📦 Total products: 15
📋 Total admin_products records: 47
💳 Unsettled records: 12
💰 Total unsettled debt: 3,500.00 ₽
👥 Admins with debt: 4
💎 Most expensive product: Premium Product (500.00 ₽)
📦 Most taken product: Popular Item (25 units)

======================================================================
📋 DIAGNOSTICS SUMMARY
======================================================================
✅ All product tables exist
📊 Products table: 15 rows
📊 Admin_products table: 47 rows
======================================================================
```

### When to use

- Before running migration or reset
- When experiencing database errors
- For regular health checks
- To understand current database state
- For troubleshooting issues
- To gather statistics

## Common Troubleshooting Scenarios

### Scenario 1: Missing Tables

**Symptoms:**
- Error: `no such table: products`
- Bot fails to load ProductManager

**Solution:**
```bash
# Run migration to create tables
python3 migrate_product_db.py
```

### Scenario 2: Corrupted Database

**Symptoms:**
- SQLite errors
- Integrity check failures
- Unexpected behavior

**Diagnosis:**
```bash
# First, diagnose the issue
python3 diagnose_product_db.py
```

**Solution:**
```bash
# Reset with data preservation
python3 reset_product_db.py
```

### Scenario 3: Performance Issues

**Symptoms:**
- Slow queries
- High response times

**Diagnosis:**
```bash
# Check if indexes exist
python3 diagnose_product_db.py
```

**Solution:**
```bash
# Recreate indexes using migration
python3 migrate_product_db.py
```

### Scenario 4: Data Integrity Issues

**Symptoms:**
- Orphaned records
- Invalid prices or quantities

**Diagnosis:**
```bash
# Identify data issues
python3 diagnose_product_db.py
```

**Solution:**
- Fix manually in database, OR
- Clean data, then run reset to rebuild

### Scenario 5: Testing/Development

**Goal:** Start with fresh database

**Solution:**
```bash
# Clean reset for fresh start
python3 reset_product_db.py --clean
```

## Best Practices

1. **Regular Diagnostics**
   - Run `diagnose_product_db.py` weekly or after issues
   - Monitor statistics and integrity

2. **Before Major Changes**
   - Always run diagnostics first
   - Create manual backup if needed

3. **After Issues**
   - Diagnose to understand the problem
   - Use appropriate tool (migrate vs reset)
   - Verify fix with diagnostics

4. **Data Preservation**
   - Default reset preserves data
   - Use `--clean` only when necessary
   - Backups are automatic but verify location

5. **Logging**
   - All scripts provide detailed logging
   - Review logs to understand what happened
   - Save logs for troubleshooting

## Script Integration

These scripts can be called from other Python code:

```python
# Migration
from migrate_product_db import ProductDatabaseMigration

migration = ProductDatabaseMigration('knowledge.db')
success = migration.run_migration()

# Diagnostics
from diagnose_product_db import ProductDatabaseDiagnostics

diagnostics = ProductDatabaseDiagnostics('knowledge.db')
success = diagnostics.run_diagnostics()

# Reset
from reset_product_db import ProductDatabaseReset

reset_handler = ProductDatabaseReset('knowledge.db')
# With data preservation
success = reset_handler.reset_with_data_preservation()
# Or clean
success = reset_handler.reset_without_data_preservation()
```

## Database Schema Reference

### products Table

```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    cost_price REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### admin_products Table

```sql
CREATE TABLE admin_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    admin_name TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    cost_price REAL NOT NULL,
    total_debt REAL NOT NULL,
    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

### Indexes

- `idx_products_name` - On products(name)
- `idx_admin_products_admin_id` - On admin_products(admin_id)
- `idx_admin_products_settled` - On admin_products(settled)
- `idx_admin_products_admin_settled` - On admin_products(admin_id, settled)

## Support

For issues or questions:

1. Run diagnostics first: `python3 diagnose_product_db.py`
2. Check the logs for detailed error messages
3. Refer to this guide for common scenarios
4. Review the ProductManager implementation in `product_manager.py`

## Files

- `migrate_product_db.py` - Migration script
- `reset_product_db.py` - Reset script
- `diagnose_product_db.py` - Diagnostics script
- `test_product_migration.py` - Test suite for all scripts
- `PRODUCT_DB_MIGRATION_GUIDE.md` - This guide
