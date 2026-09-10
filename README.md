# Maison Roast — Coffee Shop Web Application

## Overview
A full-stack Django web application for a vintage coffee shop. It features product
browsing, user authentication and order management, backed by a PostgreSQL database
running in Docker — plus **Basil**, an AI concierge that answers questions about the
menu and the shop, identifies food from a photo with a locally-run CNN, and places
orders through the same audited checkout the website uses.

## The concept — Maison Roast
*"Maison"* is French for house; *"Roast"* is the raw act of turning green beans over
heat. The name says the whole idea: roasting and baking as **domestic crafts**, done in
a home rather than a factory. The fiction behind the shop — used throughout the copy and
fed to Basil as its knowledge base — is a defunct cobbler's workshop in the arts
district, taken over in 2018 by two friends, Elias and Maya, who were tired of sterile
fluorescent chains. One location, on purpose: depth over scale, small-batch roasting, no
franchising.

That concept drives the interface, not just the prose. The design is **vintage without
the stuffy nostalgia** — worn cognac leather, oak, filament-bulb amber, film photography
and mid-century type, aimed at a young, loud, free-spirited crowd. It is expressed in
code as five colour tokens (`espresso`, `roast`, `crema`, `terracotta`, `gold`, plus an
evening-only `plum` for the bar) and three typefaces — Playfair Display, Great Vibes and
Lato — all defined in `tailwind.config.js` and **self-hosted**, never a webfont CDN.

Basil is the same idea in software: not a support bot, but the person behind the
counter who knows the menu, talks like a human, and is honest when the answer is no.

## Features
- **User Authentication**: registration, login and logout on a custom user model.
- **Product Catalog**: products carry images, prices, descriptions and **many categories
  at once** (an Iced Latte is `Coffee`, `Iced`, `Espresso` and `Milky`), filterable from
  the menu page.
- **Order Management**: place orders and view order history. Checkout is atomic and row-
  locked, the price is always read from the catalog, and deletion is a soft delete that
  restores stock.
- **Favourites** (`/favourites/`): per-browser, `localStorage` only — no account needed.
- **The Bar** (`/bar/`): the alcohol catalog, behind a server-side **age gate** and an
  **evening-only service-hours gate**.
- **Basil, the AI concierge**: streaming chat in a side rail on every page, with menu
  lookups, image recognition, RAG over the shop's own documents, and order placement.
- **REST API**: product, profile and order endpoints via Django REST Framework.
- **Profile CRUD**: a JS-driven page over `/api/users/me/` (PUT / PATCH / DELETE).
- **Responsive Interface**: Tailwind, compiled locally, verified down to 360px.

## Tech Stack
- **Backend Framework**: Django 6.1
- **Database**: PostgreSQL 15 with **pgvector** (Dockerized)
- **API**: Django REST Framework
- **Frontend**: Tailwind CSS 3.4.7 compiled locally + vanilla ES modules (no React, Vue,
  Alpine or HTMX; no runtime CDN)
- **AI**: Anthropic Claude for the agent loop, Voyage AI for embeddings,
  **ONNX Runtime** for on-server image classification
- **Language**: Python 3.13
- **Containerization**: Docker

## Prerequisites
- Python 3.13 or higher
- Node.js and `npm` (the CSS is compiled, not loaded from a CDN)
- Docker Desktop or Engine
- `pip` (Python package manager)
- API keys for Anthropic and Voyage AI — **only if you want Basil**; the rest of the site
  runs fine without them

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

### 4. Build the CSS
**Do this or every page renders unstyled.** Tailwind is compiled locally; there is no
runtime CDN.

```bash
npm install
npm run build      # two steps: `fonts` (copies the woff2 files) then `css`
```

`static/css/main.css` and `static/css/files/` are gitignored build artifacts. Use
`npm run watch` while editing styles, and re-run `npm run fonts` if the font imports
change.

### 5. Environment Configuration
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

# Alcohol compliance (optional, these are the defaults) ---
MINIMUM_ALCOHOL_AGE=18
ALCOHOL_CATEGORY_NAME=Alcohol
ALCOHOL_SERVICE_START_HOUR=18

