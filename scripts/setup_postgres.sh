#!/usr/bin/env bash
# Start PostgreSQL 16 (Ubuntu package) and create the project role and database.
set -e
pg_ctlcluster 16 main start 2>/dev/null || true
su postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='foodsafety'\"" | grep -q 1 || \
  su postgres -c "psql -c \"CREATE ROLE foodsafety LOGIN PASSWORD 'foodsafety' SUPERUSER;\""
su postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='foodsafety'\"" | grep -q 1 || \
  su postgres -c "psql -c \"CREATE DATABASE foodsafety OWNER foodsafety;\""
echo "PostgreSQL ready: postgresql://foodsafety:foodsafety@localhost:5432/foodsafety"
