# Pipedrive to Chatwoot Sync

A robust Docker-based synchronization solution that keeps your Chatwoot contacts in sync with Pipedrive CRM data, using MySQL as a middleware database for data integrity and reliability.

## 🚀 Features

- **Bidirectional Sync**: Pipedrive as the source of truth
- **MySQL Middleware**: Reliable data storage and conflict resolution
- **Docker-based**: Clean, isolated, and portable deployment
- **Error Handling**: Comprehensive logging and retry mechanisms
- **Data Validation**: Phone number normalization and data cleaning
- **Monitoring**: Built-in sync logging and status tracking
- **Web Interface**: phpMyAdmin for database management

## 📋 Prerequisites

- Docker and Docker Compose installed
- Pipedrive API token
- Chatwoot API token
- At least 2GB RAM and 10GB disk space

## 🛠️ Quick Setup

1. **Clone and navigate to the project:**
   ```bash
   cd /home/n8n/pipedrive-chatwoot-sync
   ```

2. **Run the setup script:**
   ```bash
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

3. **Edit the `.env` file with your API keys:**
   ```bash
   nano .env
   ```

4. **Get your API tokens:**
   - **Pipedrive**: Go to https://yourcompany.pipedrive.com/settings/api
   - **Chatwoot**: Go to https://support.liveport.com.au/app/accounts/2/settings/integrations/api

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `env.example`:

```bash
# API Configuration
PIPEDRIVE_API_KEY=your_pipedrive_api_token_here
CHATWOOT_API_KEY=your_chatwoot_api_token_here

# Database Configuration
MYSQL_ROOT_PASSWORD=root_password_2024
MYSQL_PASSWORD=sync_password_2024

# API URLs (usually don't need to change)
CHATWOOT_BASE_URL=https://support.liveport.com.au/api/v1/accounts/2
PIPEDRIVE_BASE_URL=https://api.pipedrive.com/v1

# Sync Configuration
BATCH_SIZE=50
RETRY_ATTEMPTS=3
RETRY_DELAY=5
DEFAULT_COUNTRY_CODE=+61
```

## 🎮 Management Commands

Use the management script for easy operations:

```bash
chmod +x scripts/manage.sh

# Start services
./scripts/manage.sh start

# Run manual sync
./scripts/manage.sh sync

# View logs
./scripts/manage.sh logs

# Check status
./scripts/manage.sh status

# Backup database
./scripts/manage.sh backup

# Stop services
./scripts/manage.sh stop
```

## 📊 Database Schema

The MySQL database includes three main tables:

### Organizations Table
- `pipedrive_org_id`: Unique Pipedrive organization ID
- `name`, `phone`, `support_link`: Organization details
- `synced_to_chatwoot`: Sync status flag
- `chatwoot_contact_id`: Linked Chatwoot contact ID

### Persons Table
- `pipedrive_person_id`: Unique Pipedrive person ID
- `name`, `email`, `phone`: Person details
- `org_id`: Associated organization ID
- `synced_to_chatwoot`: Sync status flag
- `chatwoot_contact_id`: Linked Chatwoot contact ID

### Sync Log Table
- Tracks all sync operations with timestamps and status
- Records success/failure rates and error messages

## 🔗 N8N Integration

To use this MySQL database in your N8N workflows:

### Connection String
```
Host: localhost (or your server IP)
Port: 3306
Database: pipedrive_chatwoot_sync
Username: sync_user
Password: sync_password_2024
```

### Example N8N MySQL Node Configuration
```json
{
  "host": "localhost",
  "port": 3306,
  "database": "pipedrive_chatwoot_sync",
  "user": "sync_user",
  "password": "sync_password_2024"
}
```

## 📈 Monitoring

### View Sync Logs
```bash
# Application logs
./scripts/manage.sh logs

# Database logs
docker-compose logs mysql
```

### Check Sync Status
```sql
-- View recent sync operations
SELECT * FROM sync_log ORDER BY started_at DESC LIMIT 10;

