#!/usr/bin/env bash
# Render/Railway build step: install, collect static, migrate, sync bucket CORS.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py configure_bucket_cors
