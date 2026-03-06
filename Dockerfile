FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Copy dependency files first so Docker can cache the install layer
COPY Pipfile Pipfile.lock ./

# Install only production dependencies (no dev tools in the image)
# If Pipfile.lock exists, use --deploy for reproducible installs.
# Otherwise fall back to installing from Pipfile directly.
RUN pipenv install --system --ignore-pipfile 2>/dev/null || pipenv install --system

# Copy application source
COPY app.py generate_sheets.py last_sale_date.py ./
COPY templates/ templates/

# Expose Flask port
EXPOSE 5000

# Use gunicorn in production instead of Flask's dev server
# Install gunicorn as part of the image (not in Pipfile to keep it Docker-specific)
RUN pip install --no-cache-dir gunicorn

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