-- Check unsynced records
SELECT COUNT(*) as unsynced_orgs FROM organizations WHERE synced_to_chatwoot=FALSE;
SELECT COUNT(*) as unsynced_persons FROM persons WHERE synced_to_chatwoot=FALSE;
```

### Web Interface
- **phpMyAdmin**: http://localhost:8080
  - Username: `sync_user`
  - Password: `sync_password_2024`

## 🔄 Sync Process

1. **Fetch from Pipedrive**: Retrieves all organizations and persons
2. **Store in MySQL**: Upserts data with conflict resolution
3. **Sync to Chatwoot**: Creates/updates contacts in Chatwoot
4. **Update Status**: Marks records as synced
5. **Log Results**: Records operation in sync_log table

## 🛡️ Security

- MySQL root access is restricted to localhost
- Dedicated `sync_user` with limited permissions
- API keys stored in environment variables
- Database connections use SSL (configurable)

## 📁 File Structure

```
pipedrive-chatwoot-sync/
├── app/
│   ├── sync.py              # Main sync application
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile          # Application container
├── mysql/
│   ├── init.sql            # Database schema
│   └── my.cnf              # MySQL configuration
├── scripts/
│   ├── setup.sh            # Initial setup script
│   └── manage.sh           # Management commands
├── logs/                   # Application logs
├── backups/                # Database backups
├── docker-compose.yml      # Service orchestration
├── env.example             # Environment template
└── README.md              # This file
```

## 🚨 Troubleshooting

### Common Issues

1. **API Key Errors**
   ```bash
   # Check if API keys are set
   docker-compose exec sync-app env | grep API_KEY
   ```

2. **Database Connection Issues**
   ```bash
   # Test database connection
   ./scripts/manage.sh db
   ```

3. **Sync Failures**
   ```bash
   # Check sync logs
   ./scripts/manage.sh logs
   
   # Check database sync status
   ./scripts/manage.sh db
   SELECT * FROM sync_log ORDER BY started_at DESC LIMIT 5;
   ```

4. **Container Issues**
   ```bash
   # Restart services
   ./scripts/manage.sh restart
   
   # Clean rebuild
   ./scripts/manage.sh clean
   ./scripts/setup.sh
   ```

### Performance Tuning

- Adjust `BATCH_SIZE` in `.env` for larger datasets
- Increase `innodb_buffer_pool_size` in `mysql/my.cnf`
- Monitor memory usage with `./scripts/manage.sh status`

## 🔄 Automation

### Cron Job Setup
To set up all automated tasks:

```bash
# Run the comprehensive cron setup script
./scripts/setup-cron.sh

# If crontab is not available, the script will save configuration to crontab.txt
# Install manually with: crontab crontab.txt

# Monitor cron job health:
./scripts/monitor-cron.sh

# Test individual scripts:
./scripts/auto-sync.sh      # Automated sync with logging
./scripts/manual-sync.sh    # Manual sync with console output
```

#### Scheduled Jobs
- **Main sync**: Every 30 minutes during business hours (8am-5pm, weekdays)
- **Storage cleanup**: Daily at 2 AM
- **Storage monitoring**: Every 4 hours  
- **Database backup**: Daily at 3 AM
- **Inbox assignment**: Weekly on Sundays at 1 AM
- **Common support sync**: Weekly on Sundays at 1 AM

All jobs include proper logging to `logs/` directory with automatic log rotation.


### Docker Compose with Scheduler
Uncomment the scheduler command in `docker-compose.yml` to run sync every 30 minutes automatically.

## 📞 Support

For issues or questions:
1. Check the logs: `./scripts/manage.sh logs`
2. Verify configuration: `./scripts/manage.sh status`
3. Test database connection: `./scripts/manage.sh db`
4. Review sync history in the database

## 🔄 Updates

To update the sync application:

```bash
./scripts/manage.sh update
```

This will pull the latest images and rebuild containers while preserving your data.
