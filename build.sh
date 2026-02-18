#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

echo "Running database migrations..."
alembic upgrade head

echo "Build complete!"
