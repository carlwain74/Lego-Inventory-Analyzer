# 🧱 Lego Inventory — Set Price Analyzer

A local web application for analysing Bricklink marketplace pricing data across
Lego sets. Look up individual sets or import a collection into a persistent
inventory, with live price data fetched from the Bricklink API.

---

## Table of Contents

- [Project Description](#project-description)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [How to Run](#how-to-run)
- [Configuration](#configuration)
- [Local Network Access](#local-network-access)
- [How to Test](#how-to-test)
- [How to Contribute](#how-to-contribute)
- [Docker](#docker)

---

## Project Description

Lego Inventory connects to the [Bricklink](https://www.bricklink.com)
marketplace API to retrieve pricing data for one or more Lego sets and renders
it as an interactive dashboard.

### Key features

- **Check Prices** — enter a set number or upload a file of set numbers to
  retrieve live Bricklink pricing without saving to the database
- **Import to inventory** — single set or bulk file import saves sets to a
  local SQLite database; re-importing increments quantity
- **Inventory management** — browse your full inventory with live category
  chips and a search box; remove individual sets or clear all
- **Refresh prices** — refresh all inventory prices in one click; progress
  shown in an animated right-panel view
- **Current & past sales** — each set card displays separate pricing rows for
  items currently for sale and historical sold listings
- **Sale value estimate** — recommended sale price derived from the average of
  the current avg and max prices
- **Bulk import progress** — SSE-streamed progress panel shows imported,
  cached, and failed counts in real time; post-import summary with failure
  reasons
- **Thumbnail previews** — hover over a set image to see a full-size popup
- **API settings dialog** — manage Bricklink OAuth credentials through a
  built-in settings panel without touching config files manually
- **XLSX export** — download the full results as a formatted spreadsheet

### Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14 · Flask · SQLAlchemy · bricklink-py · openpyxl |
| Database | SQLite (via SQLAlchemy) |
| Frontend | Vanilla JS · CSS custom properties · HTML5 |
| Testing (Python) | pytest · pytest-cov |
| Testing (JS) | Jest · jest-environment-jsdom |
| Dependency management | Pipenv (Python) · npm (JS) |
| Container | Docker · Docker Compose · gunicorn |

---

## Project Structure

```
.
├── app.py                    # Flask application, route registration, DB init
├── database.py               # SQLAlchemy engine, session, upsert helpers
├── models.py                 # SQLAlchemy models — Set, SetPrice, Inventory
├── set_handler.py            # SetHandler class — wraps Bricklink API calls
├── bricklink.py              # BrickLinkAPI — low-level API client
├── generate_sheets.py        # XLSX generation
├── config.ini.template       # Credentials template (committed)
├── config.ini                # Bricklink API credentials (not committed)
├── VERSION                   # Current version string
├── Pipfile                   # Python dependencies
├── Pipfile.lock
├── .coveragerc               # Coverage configuration
├── run_tests.sh              # Wrapper script to run all test suites
├── scripts/
│   ├── release.sh            # Build, tag, and push image to Docker Hub
│   └── docker-push.md        # Detailed push guide
├── Dockerfile                # Container image definition
├── docker-compose.yml        # Docker Compose service configuration
├── .dockerignore             # Files excluded from the Docker build context
├── routes/
│   ├── __init__.py
│   ├── inventory.py          # GET/DELETE /inventory, POST /inventory/<n>/refresh
│   └── import_routes.py      # POST /inventory/import, POST /inventory/import/bulk
├── templates/
│   └── index.html            # Single-page frontend
└── tests/
    ├── __init__.py
    ├── conftest.py           # pytest shared fixtures and module stubs
    ├── test_app.py           # Flask route tests (/, /generate, /settings, /download)
    ├── test_bricklink.py     # BrickLinkAPI unit tests
    ├── test_database.py      # database helper tests (init_db, upsert, set_to_dict)
    ├── test_inventory_routes.py  # Inventory and import blueprint tests
    ├── test_models.py        # SQLAlchemy model tests
    ├── test_set_handler.py   # SetHandler unit tests
    └── test_ui.js            # Jest suite for frontend JS functions
```

---

## Prerequisites

- **Python 3.14+**
- **Pipenv** — `pip install pipenv`
- **Node.js 18+** and **npm** — [nodejs.org](https://nodejs.org)
- A Bricklink account with API credentials
  ([register here](https://www.bricklink.com/v3/api.page))

---

## How to Run

### 1. Install Python dependencies

```bash
pipenv install
```

### 2. Configure Bricklink API credentials

```bash
cp config.ini.template config.ini
```

Open `config.ini` and fill in your credentials, or use the in-app settings
dialog (see [Configuration](#configuration)).

### 3. Start the server

```bash
pipenv run python app.py
```

The app will be available at **http://localhost:5000**.

### 4. Use the app

**Check Prices**
- Select *Single Set Number*, type a set number (the `-1` suffix is added
  automatically), and click *Check Prices*
- Select *File List* to upload a `.txt` or `.list` file with one set number
  per line

**Import Sets**
- Switch to *Import Sets* in the sidebar
- Import a single set or upload a bulk file — sets are saved to the local
  database and quantity is incremented on re-import

**My Inventory**
- Click *My Inventory* to browse all imported sets
- Use category chips and the search box to filter
- Click ↻ to refresh all prices, 🗑 to clear the inventory
- Click *✕ Remove* on a card to decrement its quantity

---

## Configuration

Bricklink API credentials are stored in `config.ini` in the project root.
They can be updated at any time without restarting the server using the in-app
settings panel:

1. Click the **⚙ cogwheel** icon in the sidebar
2. Enter new values for any of the four credential fields
3. Use **Test Connection** to verify credentials before saving
4. Click **Save Settings** — changes take effect immediately

> **Security note:** `config.ini` contains sensitive credentials and should
> never be committed to version control. Ensure it is listed in `.gitignore`.

```gitignore
config.ini
```

---

## Local Network Access

The app binds to `0.0.0.0:5000` by default, making it reachable from other
devices on your local network via your machine's IP address
(e.g. `http://192.168.1.42:5000`).

To access it via a friendly hostname (e.g. `http://legoinventory.local`)
across your LAN, see the included setup guides:

- **`dnsmasq-setup.md`** — recommended: runs a lightweight DNS server on your
  Mac, no per-device config needed
- **`caddy-setup.md`** — alternative: reverse proxy to remove the port number
  from the URL

---

## How to Test

### Run all test suites

```bash
./run_tests.sh
```

The script will:
1. Run `pipenv sync --dev` to ensure all dev dependencies are installed
2. Run pytest with coverage reporting (threshold: **90%**)
3. Generate an HTML coverage report at `coverage_html/index.html`
4. Install JS dependencies if needed (`node_modules`)
5. Run the Jest suite

### Run suites individually

**Python (pytest):**
```bash
pipenv run pytest tests/ -v
```

**Python with coverage:**
```bash
pipenv run pytest tests/ -v \
  --cov=. \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-report=html:coverage_html
```

**JavaScript (Jest):**
```bash
cd tests
npm install
npm test
```

### What is tested

| Suite | File | Tests |
|---|---|---|
| Flask routes (`/`, `/generate`, `/settings`, `/download`) | `test_app.py` | 44 |
| BrickLinkAPI client | `test_bricklink.py` | 36 |
| Database helpers (`init_db`, `upsert_set`, `set_to_dict` etc.) | `test_database.py` | 27 |
| Inventory & import routes | `test_inventory_routes.py` | 30 |
| SQLAlchemy models | `test_models.py` | 15 |
| SetHandler | `test_set_handler.py` | 24 |
| Frontend JS (`normaliseSets`, `formatPrice`, `formatSaleDate`, `calcSaleValue`, `esc`) | `test_ui.js` | 59 |

---

## API Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the single-page frontend |
| `POST` | `/generate` | Check prices (no DB write) |
| `GET` | `/settings` | Read current credentials |
| `POST` | `/settings` | Save credentials to config.ini |
| `POST` | `/settings/test` | Test Bricklink API connection |
| `GET` | `/download` | Download Sets.xlsx |
| `GET` | `/inventory` | Return full inventory as JSON |
| `DELETE` | `/inventory` | Clear all inventory rows |
| `DELETE` | `/inventory/<set_number>` | Decrement or remove a set |
| `POST` | `/inventory/<set_number>/refresh` | Refresh price data for one set |
| `POST` | `/inventory/import` | Import a single set |
| `POST` | `/inventory/import/bulk` | Bulk import via SSE stream |

---

## How to Contribute

### 1. Fork and clone

```bash
git clone https://github.com/YOUR_USERNAME/bricklink.git
cd bricklink
```

### 2. Create a feature branch

```bash
git checkout -b feature/my-new-feature
# or
git checkout -b fix/bug-description
```

### 3. Make your changes

- Keep changes focused — one feature or fix per PR
- Follow the existing code style
- Add tests for any new Flask route in `tests/test_app.py` or
  `tests/test_inventory_routes.py`
- Add tests for any new JS function in `tests/test_ui.js`
- Do not commit `config.ini`, `coverage_html/`, `__pycache__/`,
  `node_modules/`, or `inventory.db`

### 4. Run the test suite

```bash
./run_tests.sh
```

All tests must pass and coverage must remain at or above **90%**.

### 5. Commit and push

```bash
git add .
git commit -m "Add last sale date to past sales card"
git push origin feature/my-new-feature
```

Open a Pull Request against `main`. Include what the change does, why it's
needed, screenshots if the UI is affected, and confirmation that
`./run_tests.sh` passes.

---

## Docker

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Running with Docker Compose

#### 1. Create config.ini

```bash
cp config.ini.template config.ini
```

#### 2. Start

```bash
docker compose up
```

The app will be available at **http://localhost:5000**.

To run in the background:

```bash
docker compose up -d
```

#### 3. Stop

```bash
docker compose down
```

### Volumes

| Volume | Mount | Contents |
|---|---|---|
| `db` | `/app/db` | `inventory.db` — persists between restarts |
| `output` | `/app/output` | `Sets.xlsx` — generated export files |
| `./config.ini` | `/app/config.ini` | Bind mount, read-only |

The database and generated files are stored in separate named volumes so they
persist across container restarts and can be backed up independently.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `OUTPUT_DIR` | `/app/output` | Where Sets.xlsx is written |
| `DB_DIR` | `/app/db` | Where inventory.db is stored |

### Building and pushing to Docker Hub

Use the included `scripts/release.sh` script. It resolves the version from a CLI
argument, git tag, or `VERSION` file; builds and tags the image; pushes both
the versioned tag and `latest`; and verifies the tags exist on Docker Hub.

```bash
# Set your Docker Hub PAT (Read & Write scope)
export DOCKER_HUB_TOKEN=your_token_here

# Push a specific version
./scripts/release.sh 0.6

# Or let the script resolve the version from the latest git tag
./scripts/release.sh
```

See `scripts/docker-push.md` for full details including tag immutability configuration.

### Notes

- The container runs **gunicorn** (2 workers, 120s timeout) rather than
  Flask's built-in dev server
- `config.ini` is mounted read-only and is never baked into the image
- Dev dependencies (`pytest`, `pytest-cov`) are excluded from the image

---

## Licence

This project is for personal use. Contact the repository owner for licensing
enquiries.