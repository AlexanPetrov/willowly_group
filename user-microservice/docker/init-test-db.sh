#!/bin/bash
set -e

# Create test database if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE user_microservice_test_db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'user_microservice_test_db')\gexec
EOSQL

echo "Test database 'user_microservice_test_db' created or already exists"
