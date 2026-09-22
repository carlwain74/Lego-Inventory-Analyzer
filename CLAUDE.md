# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local Flask web app that fetches Lego set pricing from the Bricklink marketplace API (via `bricklink-py`) and either exports it to XLSX or persists it into a SQLite inventory. Single-page vanilla-JS frontend (`templates/index.html`), no build step.

## Commands

Install deps (Python via Pipenv, JS via npm):
```bash
pipenv install
```

Run the app (serves at http://localhost:5000):
```bash
pipenv run python app.py
```

Run everything (pytest + coverage threshold 90% + Jest), the standard pre-PR check:
```bash
./run_tests.sh
```

Run Python tests only:
```bash
pipenv run pytest tests/ -v
# single test:
pipenv run pytest tests/test_database.py::test_upsert_set -v
# with coverage:
pipenv run pytest tests/ -v --cov=. --cov-config=.coveragerc --cov-report=term-missing --cov-report=html:coverage_html
```

Run JS tests only (Jest, lives under `test_ui/`, driven from repo root by `run_tests.sh` but must be run from that dir directly otherwise):
```bash
cd test_ui && npm install && npm test
```

Config setup (required before hitting any Bricklink-backed route):
```bash
cp config.ini.template config.ini   # then fill in Bricklink API credentials, or use the in-app settings dialog
```

Docker:
```bash
docker compose up            # config.ini must exist first, bind-mounted read-only
./scripts/release.sh [ver]   # build/tag/push to Docker Hub; resolves version from arg, git tag, or VERSION file
```

## Architecture

**Two independent data paths share the same Bricklink fetch code but diverge after that:**

1. **Check Prices** (`POST /generate` in `app.py`) — stateless. Builds a `SetHandler`, calls `set_handler()`, returns the raw dict straight to the frontend. Nothing touches the database. Also drives `generate_sheets.py` to produce `Sets.xlsx` for `/download`.
2. **Import / Inventory** (`routes/import_routes.py`, `routes/inventory.py`) — persists to SQLite via `database.py`. `_fetch_set()` in `import_routes.py` wraps the same `SetHandler` call, but results are cached: `is_price_stale()` checks `PRICE_TTL_HOURS` (env var, default 24) against `Set.last_fetched` before deciding whether to re-hit the Bricklink API or reuse the existing row.

**Fetch chain:** `SetHandler` (`set_handler.py`) orchestrates → `BrickLinkAPI` (`bricklink.py`) wraps `bricklink_py.Bricklink` and makes four sequential calls per set (`getSetInfo`, `getSetCatalogInfo`, `getSetPastSales`, `getSetCurrentSales`), accumulating results in `self.sets[set_number]`. A set literal `"40158"` is special-cased to `item_type = "GEAR"` instead of `"SET"` — Bricklink has no other way to distinguish gear from sets by number alone. After the Bricklink calls complete, `SetHandler._attach_retail_prices()` calls `BrickSetAPI` (`brickset.py`, wraps the `brickse` library) once per set to add the official LEGO.com US retail price (`retail_price_usd`, a float or `None`) to each set's dict — a lookup failure here is logged and never aborts the Bricklink result.

**BrickSet config:** the `[bricklink]` section of `config.ini` (despite the name, shared with the Bricklink `[secrets]` section by historical accident) holds `api_key` for the BrickSet API. `BrickSetAPI.__init__` reads it once; if absent, `get_retail_price_usd()` returns `None` without attempting a request. The `brickse` package is imported lazily inside `get_retail_price_usd()` (not at module load) so tests and any environment missing the dependency degrade gracefully instead of failing to import.

**Data model** (`models.py`): `Set` (metadata cache, one row per set number, unique) → `SetPrice` (append-only price snapshots, newest is `set.latest_price`) → `Inventory` (owned quantity, one row per set, incremented on re-import, decremented/deleted via `decrement_inventory`). `database.py` centralizes all session handling (`get_session()` context manager commits/rolls back) and upsert logic — routes never touch SQLAlchemy sessions directly beyond calling these helpers. `set_to_dict()` is the single place that serializes a `Set` + its latest `SetPrice` into the JSON shape the frontend expects (same shape both `/generate` and inventory routes return).

**Bulk import** (`POST /inventory/import/bulk`) streams progress via Server-Sent Events (`text/event-stream`), one JSON event per imported set plus a final `{"done": true, ...}` event — see `_sse()` in `import_routes.py`. The frontend's SSE consumer logic is what `test_ui/test_ui.js` covers.

**Config handling:** `config.ini` (gitignored) holds Bricklink OAuth1 credentials under a `[secrets]` section, read fresh by `BrickLinkAPI.__init__` on every `SetHandler` construction — there's no long-lived API client. `/settings/test` writes credentials to a temp version of `config.ini`, tests the connection, then unconditionally restores the original content/absence in a `finally` block — don't remove that restore-on-exit invariant.

**Env-driven paths:** `OUTPUT_DIR` and `DB_DIR` (both default to the project root, overridden in Docker to point at named volumes) control where `Sets.xlsx` and `inventory.db` land. `CONFIG_PATH` and `OUTPUT_DIR` are also pushed into `os.environ` by `app.py` at startup so route modules (which import `SetHandler` lazily, inside the handler function, to avoid circular imports) can read them.

## Testing conventions

- `.coveragerc` omits `tests/`, `test_ui/`, `generate_sheets.py`, `inventory*.py`, and `bricklink_py*` from coverage — new modules following that naming won't be tracked unless the config is updated.
- Coverage gate is 90% locally (`run_tests.sh`) but only 80% in CI (`.github/workflows/main.yml`, `sub-python.yml`) — treat 90% as the real bar.
- New Flask routes need tests in `tests/test_app.py` or `tests/test_inventory_routes.py`; new frontend JS functions need tests in `test_ui/test_ui.js`.
- `tests/conftest.py` stubs external modules — check it before assuming a real Bricklink API call happens in tests.
