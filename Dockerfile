# ── Builder stage — resolve dependencies with pipenv (build tooling only) ────
FROM python:3.14-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir pipenv

COPY Pipfile Pipfile.lock ./

# Install into an isolated prefix so only resolved app deps get copied into
# the final stage, not pipenv itself. --ignore-installed: without it, pip
# skips anything already satisfied by pipenv's own deps (e.g. certifi).
RUN pipenv requirements > requirements.txt \
    && pip install --no-cache-dir --ignore-installed --prefix=/install -r requirements.txt gunicorn


# ── Final stage — runtime only ────────────────────────────────────────────────
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /install /usr/local

# pip vendors its own internal msgpack/setuptools copies that CVE scanners
# flag (no newer pip fixes this). Not needed at runtime, so it's removed —
# pip can uninstall itself, which takes the vendored copies with it.
RUN pip uninstall -y pip

COPY app.py generate_sheets.py set_handler.py bricklink.py brickset.py ./
COPY models.py database.py ./
COPY routes/ routes/
COPY templates/ templates/
COPY VERSION ./
COPY gunicorn.conf.py ./

EXPOSE 5000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
