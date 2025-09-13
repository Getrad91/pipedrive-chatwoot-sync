#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/auto-sync.log"

mkdir -p "$PROJECT_DIR/logs"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting auto sync" >> "$LOG_FILE"

if ! command -v docker-compose &> /dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - WARNING: docker-compose not found, skipping sync" >> "$LOG_FILE"
    exit 0
fi

cd "$PROJECT_DIR"
if ./scripts/manage.sh sync >> "$LOG_FILE" 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Auto sync completed successfully" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Auto sync failed with exit code $?" >> "$LOG_FILE"
    exit 1
fi
