#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"

echo "🔍 Cron Job Health Monitor"
echo "=========================="
echo "Timestamp: $(date)"
echo ""

if [ ! -d "$LOG_DIR" ]; then
    echo "❌ Logs directory not found: $LOG_DIR"
    exit 1
fi

echo "📊 Recent Log Activity:"
for log_file in auto-sync.log storage-cleanup.log storage-monitor.log backup.log inbox-assignment.log common-support-sync.log; do
    log_path="$LOG_DIR/$log_file"
    if [ -f "$log_path" ]; then
        last_modified=$(stat -c %Y "$log_path" 2>/dev/null || echo "0")
        current_time=$(date +%s)
        age=$((current_time - last_modified))
        
        if [ $age -lt 3600 ]; then
            echo "  ✅ $log_file - Updated $(($age/60)) minutes ago"
        elif [ $age -lt 86400 ]; then
            echo "  ⚠️  $log_file - Updated $(($age/3600)) hours ago"
        else
            echo "  ❌ $log_file - Updated $(($age/86400)) days ago"
        fi
    else
        echo "  ❓ $log_file - Not found"
    fi
done

echo ""
echo "💾 Disk Usage:"
df -h "$PROJECT_DIR" | tail -1

echo ""
echo "🕐 Current Crontab:"
if command -v crontab &> /dev/null; then
    crontab -l | grep -A 20 "Pipedrive Chatwoot Sync" || echo "No cron jobs found"
else
    echo "⚠️  crontab command not available"
    if [ -f "$PROJECT_DIR/crontab.txt" ]; then
        echo "📄 Saved cron configuration:"
        grep -A 20 "Pipedrive Chatwoot Sync" "$PROJECT_DIR/crontab.txt" || echo "No cron jobs found in saved config"
    fi
fi
