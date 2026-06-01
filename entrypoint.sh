#!/bin/sh
set -e

echo ">>> Waiting for database..."
python << 'PYEOF'
import time, os, sys
for i in range(30):
    try:
        import psycopg2
        psycopg2.connect(os.environ["DATABASE_URL"])
        print("Database is ready.")
        sys.exit(0)
    except Exception as e:
        print(f"  [{i+1}/30] Not ready: {e}")
        time.sleep(2)
print("ERROR: Database never became ready.")
sys.exit(1)
PYEOF

echo ">>> Running migrations..."
python manage.py migrate --noinput

echo ">>> Collecting static files..."
python manage.py collectstatic --noinput --clear

echo ">>> Starting Daphne..."
exec daphne -b 0.0.0.0 -p 8000 school_project.asgi:application