# Basil, the AI concierge (optional; omit to run the site without him) ---
BASIL_API_KEY=<your Anthropic API key>
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_WORKSPACE_ID=<only for identity-linked keys; bare id, not the Console URL>
VOYAGE_API_KEY=<your Voyage AI key>
VOYAGE_MODEL=voyage-4-lite
VOYAGE_DIM=1024
BASIL_CNN=ml/basil_effnetv2s.onnx
BASIL_UNKNOWN_THRESHOLD=0.60
BASIL_MAX_TOOL_ITERATIONS=8
```

`.env` is gitignored — never commit real credentials.

No key is ever exposed to a template or to JavaScript — every model call happens
server-side.

### 6. Database Setup (Docker)
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

### 7. Apply Migrations & Load Data
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

### 8. Set Up Basil (optional)
Skip this and the site works; the chat rail simply has nothing behind it.

**The CNN weights.** `ml/basil_effnetv2s.onnx` is 81 MB and gitignored, so a fresh clone
does not have it. The trained model is published on Hugging Face under Beau's profile
with a public licence — download it to `ml/` (or point `BASIL_CNN` at wherever you put
it). `ml/label_map.json` **is** committed, and the two must match.

**The knowledge base.** Build the RAG corpus once the Voyage key is in `.env`:

```bash
python manage.py ingest_knowledge --dry-run   # chunk and report, no API calls, no writes
python manage.py ingest_knowledge             # embed and store
```

Re-running is idempotent: chunks are keyed on `(source, chunk_index)` and updated in
place, and chunks orphaned by a shrunk source file are deleted.

## Running the Application
Start the development server:
```bash
python manage.py runserver
```
Open your browser and navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Basil — the AI concierge
Basil lives in a rail on the right of every page (`[x]` collapses it; the state persists
in `localStorage`). He is a Claude-driven agent loop running **entirely server-side**,
streaming his replies over SSE.

### What he can do
Eight tools. He never sees the database directly — each tool is a narrow, audited
server-side function, and `dispatch()` **injects the signed-in user** rather than reading
an identity out of the model's output, so a prompt injection cannot ask for someone
else's orders.

| tool | what it does |
|---|---|
| `search_menu` | keyword and/or category search over the live catalog |
| `get_product_details` | full detail for one product by id |
| `check_product_availability` | does this exist, and is it orderable right now |
| `check_compliance` | may this customer be sold alcohol, at this hour |
| `create_order` | places a real order through the shared checkout service |
| `read_orders` | the signed-in customer's own recent orders |
| `vision_identify` | classifies an uploaded photo with the local CNN |
| `search_knowledge_base` | semantic search over the shop's own documents |

Tools never raise: a failure comes back as `{"error": ...}` so a crash cannot kill the
conversation. The loop is capped at 8 tool calls per turn, enforced in code rather than
requested in the prompt.

### What he refuses
Alcohol is gated **in `orders/services.py::place_order`**, not in the prompt and not in a
tool — that is the one function both the website checkout and `create_order` call, so
neither can go around it. Under the legal age, or before the bar opens, the order is
refused before any stock moves. `check_compliance` lets Basil say no politely *before*
taking the order, but it is advisory; the service is what binds. He is also told never to
ask a customer their age — the check does not consult the conversation, so interrogating
people would be worse UX and no more secure.

### Chat persistence
Conversations are stored in Postgres and replayed by `GET /basil/history/`, so a chat
survives navigation, a new tab and a different device. `localStorage` holds only a paint
cache so the rail is not blank while that fetch is in flight — it is never authoritative.

### Endpoints
`POST /basil/chat/` (SSE stream), `GET /basil/history/`, `POST /basil/upload-image/`.

## Food recognition — EfficientNetV2-S
A customer can drop a photo into the chat and ask "do you sell this?".

- **Model**: EfficientNetV2-Small, fine-tuned on a Food-41 style dataset, exported to
  **ONNX** and run in-process with ONNX Runtime. No image ever leaves the server for a
  third-party vision API.
- **Classes**: **40 food classes plus `unknown`** (class 40). Below
  `BASIL_UNKNOWN_THRESHOLD` (default 0.60) the tool reports `is_unknown` and Basil asks
  what the customer is looking for instead of guessing. `unknown` is never offered as a
  suggestion.
- **Measured accuracy**: 12/12 top-1 on a deliberately hard real-photo set, most above
  0.99 confidence, 98–224 ms per image against a 400 ms budget.
- **From photo to answer**: `vision_identify` returns a label like `creme_brulee`, which
  the menu tools resolve against the real catalog — including an accent- and
  punctuation-folding fallback, so `creme_brulee` finds "Crème Brûlée".
- Training notebooks and the ETL report are in `ml/`. The `.onnx` file itself is
  gitignored (81 MB) and downloaded from Hugging Face.

Uploads are capped at 5 MB and currently accept **JPEG and PNG only** — WebP works fine
for inference but is refused at the endpoint, which is a known open item.

## Running Tests
243 tests covering products, orders, users and Basil.

Run all tests:
```bash
python manage.py test
```

Run specific app tests:
```bash
python manage.py test users
python manage.py test products
python manage.py test orders
python manage.py test basil
```

**No test calls the Anthropic or Voyage APIs** — the clients are mocked, deliberately, so
running the suite never costs credits. The vision tests do not need the `.onnx` file
either.

## Project Structure
- **`CoffeeWebShop/`**: Main project configuration (settings, URLs, WSGI).
- **`users/`**: Custom user model with the age fields, authentication views.
- **`products/`**: Product and Category models, catalog views, favourites, the bar, API.
- **`orders/`**: Order processing and history, plus `services.py` — the single checkout
  function shared by the website and Basil.
- **`basil/`**: the AI concierge — `agent.py` (the loop), `tools/` (the eight tools),
  `vision/` (ONNX inference), `rag/` (pgvector retrieval), `knowledge/` (the source
  documents), `prompts/system_prompt.md`.
- **`ml/`**: CNN training notebooks, label map, training curves and reports.
- **`static/`**: `src/input.css` (Tailwind source and component classes), `js/` (vanilla
  ES modules), `icons/`, `images/`.
- **`templates/`**: `base.html`, the site shell every page extends, plus the error pages.
- **`manage.py`**: Django CLI utility.

## Project Directory Structure

```
├── CoffeeWebShop/          # settings, root urlconf, asgi/wsgi
├── basil/                  # the AI concierge
│   ├── agent.py            # the tool-use loop, SSE streaming
│   ├── models.py           # ChatSession, ChatMessage, UploadedImage, corpus chunks
│   ├── views.py            # /basil/chat/, /history/, /upload-image/
│   ├── knowledge/          # the source markdown for the RAG corpus
│   ├── prompts/            # system_prompt.md
│   ├── rag/                # chunking, embedding, pgvector retrieval
│   ├── tools/              # menu, create_order, check_compliance, read_orders,
│   │                       #   vision, knowledge  (+ __init__.py: schemas + dispatch)
│   └── vision/             # ONNX inference and the label map
├── ml/                     # training notebooks, label_map.json, reports
│                           #   (basil_effnetv2s.onnx is gitignored — 81 MB)
├── orders/
│   ├── services.py         # place_order — the one checkout, age + hours gates
│   ├── models.py           # Order, ProductOrder
│   └── templates/orders/
├── products/
│   ├── models.py           # Product, Category (M2M), ProductImage
│   ├── permissions.py      # IsStaffOrReadOnly
│   └── templates/products/ # home, product_list, product_detail, bar, favourites, ...
├── users/
│   ├── models.py           # CustomUser: gender, date_of_birth, computed age
│   ├── api.py              # /api/users/me/
│   └── templates/users/
├── static/
│   ├── src/input.css       # Tailwind source + @layer components
│   ├── js/                 # vanilla ES modules (chat, basil-panel, favourites, ...)
│   ├── icons/  images/
│   └── css/                # build output — gitignored
├── templates/              # base.html, 404.html, 403.html, 500.html
├── docker-compose.yml      # pgvector/pgvector:pg15 on host port 5433
├── tailwind.config.js      # the design tokens live here, not in templates
├── package.json
├── requirements.txt        # pinned direct runtime deps
├── requirements-dev.txt    # -r requirements.txt + dev-only tools
├── manage.py
└── README.md
```


## License
MIT
