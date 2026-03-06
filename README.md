# 🧱 Lego Inventory — Set Price Analyzer

A local web application for analysing Bricklink marketplace pricing data across Lego sets. Given a set number or a list of sets, it queries the Bricklink API and presents current and historical sale data in a clean, filterable card interface.

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

Lego Inventory connects to the [Bricklink](https://www.bricklink.com) marketplace API to retrieve pricing data for one or more Lego sets and renders it as an interactive dashboard.

### Key features

- **Single set lookup** — enter a set number (e.g. `75192-1`) and instantly retrieve pricing
- **Batch processing** — upload a `.txt` or `.list` file containing multiple set numbers to analyse them all at once
- **Current & past sales** — each set card displays separate pricing rows for items currently for sale and historical sold listings
- **Sale value estimate** — a calculated recommended sale price derived from the average of the current avg and max prices
- **Category filtering** — filter a batch result set by category with live chip-based controls
- **Thumbnail previews** — hover over a set image to see a full-size popup
- **API settings dialog** — manage Bricklink OAuth credentials through a built-in settings panel without touching config files manually
- **XLSX export** — download the full results as a formatted spreadsheet

### Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · Flask · bricklink-py · openpyxl |
| Frontend | Vanilla JS · CSS custom properties · HTML5 |
| Testing (Python) | pytest · pytest-cov |
| Testing (JS) | Jest · jest-environment-jsdom |
| Dependency management | Pipenv (Python) · npm (JS) |

---

## Project Structure

```
.
├── app.py                  # Flask application and API routes
├── generate_sheets.py      # Bricklink API integration, sheet generation and sale date utility
├── config.ini.template     # Credentials template (committed)
├── config.ini              # Bricklink API credentials (not committed to git)
├── Pipfile                 # Python dependencies
├── Pipfile.lock
├── .coveragerc             # Coverage configuration
├── run_tests.sh            # Wrapper script to run all test suites
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Docker Compose service configuration
├── .dockerignore           # Files excluded from the Docker build context
├── templates/
│   └── index.html          # Single-page frontend
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # pytest shared fixtures and stubs
│   └── test_app.py         # pytest suite for Flask routes
└── test_ui/
    ├── package.json        # JS test dependencies (Jest)
    └── test_ui.js          # Jest suite for frontend JS functions
```

---

## Prerequisites

- **Python 3.11+**
- **Pipenv** — `pip install pipenv`
- **Node.js 18+** and **npm** — [nodejs.org](https://nodejs.org)
- A Bricklink account with API credentials ([register here](https://www.bricklink.com/v3/api.page))

---

## How to Run

### 1. Install Python dependencies

```bash
pipenv install
```

### 2. Configure Bricklink API credentials

Copy the provided template and fill in your credentials:

```bash
cp config.ini.template config.ini
```

Then open `config.ini` and fill in your credentials, or use the in-app settings dialog (see [Configuration](#configuration)).

### 3. Start the server

```bash
pipenv run python app.py
```

The app will be available at **http://localhost:5000**.

### 4. Use the app

- **Single set** — select *Set Number*, type a set number (the `-1` suffix is added automatically), and click *Generate*
- **Batch** — select *Set List File*, upload a `.txt` or `.list` file with one set number per line, and click *Generate*
- **Export** — after a batch run, click *⬇ Download Sets.xlsx* in the summary bar

### 5. Run backend direct

There are two modes; Printing details about a single set `-s` or multiple sets `-f`.

Single set option will take presedence over multiple sets

```
usage: app.py [-h] [-s SET] [-f FILE] [-m MULTI] [-v] [-o OUTPUT]

options:
  -h, --help            show this help message and exit
  -s SET, --set SET
  -f FILE, --file FILE
  -m MULTI, --multi MULTI
  -v, --verbose
  -o OUTPUT, --output OUTPUT
```
#### Single set

```
pipenv run python inventory.py -s 40158
2021-11-11 19:16:48 INFO     Item: 40158
2021-11-11 19:16:48 INFO       Name: Pirates Chess Set, Pirates III
2021-11-11 19:16:48 INFO       Category: Game
2021-11-11 19:16:48 INFO       Avg Price: 102 USD
2021-11-11 19:16:48 INFO       Max Price: 150 USD
2021-11-11 19:16:48 INFO       Min Price: 84 USD
2021-11-11 19:16:48 INFO       Quantity avail: 16
```

#### Multiple Sets

You need to create a text file with a list of sets as follows. Script will generate a default file `Sets.xlsx` with a single sheet with all sets it was able to process
```
21036-1
41585-1
```
Then include the filename instead of a set.
```
pipenv run python inventory.py -f test.txt
2021-11-11 19:18:42 INFO     Processing sets in test.txt
2021-11-11 19:18:44 INFO     Item: 21036-1
2021-11-11 19:18:44 INFO       Name: Arc De Triomphe
2021-11-11 19:18:44 INFO       Category: Architecture
2021-11-11 19:18:44 INFO       Avg Price: 91 USD
2021-11-11 19:18:44 INFO       Max Price: 99 USD
2021-11-11 19:18:44 INFO       Min Price: 75 USD
2021-11-11 19:18:44 INFO       Quantity avail: 17
2021-11-11 19:18:45 INFO     Item: 41585-1
2021-11-11 19:18:45 INFO       Name: Batman
2021-11-11 19:18:45 INFO       Category: BrickHeadz
2021-11-11 19:18:45 INFO       Avg Price: 45 USD
2021-11-11 19:18:45 INFO       Max Price: 65 USD
2021-11-11 19:18:45 INFO       Min Price: 34 USD
2021-11-11 19:18:45 INFO       Quantity avail: 13
2021-11-11 19:18:45 INFO     Total: 136USD
```

---

## Configuration

Bricklink API credentials are stored in `config.ini` in the project root. They can be updated at any time without restarting the server using the in-app settings panel:

1. Click the **⚙ cogwheel** icon next to the *Configure* heading in the sidebar
2. Enter new values for any of the four credential fields
3. Use **Test Connection** to verify credentials before saving
4. Click **Save Settings** — changes take effect immediately

> **Security note:** `config.ini` contains sensitive credentials and should never be committed to version control. Ensure it is listed in `.gitignore`.

```gitignore
config.ini
```

---

## Local Network Access

The app binds to `0.0.0.0:5000` by default, making it reachable from other devices on your local network via your machine's IP address (e.g. `http://192.168.1.42:5000`).

To access it via a friendly hostname (e.g. `http://legoinventory.local`) across your LAN, see the included setup guides:

- **`dnsmasq-setup.md`** — recommended: runs a lightweight DNS server on your Mac, no per-device config needed
- **`caddy-setup.md`** — alternative: reverse proxy to remove the port number from the URL (requires a newer macOS)

---

## How to Test

### Run all test suites

A single wrapper script runs both the Python and JavaScript suites, syncs dependencies first, and reports a coverage summary:

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
pipenv sync --dev
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
cd test_ui
npm install
npm test
```

### What is tested

| Suite | File | Coverage |
|---|---|---|
| Flask routes (`/`, `/generate`, `/settings`, `/settings/test`, `/download`) | `tests/test_app.py` | 48 tests |
| `capture_output` logging capture | `tests/test_app.py` | 5 tests |
| JS parser (`parseAllSets`) | `test_ui/test_ui.js` | 28 tests |
| JS helpers (`formatPrice`, `formatSaleDate`, `calcSaleValue`, `esc`) | `test_ui/test_ui.js` | 30 tests |

---

## How to Contribute

Contributions are welcome. Please follow the process below to keep the codebase consistent and the review process smooth.

### 1. Fork and clone

```bash
git clone https://github.com/YOUR_USERNAME/bricklink.git
cd bricklink
```

### 2. Create a feature branch

Branch names should be short and descriptive, prefixed by type:

```bash
git checkout -b feature/my-new-feature
# or
git checkout -b fix/bug-description
# or
git checkout -b chore/update-dependencies
```

### 3. Make your changes

- Keep changes focused — one feature or fix per PR
- Follow the existing code style (no external linters are enforced, but consistency matters)
- If adding a new Flask route, add corresponding tests in `tests/test_app.py`
- If adding or modifying a JS function in `index.html`, add corresponding tests in `test_ui/test_ui.js`
- Do not commit `config.ini`, `coverage_html/`, `__pycache__/`, or `node_modules/`

### 4. Run the test suite

All tests must pass and coverage must remain at or above **90%** before submitting:

```bash
./run_tests.sh
```

### 5. Commit your changes

Write clear, imperative commit messages:

```bash
git add .
git commit -m "Add last sale date to past sales card"
```

### 6. Push and open a Pull Request

```bash
git push origin feature/my-new-feature
```

Then open a Pull Request against the `main` branch on GitHub. In the PR description include:

- **What** the change does
- **Why** it's needed
- Any **screenshots** if the change affects the UI
- Confirmation that `./run_tests.sh` passes

### 7. Code review

PRs require at least one approving review before merging. Address any feedback with additional commits on the same branch — do not force-push after a review has started.

---

## Docker

The app can be run in a container using Docker Compose. The container will automatically restart if the app crashes (`restart: on-failure`).

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)

### 1. Create a config.ini

The container expects `config.ini` to exist in the project root before starting — it is mounted as a volume rather than baked into the image so credentials are never embedded in the image layer.

Copy the template and fill in your credentials:

```bash
cp config.ini.template config.ini
```

### 2. Build and start

```bash
docker compose up --build
```

The app will be available at **http://localhost:5000**.

To run in the background:

```bash
docker compose up --build -d
```

### 3. Stop the container

```bash
docker compose down
```

### Generated files

`Sets.xlsx` is written to an `output/` directory that is mounted as a volume, so generated files persist between container restarts and are accessible on your host machine.

### Rebuilding after code changes

```bash
docker compose up --build
```

Docker will only rebuild layers that have changed. Dependency installation is cached as a separate layer so it is only re-run when `Pipfile` or `Pipfile.lock` changes.

### Notes

- The container runs **gunicorn** (2 workers, 120s timeout) rather than Flask's built-in dev server for better stability
- `config.ini` and `output/` are mounted as volumes and are never baked into the image
- Dev dependencies (`pytest`, `pytest-cov`) are excluded from the image — only production packages are installed


---

## Licence

This project is for personal use. Contact the repository owner for licensing enquiries.