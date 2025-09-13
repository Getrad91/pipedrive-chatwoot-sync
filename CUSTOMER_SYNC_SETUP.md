# Customer-Only Sync Setup

## Overview
This setup automatically syncs Customer contacts from Pipedrive to Chatwoot, running every 30 minutes during business hours (8am-5pm, weekdays only).

## What's Configured

### ✅ Customer-Only Filtering
- Only processes contacts with Pipedrive label `5` (Customer)
- Excludes Suspended (239) and Cancelled (43) contacts
- Database contains 100 customer organizations and 100 customer persons

### ✅ Automatic Syncing
- **Schedule**: Every 30 minutes between 8am-5pm on weekdays
- **Cron Expression**: `*/30 8-17 * * 1-5`
- **Log File**: `/home/n8n/pipedrive-chatwoot-sync/logs/auto-sync.log`

### ✅ Rate Limiting
- Respects Chatwoot's 60 requests/minute limit
- 1-second delay between API calls
- 60-second wait when rate limited

## Available Scripts

### 1. Manual Sync (for testing)
```bash
sudo ./scripts/manual-sync.sh
```

### 2. Auto Sync (incremental)
```bash
sudo ./scripts/auto-sync.sh
```

### 3. Setup Cron Job
```bash
sudo ./scripts/setup-cron.sh
```

## Monitoring

### View Sync Logs
```bash
tail -f logs/auto-sync.log
```

### Check Database Status
```bash
sudo docker-compose exec mysql mysql -u root -pSuperStrongPassword123! -e "USE pipedrive_chatwoot_sync; SELECT 'Organizations' as table_name, COUNT(*) as count FROM organizations UNION ALL SELECT 'Persons' as table_name, COUNT(*) as count FROM persons UNION ALL SELECT 'Contacts' as table_name, COUNT(*) as count FROM contacts;"
```

### Check Cron Job
```bash
crontab -l
```

## How It Works

1. **Every 30 minutes** (8am-5pm weekdays):
   - Fetches Customer contacts from Pipedrive
   - Updates local MySQL database
   - Syncs new/updated contacts to Chatwoot
   - Logs all activity

2. **For each contact**:
   - Searches Chatwoot for existing contact
   - If exists: Updates the contact
   - If new: Creates new contact
   - Never deletes existing contacts

3. **Rate Limiting**:
   - 1-second delay between requests
   - 60-second wait if rate limited
   - Gradually processes all 200 contacts over time

## Current Status
- ✅ 100 Customer organizations ready to sync
- ✅ 100 Customer persons ready to sync
- ✅ Automatic syncing configured
- ✅ Rate limiting implemented
- ⏳ Syncing in progress (will complete gradually)

## Next Steps
The system will automatically:
1. Sync all 200 customer contacts over the next few hours
2. Continue syncing new customers as they're added to Pipedrive
3. Run during business hours only (8am-5pm weekdays)

No further action required - the system is fully automated!
