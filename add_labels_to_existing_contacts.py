#!/usr/bin/env python3
"""
Add customer labels to existing contacts that were synced without labels
"""

import os
import sys
import requests
import pymysql
import time
import logging
from dotenv import load_dotenv

sys.path.append('app')
from error_handling import robust_api_request, CHATWOOT_CONFIG, DATABASE_CONFIG, retry_on_failure

load_dotenv()

# Configuration
CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3307')),
    'user': os.getenv('MYSQL_USER', 'sync_user'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE', 'pipedrive_chatwoot_sync'),
    'charset': 'utf8mb4'
}


def setup_logging():
    """Set up logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)


@retry_on_failure(config=DATABASE_CONFIG, operation_name="Database connection")
def get_db_connection():
    """Get database connection with retry logic"""
    return pymysql.connect(**DB_CONFIG)


def add_customer_label_to_contact(contact_id, contact_name, logger):
    """Add customer label to a contact with robust error handling"""
    try:
        labels_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/labels"
        headers = {'Api-Access-Token': CHATWOOT_API_KEY}

        try:
            response = robust_api_request(
                requests.get,
                labels_url,
                headers=headers,
                config=CHATWOOT_CONFIG,
                logger=logger,
                operation_name=f"Check labels for {contact_name}"
            )

            current_labels = response.json().get('payload', [])
            if 'customer' in current_labels:
                logger.info(f"✅ {contact_name} already has customer label")
                return True
        except Exception as e:
            logger.warning(f"Failed to check existing labels for {contact_name}: {e}. Proceeding to add label.")

        headers['Content-Type'] = 'application/json'
        label_data = {'labels': ['customer']}

        robust_api_request(
            requests.post,
            labels_url,
            json=label_data,
            headers=headers,
            config=CHATWOOT_CONFIG,
            logger=logger,
            operation_name=f"Add customer label to {contact_name}"
        )

        logger.info(f"🏷️ Added customer label to {contact_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Error adding label to {contact_name}: {str(e)}")
        return False


def main():
    """Main function"""
    logger = setup_logging()

    logger.info("🏷️ Adding customer labels to existing synced contacts")
    logger.info("=" * 60)

    try:
        conn = get_db_connection()
        logger.info("✅ Connected to database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.info("💡 Make sure Docker services are running: docker-compose up -d")
        return

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT name, chatwoot_contact_id
                FROM organizations
                WHERE synced_to_chatwoot = 1 AND chatwoot_contact_id IS NOT NULL
                ORDER BY name
            """)
            contacts = cursor.fetchall()

            logger.info(f"📊 Found {len(contacts)} synced contacts to process")

            if not contacts:
                logger.info("✅ No contacts found to process")
                return

            labeled_count = 0
            error_count = 0

            for i, contact in enumerate(contacts, 1):
                contact_name = contact['name']
                contact_id = contact['chatwoot_contact_id']

                logger.info(f"[{i}/{len(contacts)}] Processing: {contact_name}")

                if add_customer_label_to_contact(contact_id, contact_name, logger):
                    labeled_count += 1
                else:
                    error_count += 1

                # Rate limiting
                time.sleep(1)

            logger.info("✅ Summary:")
            logger.info(f"   Labeled: {labeled_count} contacts")
            logger.info(f"   Errors: {error_count} contacts")

            if labeled_count > 0:
                logger.info("🎉 Customer labels have been added to existing contacts!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
