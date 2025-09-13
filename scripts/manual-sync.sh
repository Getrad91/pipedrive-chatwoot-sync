#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/manual-sync.log"

mkdir -p "$PROJECT_DIR/logs"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting manual sync" >> "$LOG_FILE"

if ! command -v docker-compose &> /dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - WARNING: docker-compose not found, skipping sync" | tee -a "$LOG_FILE"
    exit 0
fi

cd "$PROJECT_DIR"
if ./scripts/manage.sh sync | tee -a "$LOG_FILE"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Manual sync completed successfully" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Manual sync failed with exit code $?" >> "$LOG_FILE"
    exit 1
fi
