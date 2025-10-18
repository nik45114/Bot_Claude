# Advanced Sorting and Identification for Debtors - Feature Summary

## Overview
This update adds advanced sorting capabilities and enhanced reporting features to the product management system, making it easier to track and identify debts by admin name and products.

## New Features

### 1. Sorting Debtors by Name
**Method**: `get_all_debts(sort_by='name')`
- Sort the list of debtors alphabetically by admin name
- Makes it easy to find a specific admin's debt quickly
- Example output:
  ```
  👤 Anna - 425 ₽
  👤 Igor - 1,440 ₽
  👤 Vanya - 280 ₽
  ```

### 2. Sorting Debtors by Debt Amount
**Method**: `get_all_debts(sort_by='debt')`
- Sort debtors by debt amount (highest to lowest)
- Helps identify who owes the most
- Example output:
  ```
  👤 Igor - 1,440 ₽
  👤 Anna - 425 ₽
  👤 Vanya - 280 ₽
  ```

### 3. Product Summary Report (Period-Based)
**Method**: `format_products_summary_report()`
- Shows total quantities of each product taken during a period
- Format: "12 Gorilla, 14 Redbull, 4 Bulmeni"
- Includes detailed breakdown with amounts
- Example output:
  ```
  📊 СВОДКА ПО ТОВАРАМ
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━
  
  📦 4 Bulmeni, 15 Gorilla, 5 Monster, 16 Redbull
  
  Детально:
    • Bulmeni: 4 шт = 160 ₽
    • Gorilla: 15 шт = 750 ₽
    • Monster: 5 шт = 275 ₽
    • Redbull: 16 шт = 960 ₽
  
  💰 ВСЕГО: 2,145 ₽
  ```

### 4. Detailed Debts Report (Per-User Breakdown)
**Method**: `format_detailed_debts_report()`
- Shows each admin's debt with product breakdown
- Format: "Vanya: 2 Redbull, 4 Bulmeni = 280₽"
- Clearly identifies admin names and their specific product quantities
- Example output:
  ```
  💳 ДЕТАЛЬНЫЕ ДОЛГИ АДМИНОВ
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━
  
  👤 Anna: 3 Gorilla, 5 Monster = 425 ₽
  
  👤 Igor: 12 Gorilla, 14 Redbull = 1,440 ₽
  
  👤 Vanya: 4 Bulmeni, 2 Redbull = 280 ₽
  
  💎 ВСЕГО ДОЛГОВ: 2,145 ₽
  ```

### 5. Enhanced Product Reports with Sorting
**Method**: `format_products_report(sort_by='admin'|'product')`

#### Sort by Admin (default)
Groups products under each admin:
```
👤 Vanya
   📦 Bulmeni: 4 шт × 40 ₽ = 160 ₽
   📦 Redbull: 2 шт × 60 ₽ = 120 ₽
   💰 Итого: 280 ₽
```

#### Sort by Product
Groups admins under each product:
```
📦 Gorilla
   👤 Anna: 3 шт × 50 ₽ = 150 ₽
   👤 Igor: 12 шт × 50 ₽ = 600 ₽
   💰 Итого: 750 ₽
```

## User Interface Updates

### New Buttons in Product Menu (Owner Only)

1. **Debts Report Screen**:
   - "📊 По долгу" - Sort by debt amount
   - "👤 По имени" - Sort by name
   - "📋 Детальный отчёт" - View detailed per-user breakdown

2. **Products Report Screen**:
   - "👤 По админам" - Group by admins
   - "📦 По товарам" - Group by products
   - "📊 Сводка" - View product summary

## API Changes

### ProductManager Class

#### New Methods:
- `get_all_debts(sort_by='debt'|'name')` - Get debts with sorting
- `get_products_summary(start_date=None, end_date=None)` - Get product totals
- `format_products_summary_report(start_date=None, end_date=None)` - Format summary
- `format_detailed_debts_report()` - Format detailed per-user report

#### Updated Methods:
- `get_products_report(start_date=None, end_date=None, sort_by='admin'|'product')` - Added sorting
- `format_all_debts_report(sort_by='debt'|'name')` - Added sorting
- `format_products_report(start_date=None, end_date=None, sort_by='admin'|'product')` - Added sorting

### ProductCommands Class

#### New Methods:
- `show_products_summary(update, context)` - Display product summary
- `show_detailed_debts(update, context)` - Display detailed debts

#### Updated Methods:
- `show_all_debts(update, context)` - Now supports sorting buttons
- `show_products_report(update, context)` - Now supports grouping buttons

## Bot Integration

New callback handlers added to `bot.py`:
- `product_all_debts_by_name` - Sort debts by name
- `product_report_by_product` - Group report by products
- `product_summary` - Show product summary
- `product_detailed_debts` - Show detailed debts

## Testing

Comprehensive test suite added in `test_product_sorting.py`:
- ✅ Test sorting debts by name and amount
- ✅ Test product summary aggregation
- ✅ Test report sorting by admin and product
- ✅ Test format of summary reports
- ✅ Test format of detailed debt reports
- ✅ Test format of sorted debt reports
- ✅ Test format of grouped product reports

All tests pass successfully!

## Demo

Run `demo_product_sorting.py` to see all new features in action with sample data.

## Backward Compatibility

All existing functionality remains unchanged. New parameters have default values:
- `sort_by` defaults to previous behavior
- Existing code will continue to work without modifications

## Benefits

1. **Better Organization**: Sort and group data in multiple ways
2. **Clear Identification**: Admin names are prominently displayed
3. **Easy Tracking**: Quickly see "12 Gorilla, 14 Redbull" style summaries
4. **Flexible Reporting**: Choose the view that works best for your needs
5. **Period Analysis**: See totals for specific time periods
