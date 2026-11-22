#!/usr/bin/env bash
# Builds a 3-node Citus cluster on one machine: coordinator (port 5440) and two workers (5441, 5442).
# Requires the PGDG build of PostgreSQL 16 and the package postgresql-16-citus-13.2 (see docs/distributed_warehouse.md).
# Also works with PostgreSQL 18 + Citus 14 built from source (see PROJECT_EXPLAINED.md and scripts/run_everything_wsl.sh).
# The PostgreSQL major version is detected; override with PGVER=16 if several are installed.
set -euo pipefail
PGVER="${PGVER:-$(ls /usr/lib/postgresql | sort -V | tail -1)}"
for spec in "coord 5440" "worker1 5441" "worker2 5442"; do
  set -- $spec; name=$1; port=$2
  if ! pg_lsclusters -h | awk '{print $2}' | grep -qx "$name"; then
    pg_createcluster "$PGVER" "$name" -p "$port" -- --auth-local=trust --auth-host=trust >/dev/null
    cat >> "/etc/postgresql/$PGVER/$name/postgresql.conf" <<CONF
shared_preload_libraries = 'citus'
listen_addresses = 'localhost'
shared_buffers = 256MB
max_connections = 200
citus.shard_count = 32
CONF
  fi
  pg_ctlcluster "$PGVER" "$name" start 2>/dev/null || true
done
sleep 4
for port in 5440 5441 5442; do
  su postgres -c "psql -p $port -tAc \"SELECT 1 FROM pg_database WHERE datname='foodsafety_citus'\"" | grep -q 1 || su postgres -c "psql -p $port -c 'CREATE DATABASE foodsafety_citus'"
  su postgres -c "psql -p $port -d foodsafety_citus -c 'CREATE EXTENSION IF NOT EXISTS citus'" >/dev/null
done
su postgres -c "psql -p 5440 -d foodsafety_citus -c \"SELECT citus_set_coordinator_host('localhost', 5440)\"" >/dev/null
for port in 5441 5442; do
  su postgres -c "psql -p 5440 -d foodsafety_citus -tAc \"SELECT count(*) FROM pg_dist_node WHERE nodeport=$port\"" | grep -q '^1$' || \
    su postgres -c "psql -p 5440 -d foodsafety_citus -c \"SELECT citus_add_node('localhost', $port)\""
done
su postgres -c "psql -p 5440 -d foodsafety_citus -c \"SELECT nodeid, nodename, nodeport, noderole, isactive FROM pg_dist_node ORDER BY nodeid\""
