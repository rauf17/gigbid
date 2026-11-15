#!/usr/bin/env bash
set -e

export PYTHONPATH="/app:${PYTHONPATH:-}"
cd /app

echo "[space.boot] Starting PostgreSQL 15 on port 5433..."
mkdir -p /var/run/postgresql
chown -R postgres:postgres /var/run/postgresql
service postgresql start

echo "[space.boot] Waiting for PostgreSQL readiness..."
for i in {1..30}; do
  if pg_isready -h 127.0.0.1 -p 5433 -U postgres >/dev/null 2>&1; then
    echo "[space.boot] PostgreSQL is ready on 5433."
    break
  fi
  sleep 1
done

echo "[space.boot] Provisioning database and credentials..."
su - postgres -c "psql -p 5433 -tc \"SELECT 1 FROM pg_user WHERE usename = 'gigbid'\" | grep -q 1 || psql -p 5433 -c \"CREATE USER gigbid WITH PASSWORD 'gigbid' SUPERUSER;\""
su - postgres -c "psql -p 5433 -tc \"SELECT 1 FROM pg_database WHERE datname = 'gigbid'\" | grep -q 1 || psql -p 5433 -c \"CREATE DATABASE gigbid OWNER gigbid;\""

echo "[space.boot] Starting Redis on port 6380..."
service redis-server start || redis-server --port 6380 --daemonize yes --protected-mode no

echo "[space.boot] Applying database migrations..."
python scripts/migrate_db.py

echo "[space.boot] Seeding REVIEWER user from env ($REVIEWER_EMAIL)..."
python -c "from apps.api.auth.service import seed_reviewer_user; seed_reviewer_user()"

echo "[space.boot] Seeding GigSim marketplace state..."
python gigsim/seed.py

echo "[space.boot] All storage and data initialized. Launching supervisord on port 7860..."
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf
