#!/bin/bash

# Data Migration Script
# This script helps migrate your existing n8n_chatwoot database to pipedrive_chatwoot_sync

set -e

echo "🔄 Pipedrive to Chatwoot Data Migration Script"
echo "=============================================="

# Check if MySQL is running
if ! docker-compose ps mysql | grep -q "Up"; then
    echo "❌ MySQL container is not running. Please start it first:"
    echo "   docker-compose up -d mysql"
    exit 1
fi

echo "📊 Current database status:"
echo ""

# Show current data in n8n_chatwoot
echo "Current data in n8n_chatwoot database:"
docker-compose exec mysql mysql -u root -proot_password_2024 -e "
USE n8n_chatwoot;
SELECT 'Organizations' as table_name, COUNT(*) as count FROM organizations
UNION ALL
SELECT 'Persons' as table_name, COUNT(*) as count FROM persons  
UNION ALL
SELECT 'Contacts' as table_name, COUNT(*) as count FROM contacts;
"

echo ""
echo "🔄 Starting migration to pipedrive_chatwoot_sync database..."
echo ""

# Create the new database and tables
echo "1. Creating pipedrive_chatwoot_sync database and tables..."
docker-compose exec mysql mysql -u root -proot_password_2024 < /docker-entrypoint-initdb.d/init.sql

# Migrate data
echo "2. Migrating organizations..."
docker-compose exec mysql mysql -u root -proot_password_2024 -e "
INSERT INTO pipedrive_chatwoot_sync.organizations 
SELECT * FROM n8n_chatwoot.organizations
ON DUPLICATE KEY UPDATE
  name=VALUES(name),
  phone=VALUES(phone),
  support_link=VALUES(support_link),
  city=VALUES(city),
  country=VALUES(country),
  email=VALUES(email),
  status=VALUES(status),
  data=VALUES(data),
  notes=VALUES(notes),
  deal_title=VALUES(deal_title),
  owner_name=VALUES(owner_name),
  synced_to_chatwoot=0,
  updated_at=CURRENT_TIMESTAMP;
"

echo "3. Migrating persons..."
docker-compose exec mysql mysql -u root -proot_password_2024 -e "
INSERT INTO pipedrive_chatwoot_sync.persons 
SELECT * FROM n8n_chatwoot.persons
ON DUPLICATE KEY UPDATE
  name=VALUES(name),
  phone=VALUES(phone),
  email=VALUES(email),
  org_id=VALUES(org_id),
  status=VALUES(status),
  data=VALUES(data),
  synced_to_chatwoot=0,
  updated_at=CURRENT_TIMESTAMP;
"

echo "4. Migrating contacts..."
docker-compose exec mysql mysql -u root -proot_password_2024 -e "
INSERT INTO pipedrive_chatwoot_sync.contacts 
SELECT * FROM n8n_chatwoot.contacts
ON DUPLICATE KEY UPDATE
  org_id=VALUES(org_id),
  name=VALUES(name),
  phone=VALUES(phone),
  email=VALUES(email),
  role=VALUES(role),
  status=VALUES(status),
  data=VALUES(data),
  synced_to_chatwoot=0,
  updated_at=CURRENT_TIMESTAMP;
"

echo ""
echo "✅ Migration completed!"
echo ""

# Show final status
echo "📊 Final data in pipedrive_chatwoot_sync database:"
docker-compose exec mysql mysql -u root -proot_password_2024 -e "
USE pipedrive_chatwoot_sync;
SELECT 'Organizations' as table_name, COUNT(*) as count FROM organizations
UNION ALL
SELECT 'Persons' as table_name, COUNT(*) as count FROM persons  
UNION ALL
SELECT 'Contacts' as table_name, COUNT(*) as count FROM contacts
UNION ALL
SELECT 'Sync Log' as table_name, COUNT(*) as count FROM sync_log;
"

echo ""
echo "🎉 Migration Summary:"
echo "  - All your existing data has been copied to pipedrive_chatwoot_sync"
echo "  - All records are marked as unsynced (synced_to_chatwoot=0)"
echo "  - The sync application is ready to use"
echo ""
echo "Next steps:"
echo "  1. Set up your API keys in .env file"
echo "  2. Run: ./scripts/manage.sh start"
echo "  3. Run: ./scripts/manage.sh sync"

