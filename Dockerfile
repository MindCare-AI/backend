FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Create a non-root user for security
RUN groupadd -r django && useradd -r -g django django

# Set up the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project files with correct permissions
COPY --chown=django:django . /app/

# Collect static files (only in production)
RUN if [ "$DJANGO_ENV" = "production" ]; then python manage.py collectstatic --noinput; fi

# Change to non-root user
USER django

# Expose the port the app runs on
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health/ || exit 1

# Run the application
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]

# For production, uncomment the following line and comment the CMD above
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "mindcare.wsgi:application"]
