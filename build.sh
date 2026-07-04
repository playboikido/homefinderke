#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files (needed for favicon and django admin CSS)
python manage.py collectstatic --noinput

# Run migrations (applies tables and setup data migrations to Neon)
python manage.py migrate
