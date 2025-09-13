#!/bin/bash

# Pipedrive to Chatwoot Sync Management Script
# Provides easy commands to manage the sync environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Function to show usage
show_usage() {
    echo "Pipedrive to Chatwoot Sync Management"
    echo "====================================="
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start       Start all services"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  status      Show service status"
    echo "  logs        Show application logs"
    echo "  sync        Run manual sync"
    echo "  db          Open MySQL shell"
    echo "  backup      Backup database"
    echo "  restore     Restore database from backup"
    echo "  clean       Clean up containers and volumes"
    echo "  update      Update and rebuild containers"
    echo "  help        Show this help message"
    echo ""
}

# Function to check if services are running
check_services() {
    if ! docker-compose ps | grep -q "Up"; then
        print_warning "Services are not running. Use '$0 start' to start them."
        return 1
    fi
    return 0
}

# Function to start services
start_services() {
    print_header "Starting Pipedrive to Chatwoot Sync Services"
    docker-compose up -d
    print_status "Services started successfully"
}

# Function to stop services
stop_services() {
    print_header "Stopping Pipedrive to Chatwoot Sync Services"
    docker-compose down
    print_status "Services stopped successfully"
}

# Function to restart services
restart_services() {
    print_header "Restarting Pipedrive to Chatwoot Sync Services"
    docker-compose restart
    print_status "Services restarted successfully"
}

# Function to show service status
show_status() {
    print_header "Service Status"
    docker-compose ps
    echo ""
    print_header "Resource Usage"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
}

# Function to show logs
show_logs() {
    if ! check_services; then
        exit 1
    fi
    
    print_header "Application Logs (Press Ctrl+C to exit)"
    docker-compose logs -f sync-app
}

# Function to run manual sync
run_sync() {
    if ! check_services; then
        exit 1
    fi
    
    print_header "Running Manual Sync"
    docker-compose exec sync-app python sync.py
    print_status "Sync completed"
}

# Function to open MySQL shell
open_db_shell() {
    if ! check_services; then
        exit 1
    fi
    
    print_header "Opening MySQL Shell"
    docker-compose exec mysql mysql -u sync_user -p$MYSQL_PASSWORD pipedrive_chatwoot_sync
}

# Function to backup database
backup_database() {
    if ! check_services; then
        exit 1
    fi
    
    backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
    print_header "Creating Database Backup: $backup_file"
    
    docker-compose exec mysql mysqldump -u sync_user -p$MYSQL_PASSWORD pipedrive_chatwoot_sync > "backups/$backup_file"
    
    if [ $? -eq 0 ]; then
        print_status "Backup created successfully: backups/$backup_file"
    else
        print_error "Backup failed"
        exit 1
    fi
}

# Function to restore database
restore_database() {
    if [ -z "$2" ]; then
        print_error "Please specify backup file: $0 restore <backup_file>"
        exit 1
    fi
    
    backup_file="$2"
    if [ ! -f "backups/$backup_file" ]; then
        print_error "Backup file not found: backups/$backup_file"
        exit 1
    fi
    
    if ! check_services; then
        exit 1
    fi
    
    print_warning "This will replace all data in the database. Are you sure? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_status "Restore cancelled"
        exit 0
    fi
    
    print_header "Restoring Database from: $backup_file"
    docker-compose exec -T mysql mysql -u sync_user -p$MYSQL_PASSWORD pipedrive_chatwoot_sync < "backups/$backup_file"
    
    if [ $? -eq 0 ]; then
        print_status "Database restored successfully"
    else
        print_error "Restore failed"
        exit 1
    fi
}

# Function to clean up
clean_up() {
    print_warning "This will remove all containers, volumes, and data. Are you sure? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_status "Cleanup cancelled"
        exit 0
    fi
    
    print_header "Cleaning up containers and volumes"
    docker-compose down -v --remove-orphans
    docker system prune -f
    print_status "Cleanup completed"
}

# Function to update containers
update_containers() {
    print_header "Updating and rebuilding containers"
    docker-compose pull
    docker-compose build --no-cache
    docker-compose up -d
    print_status "Containers updated successfully"
}

# Main script logic
case "${1:-help}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    sync)
        run_sync
        ;;
    db)
        open_db_shell
        ;;
    backup)
        mkdir -p backups
        backup_database
        ;;
    restore)
        restore_database "$@"
        ;;
    clean)
        clean_up
        ;;
    update)
        update_containers
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac

