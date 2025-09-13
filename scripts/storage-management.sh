#!/bin/bash

# Storage Management Script for Pipedrive-Chatwoot Sync
# This script implements best practices for storage and memory management

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
DOCKER_LOG_DIR="/var/lib/docker/containers"
MAX_LOG_SIZE="100M"
MAX_LOG_FILES=10
CLEANUP_DAYS=30

echo "🧹 Storage Management for Pipedrive-Chatwoot Sync"
echo "=================================================="

# Function to check disk usage
check_disk_usage() {
    echo "📊 Current Disk Usage:"
    df -h "$PROJECT_DIR"
    echo ""
    
    echo "📁 Directory Sizes:"
    du -sh "$PROJECT_DIR"/* 2>/dev/null || true
    echo ""
}

# Function to clean up old logs
cleanup_logs() {
    echo "🗑️  Cleaning up old logs..."
    
    # Clean application logs
    if [ -d "$LOG_DIR" ]; then
        find "$LOG_DIR" -name "*.log" -type f -mtime +$CLEANUP_DAYS -delete 2>/dev/null || true
        echo "✅ Cleaned application logs older than $CLEANUP_DAYS days"
    fi
    
    # Clean Docker logs
    if [ -d "$DOCKER_LOG_DIR" ]; then
        find "$DOCKER_LOG_DIR" -name "*.log" -type f -mtime +$CLEANUP_DAYS -delete 2>/dev/null || true
        echo "✅ Cleaned Docker logs older than $CLEANUP_DAYS days"
    fi
    
    # Clean system logs
    sudo journalctl --vacuum-time="${CLEANUP_DAYS}d" 2>/dev/null || true
    echo "✅ Cleaned system logs older than $CLEANUP_DAYS days"
}

# Function to set up log rotation
setup_log_rotation() {
    echo "🔄 Setting up log rotation..."
    
    # Create logrotate configuration
    sudo tee /etc/logrotate.d/pipedrive-chatwoot-sync > /dev/null <<EOF
$PROJECT_DIR/logs/*.log {
    daily
    missingok
    rotate $MAX_LOG_FILES
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
    postrotate
        # Restart sync service if running
        cd $PROJECT_DIR && docker-compose restart sync-app 2>/dev/null || true
    endscript
}
EOF
    
    echo "✅ Log rotation configured"
}

# Function to optimize Docker
optimize_docker() {
    echo "🐳 Optimizing Docker..."
    
    # Clean up unused Docker resources
    docker system prune -f 2>/dev/null || true
    docker volume prune -f 2>/dev/null || true
    docker network prune -f 2>/dev/null || true
    
    echo "✅ Docker cleanup completed"
}

# Function to set up memory limits
setup_memory_limits() {
    echo "💾 Setting up memory limits..."
    
    # Update docker-compose.yml with memory limits
    if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
        # Backup original
        cp "$PROJECT_DIR/docker-compose.yml" "$PROJECT_DIR/docker-compose.yml.backup"
        
        # Add memory limits to services (if not already present)
        if ! grep -q "memory: 512M" "$PROJECT_DIR/docker-compose.yml"; then
            sed -i '/sync-app:/a\    deploy:\n      resources:\n        limits:\n          memory: 512M\n        reservations:\n          memory: 256M' "$PROJECT_DIR/docker-compose.yml"
        fi
        
        echo "✅ Memory limits configured for sync-app (512M limit, 256M reservation)"
    fi
}

# Function to create cleanup cron job
setup_cleanup_cron() {
    echo "⏰ Setting up cleanup cron job..."
    echo "   Note: Use ./scripts/setup-cron.sh for comprehensive cron setup"
    echo "   This function is deprecated in favor of setup-cron.sh"
    echo "✅ Cleanup cron job setup delegated to setup-cron.sh"
}

# Function to monitor storage
monitor_storage() {
    echo "📈 Storage Monitoring:"
    
    # Check if storage is getting full
    USAGE=$(df /home/n8n | tail -1 | awk '{print $5}' | sed 's/%//')
    
    if [ "$USAGE" -gt 80 ]; then
        echo "⚠️  WARNING: Disk usage is at ${USAGE}%"
        echo "   Running emergency cleanup..."
        cleanup_logs
        optimize_docker
    else
        echo "✅ Disk usage is at ${USAGE}% (healthy)"
    fi
}

# Main execution
case "${1:-all}" in
    "check")
        check_disk_usage
        ;;
    "cleanup")
        cleanup_logs
        optimize_docker
        ;;
    "setup")
        setup_log_rotation
        setup_memory_limits
        setup_cleanup_cron
        ;;
    "monitor")
        monitor_storage
        ;;
    "all")
        check_disk_usage
        cleanup_logs
        setup_log_rotation
        setup_memory_limits
        setup_cleanup_cron
        monitor_storage
        ;;
    *)
        echo "Usage: $0 {check|cleanup|setup|monitor|all}"
        echo "  check   - Check current disk usage"
        echo "  cleanup - Clean up old logs and Docker resources"
        echo "  setup   - Set up log rotation and memory limits"
        echo "  monitor - Monitor storage and run cleanup if needed"
        echo "  all     - Run all optimizations (default)"
        exit 1
        ;;
esac

echo ""
echo "✅ Storage management completed!"
