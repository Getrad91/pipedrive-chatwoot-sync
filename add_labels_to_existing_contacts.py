#!/usr/bin/env python3
"""
Add customer labels to existing contacts that were synced without labels
"""

import os
import requests
import pymysql
import time
import logging
from dotenv import load_dotenv

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

def get_db_connection():
    """Get database connection"""
    return pymysql.connect(**DB_CONFIG)

def add_customer_label_to_contact(contact_id, contact_name, logger):
    """Add customer label to a contact"""
    try:
        labels_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/labels"
        headers = {'Api-Access-Token': CHATWOOT_API_KEY}
        
        response = requests.get(labels_url, headers=headers, timeout=30)
        if response.status_code == 200:
            current_labels = response.json().get('payload', [])
            if 'customer' in current_labels:
                logger.info(f"✅ {contact_name} already has customer label")
                return True
        
        headers['Content-Type'] = 'application/json'
        label_data = {'labels': ['customer']}
        
        response = requests.post(labels_url, json=label_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"🏷️ Added customer label to {contact_name}")
            return True
        else:
            logger.warning(f"⚠️ Failed to add label to {contact_name}: {response.status_code}")
            return False
            
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
            
            logger.info(f"\n✅ Summary:")
            logger.info(f"   Labeled: {labeled_count} contacts")
            logger.info(f"   Errors: {error_count} contacts")
            
            if labeled_count > 0:
                logger.info(f"\n🎉 Customer labels have been added to existing contacts!")
                
    finally:
        conn.close()

if __name__ == "__main__":
    main()
