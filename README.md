# Coffee Shop Web Application

## Overview
A full-stack Django web application for an online coffee shop. It features product browsing, user authentication, and order management, backed by a PostgreSQL database running in Docker.

## Features
- **User Authentication**: Secure registration, login, and logout functionalities using a custom user model.
- **Product Catalog**: Browse various coffee products with details including images, prices, descriptions, and categories (Hot Coffee, Cold Coffee, Bakery, etc.).
- **Order Management**: Users can place orders for products and view their order history/status.
- **REST API**: built-in API support for retrieving product data via Django REST Framework.
- **Responsive Interface**: User-friendly design.
- **Database**: Robust PostgreSQL integration for data persistence.

## Tech Stack
- **Backend Framework**: Django 6.0+
- **Database**: PostgreSQL 15 (Dockerized)
- **API**: Django REST Framework
- **Language**: Python 3.13
- **Containerization**: Docker

## Prerequisites
- Python 3.13 or higher
- Docker Desktop or Engine
- `pip` (Python package manager)

## Installation Guide

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd coffeeShop
```

### 2. Set Up Virtual Environment
Create and activate a virtual environment (recommended name: `coffee`).

```bash
# Create
python -m venv coffee

# Activate (Linux/MacOS)
source coffee/bin/activate

# Activate (Windows)
# coffee\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file in the root directory of the project. **This file is the
single source of truth for the database** — `docker-compose.yml` reads the
`POSTGRES_*` values to initialise the container, and Django reads
`DATABASE_URL`. Keep the two descriptions of the database in sync.

**Note**: The host port is `5433`, not `5432`, to avoid conflicts with a
Postgres installed directly on the host.

```env
DEBUG=True
SECRET_KEY=<generate your own>
ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_USER=admin
POSTGRES_NAME=coffee_shop_db
POSTGRES_PASSWORD=<your password>

DATABASE_URL=postgres://admin:<your password>@localhost:5433/coffee_shop_db
```

`.env` is gitignored — never commit real credentials.

### 5. Database Setup (Docker)
Start the PostgreSQL container from the repo root:

```bash
docker compose up -d
```

That is the whole setup. Compose creates the database, the role, and the
password from the `POSTGRES_*` values in `.env`, so there is no manual `CREATE
USER` / `GRANT` step and none of the PG15 `public`-schema ownership trouble
that hand-created roles run into. The role is the database owner and can create
databases, which Django's test runner requires.

Data lives in the named volume `maison_pgdata`. It survives `docker compose
down` and is not a target for `docker volume prune`. To check the container is
up and accepting connections:

```bash
docker compose ps          # STATUS should read "healthy"
```

To stop it, `docker compose down`; to stop it **and delete all data**,
`docker compose down -v`.

### 6. Apply Migrations & Load Data
Apply the Django migrations to create the database schema:
```bash
python manage.py migrate
```

The schema is now ready and the app will run against an empty catalog. Add
products through the Django admin (`python manage.py createsuperuser`, then
`/admin/`).

The maintainer's own seed fixtures live in `backups/`, which is deliberately
not published. If you have them, load in this order to respect foreign keys:

```bash
python manage.py loaddata backups/backup_users.json
python manage.py loaddata backups/backup_products.json
python manage.py loaddata backups/backup_orders.json
```

## Running the Application
Start the development server:
```bash
python manage.py runserver
```
Open your browser and navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Running Tests
This project includes unit tests for products, orders, and user authentication.

Run all tests:
```bash
python manage.py test
```

Run specific app tests:
```bash
python manage.py test users
python manage.py test products
python manage.py test orders
```

## Project Structure
- **`CoffeeWebShop/`**: Main project configuration (settings, URLs, WSGI).
- **`users/`**: Custom user model, authentication views (Login/Register/Logout).
- **`products/`**: Product models, views, and API endpoints.
- **`orders/`**: Order processing, creating orders, and viewing order history.
- **`templates/`**: HTML templates for the application.
- **`manage.py`**: Django CLI utility.

## Project Directory Structure    
    
```
├── CoffeeWebShop
│   ├── asgi.py
│   ├── docker-compose.yml
│   ├── settings.py
│   ├── templates
│   ├── urls.py
│   └── wsgi.py
├── db.sqlite3
├── manage.py
├── notes.txt
├── orders
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── __init__.py
│   ├── migrations
│   ├── models.py
│   ├── templates
│   │   └── orders
│   │       ├── order_detail.html
│   │       ├── order_list.html
│   │       ├── product_order_form.html
│   │    
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── products
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── __init__.py
│   ├── migrations
│   ├── serializers.py
│   ├── templates
│   │   └── products
│   │       ├── add_product.html
│   │       ├── home.html
│   │       ├── inner_base.html
│   │       ├── product_detail.html
│   │       └── product_list.html
│   ├── tests.py
│   ├── urls.py
│   └── views.py
└── users
    ├── admin.py
    ├── apps.py
    ├── forms.py
    ├── __init__.py
    ├── migrations
    ├── templates
    │   └── users
    │       ├── login.html
    │       ├── logout.html
    │       └── register.html
    ├── tests.py
    ├── urls.py
    └── views.py
├── README.md
├── requirement-dev.txt
├── requirements-dev.txt
├── requirements.txt
├── templates
│   └── base.html

```

## License
MIT
