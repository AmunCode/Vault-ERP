# Vault Enterprise Resourse Program

## Overview
Vault ERP is an internal inventory and operations system designed to manage:
- Product catalog (brands, categories, items)
- Inventory (bulk and individual units)
- Sales tracking across marketplaces (eBay, Whatnot, etc.)
- Expense tracking
- Future: marketplace listing automation and reporting

This system is designed to support resale businesses dealing with:
- Clothing
- Luxury goods
- Accessories
- Electronics (optional support)

## Features (Phase 1)
- Product catalog with structured categories and brands
- Inventory tracking:
  - Bulk inventory (InventoryLot)
  - Individual items (InventoryUnit)
- Warehouse location tracking
- Inventory transaction history
- Sales tracking (orders + line items)
- Expense tracking with categories
- Django admin interface for all data

## Prerequisites
- Python 3.12+
- Django
- SQLite (development)
- Bootstrap (planned for UI)

## Project Structure
```
    VAULT-ERP/
    ├── catalog/
    ├── inventory/
    ├── sales/
    ├── expenses/
    ├── listings/
    ├── marketplaces/
    ├── media_manager/
    ├── core/
    └── vaultERP/
```

## Setup Instructions

1. Clone the repository:
  ```sh
  git clone https://github.com/yourusername/vault-erp.git
  cd vault-erp
  ```

2. Create virtual environment:
    ```sh
    python -m venv .venv
    .venv\Scripts\activate
    ```

3. Install dependencies:
  ```sh
  pip install django
  ```

4. Run migrations:
  ```sh
  python manage.py makemigrations
  python manage.py migrate
  ```
5. Create a superuser:
  ```sh
  python manage.py createsuperuser
  ```

6. Run the server:
  ```sh
  python manage.py runserver
  ```

7. Access admin panel:
  ```sh 
  127.0.0.1:8000/admin
  ```