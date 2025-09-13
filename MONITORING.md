# Monitoring and Alerting Setup

This document explains how to set up and use the monitoring and alerting system for the Pipedrive to Chatwoot sync process.

## Overview

The monitoring system provides:
- **Health Checks**: Validates API connectivity and data consistency
- **Google Chat Alerts**: Structured notifications for critical issues
- **Structured Logging**: JSON-formatted logs with rotation
- **Error Detection**: Identifies sync failures, API issues, and data mismatches

## Google Chat Integration Setup

### Step 1: Create Google Chat Webhook

1. Open Google Chat in your browser
2. Go to the space where you want to receive alerts
3. Click the space name → **Apps & integrations**
4. Click **Add webhooks**
5. Enter a name like "Pipedrive-Chatwoot Sync Alerts"
6. Click **Save**
7. Copy the webhook URL

### Step 2: Configure Environment Variables

Add the webhook URL to your `.env` file:

```bash
# Google Chat webhook URL for alerts
SUPPORT_GOOGLE_CHAT=https://chat.googleapis.com/v1/spaces/YOUR_SPACE_ID/messages?key=YOUR_KEY&token=YOUR_TOKEN

# Monitoring thresholds (optional - defaults shown)
MONITOR_INTERVAL_MINUTES=30
ALERT_ERROR_THRESHOLD=10
MAX_SYNC_AGE_HOURS=2
```

### Step 3: Test the Integration

```bash
# Test Google Chat notifications
./scripts/manage.sh test-alerts
```

## Monitoring Checks

The monitoring system performs these health checks:

### 1. API Connectivity
- **Pipedrive API**: Validates authentication and fetches Customer organizations count
- **Chatwoot API**: Validates authentication and fetches contact count
- **Alerts on**: Authentication failures, server errors, network issues

### 2. Database Sync Status
- **Unsynced Records**: Organizations not yet synced to Chatwoot
- **Stale Records**: Organizations unsynced for over `MAX_SYNC_AGE_HOURS`
- **Error Rate**: Percentage of failed sync operations in last 24 hours
- **Consecutive Errors**: Multiple sync failures in sequence

### 3. Data Consistency
- **Count Discrepancies**: Large differences between Pipedrive and database counts
- **Sync Rate**: Percentage of database records successfully synced to Chatwoot
- **Alerts on**: >10% discrepancy or <90% sync rate

## Alert Structure

All alerts include structured information:

```json
{
  "timestamp": "2024-01-15 10:30:00 UTC",
  "script": "sync|cleanup|monitor",
  "level": "ERROR|WARNING|INFO",
  "error_type": "API failure|auth issue|data mismatch|high error rate|system error",
  "message": "Human-readable description",
  "details": {
    "affected_count": 25,
    "error_rate": "15.2%",
    "api": "Pipedrive|Chatwoot"
  }
}
```

## Alert Types

### Critical Errors (🚨)
- API authentication failures
- Database connection failures
- System crashes or exceptions

### Warnings (⚠️)
- High error rates (>10%)
- Data consistency issues
- Stale sync records

### Info (ℹ️)
- Test notifications
- System status updates

## Management Commands

```bash
# Run health check manually
./scripts/manage.sh monitor

# Test Google Chat notifications
./scripts/manage.sh test-alerts

# View monitoring logs
./scripts/manage.sh monitor-logs

# View application logs
./scripts/manage.sh logs

# Run manual sync
./scripts/manage.sh sync
```

## Log Files

Structured JSON logs are stored in `/logs/`:

- `sync.log` - Main sync operations
- `monitor.log` - Health check results
- `alerts.log` - Alert notifications
- `cleanup.log` - Contact cleanup operations

### Log Rotation
- **Max Size**: 10MB per file
- **Backup Count**: 5 files kept
- **Format**: JSON for structured parsing

## Testing Failure Scenarios

### Test API Authentication Failure

1. Temporarily set invalid API key:
```bash
# In .env file
PIPEDRIVE_API_KEY=invalid_key_test
```

2. Run sync or monitor:
```bash
./scripts/manage.sh sync
# or
./scripts/manage.sh monitor
```

3. Verify Google Chat alert received
4. Restore correct API key

### Test High Error Rate

1. Set very low batch size to trigger rate limiting:
```bash
# In .env file
BATCH_SIZE=1
```

2. Run sync with many records
3. Monitor for high error rate alerts

### Test Database Connection

1. Stop MySQL service temporarily:
```bash
docker-compose stop mysql
```

2. Run sync:
```bash
./scripts/manage.sh sync
```

3. Verify database error alert
4. Restart MySQL:
```bash
docker-compose start mysql
```

## Monitoring Service

The monitoring service runs automatically every 30 minutes (configurable via `MONITOR_INTERVAL_MINUTES`).

### Manual Control

```bash
# Start all services including monitor
docker-compose up -d

# View monitor service logs
docker-compose logs -f monitor

# Restart monitor service only
docker-compose restart monitor
```

## Troubleshooting

### No Alerts Received

1. Check webhook URL is correct in `.env`
2. Test webhook manually:
```bash
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"text": "Test message"}'
```
3. Check monitor logs for errors:
```bash
./scripts/manage.sh monitor-logs
```

### High False Positive Rate

Adjust thresholds in `.env`:
```bash
# Increase error threshold (default: 10%)
ALERT_ERROR_THRESHOLD=20

# Increase max sync age (default: 2 hours)
MAX_SYNC_AGE_HOURS=4
```

### Missing Log Files

Ensure logs directory exists and has proper permissions:
```bash
mkdir -p logs
chmod 755 logs
```

## Gmail Integration (Alternative)

If you prefer Gmail over Google Chat, you can extend the notification system:

1. Enable Gmail API in Google Cloud Console
2. Create service account and download credentials
3. Modify `notifications.py` to include Gmail sender class
4. Set `GMAIL_CREDENTIALS_PATH` in `.env`

The current implementation focuses on Google Chat webhooks as they're simpler to set up and more suitable for real-time alerts.
