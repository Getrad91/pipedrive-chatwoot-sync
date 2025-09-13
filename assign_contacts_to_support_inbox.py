#!/usr/bin/env python3
"""
Safely assign existing contacts to the Support Email inbox only
"""
import requests
import pymysql
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')
CUSTOMER_DATABASE_INBOX_ID = 9  # Customer Database inbox - dedicated for Pipedrive contacts

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3307')),
    'user': os.getenv('MYSQL_USER', 'sync_user'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE', 'pipedrive_chatwoot_sync'),
    'charset': 'utf8mb4'
}

def get_db_connection():
    """Get database connection"""
    return pymysql.connect(**DB_CONFIG)

def assign_contact_to_customer_database_inbox(contact_id, contact_name):
    """Assign a contact to the Customer Database inbox"""
    assign_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/contact_inboxes"
    assign_data = {
        'inbox_id': CUSTOMER_DATABASE_INBOX_ID, 
        'source_id': f'pipedrive_{contact_id}'  # Use the working format
    }
    assign_headers = {'Api-Access-Token': CHATWOOT_API_KEY, 'Content-Type': 'application/json'}
    
    response = requests.post(assign_url, json=assign_data, headers=assign_headers, timeout=30)
    if response.status_code == 200:
        print(f"✅ Assigned {contact_name} to Customer Database inbox")
        return True
    else:
        print(f"⚠️ Could not assign {contact_name} to Customer Database inbox: {response.status_code} - {response.text}")
        return False

def main():
    print("🔧 Assigning contacts to Customer Database inbox")
    print("=" * 60)
    print(f"📧 Target inbox: Customer Database (ID: {CUSTOMER_DATABASE_INBOX_ID})")
    print()
    
    # Get all contacts from database
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT name, chatwoot_contact_id FROM organizations WHERE chatwoot_contact_id IS NOT NULL")
            contacts = cursor.fetchall()
            
            print(f"📊 Found {len(contacts)} contacts to assign")
            print()
            
            assigned_count = 0
            error_count = 0
            
            for i, contact in enumerate(contacts, 1):
                contact_name = contact['name']
                contact_id = contact['chatwoot_contact_id']
                
                print(f"[{i}/{len(contacts)}] Processing: {contact_name} (ID: {contact_id})")
                
                if assign_contact_to_customer_database_inbox(contact_id, contact_name):
                    assigned_count += 1
                else:
                    error_count += 1
                
                # Rate limiting
                time.sleep(1)
            
            print(f"\n✅ Summary:")
            print(f"   Assigned: {assigned_count} contacts")
            print(f"   Errors: {error_count} contacts")
            
            if assigned_count > 0:
                print(f"\n🔍 Check the contacts at: https://support.liveport.com.au/app/accounts/2/contacts")
            
    finally:
        conn.close()

if __name__ == "__main__":
    main()
