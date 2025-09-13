#!/bin/bash

# Pipedrive to Chatwoot Sync Setup Script
# This script sets up the complete sync environment

set -e

echo "🚀 Setting up Pipedrive to Chatwoot Sync Environment"
echo "=================================================="

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p mysql/data
chmod 755 logs
chmod 755 mysql/data

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp env.example .env
    echo "📝 Please edit .env file with your API keys before continuing."
    echo "   - PIPEDRIVE_API_KEY: Get from https://yourcompany.pipedrive.com/settings/api"
    echo "   - CHATWOOT_API_KEY: Get from https://support.liveport.com.au/app/accounts/2/settings/integrations/api"
    echo ""
    read -p "Press Enter after you've updated the .env file..."
fi

# Validate .env file
echo "🔍 Validating configuration..."
source .env

if [ -z "$PIPEDRIVE_API_KEY" ] || [ "$PIPEDRIVE_API_KEY" = "your_pipedrive_api_token_here" ]; then
    echo "❌ PIPEDRIVE_API_KEY is not set in .env file"
    exit 1
fi

if [ -z "$CHATWOOT_API_KEY" ] || [ "$CHATWOOT_API_KEY" = "your_chatwoot_api_token_here" ]; then
    echo "❌ CHATWOOT_API_KEY is not set in .env file"
    exit 1
fi

echo "✅ Configuration validated"

# Build and start services
echo "🐳 Building and starting Docker services..."
docker-compose down --remove-orphans
docker-compose build --no-cache
docker-compose up -d

# Wait for MySQL to be ready
echo "⏳ Waiting for MySQL to be ready..."
timeout=60
counter=0
while ! docker-compose exec mysql mysqladmin ping -h localhost --silent; do
    if [ $counter -eq $timeout ]; then
        echo "❌ MySQL failed to start within $timeout seconds"
        exit 1
    fi
    echo "   Waiting for MySQL... ($counter/$timeout)"
    sleep 2
    counter=$((counter + 2))
done

echo "✅ MySQL is ready"

# Run initial sync
echo "🔄 Running initial sync..."
docker-compose exec sync-app python sync.py

echo ""
echo "🎉 Setup complete!"
echo "=================="
echo ""
echo "Services running:"
echo "  - MySQL Database: localhost:3306"
echo "  - phpMyAdmin: http://localhost:8080"
echo "  - Sync Application: Running in background"
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose logs -f sync-app"
echo "  - Run manual sync: docker-compose exec sync-app python sync.py"
echo "  - Stop services: docker-compose down"
echo "  - Restart services: docker-compose restart"
echo ""
echo "Database connection details:"
echo "  Host: localhost"
echo "  Port: 3306"
echo "  Database: pipedrive_chatwoot_sync"
echo "  Username: sync_user"
echo "  Password: $MYSQL_PASSWORD"

