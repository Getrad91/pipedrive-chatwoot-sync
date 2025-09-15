#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🕐 Setting up cron jobs for Pipedrive Chatwoot sync"
echo "=================================================="
echo "Project directory: $PROJECT_DIR"
echo ""

mkdir -p "$PROJECT_DIR/logs"

TEMP_CRON=$(mktemp)

crontab -l 2>/dev/null > "$TEMP_CRON" || true

sed -i '/pipedrive-chatwoot-sync/d' "$TEMP_CRON"

cat >> "$TEMP_CRON" << EOF

0 8-17 * * 1-5 cd $PROJECT_DIR && ./scripts/auto-sync.sh

0 2 * * * cd $PROJECT_DIR && ./scripts/storage-management.sh cleanup >> $PROJECT_DIR/logs/storage-cleanup.log 2>&1

0 */4 * * * cd $PROJECT_DIR && ./scripts/storage-management.sh monitor >> $PROJECT_DIR/logs/storage-monitor.log 2>&1

0 3 * * * cd $PROJECT_DIR && ./scripts/manage.sh backup >> $PROJECT_DIR/logs/backup.log 2>&1

0 1 * * 0 cd $PROJECT_DIR && python3 assign_contacts_to_support_inbox.py >> $PROJECT_DIR/logs/inbox-assignment.log 2>&1
0 1 * * 0 cd $PROJECT_DIR && python3 sync_common_support.py >> $PROJECT_DIR/logs/common-support-sync.log 2>&1

EOF

if command -v crontab &> /dev/null; then
    crontab "$TEMP_CRON"
    echo "✅ Cron jobs installed successfully!"
else
    echo "⚠️  crontab command not found. Saving cron configuration to crontab.txt"
    cp "$TEMP_CRON" "$PROJECT_DIR/crontab.txt"
    echo "📄 Cron configuration saved to: $PROJECT_DIR/crontab.txt"
    echo "   To install manually: crontab $PROJECT_DIR/crontab.txt"
fi

rm "$TEMP_CRON"
echo ""
echo "📋 Scheduled jobs:"
echo "  - Main sync: Every hour (8am-5pm, weekdays)"
echo "  - Storage cleanup: Daily at 2 AM"
echo "  - Storage monitoring: Every 4 hours"
echo "  - Database backup: Daily at 3 AM"
echo "  - Inbox assignment: Weekly on Sundays at 1 AM"
echo "  - Common support sync: Weekly on Sundays at 1 AM"
echo ""
echo "📁 Log files will be created in: $PROJECT_DIR/logs/"
echo ""
echo "🔍 View current crontab: crontab -l"
echo "📊 Monitor logs: tail -f $PROJECT_DIR/logs/auto-sync.log"
