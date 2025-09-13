#!/usr/bin/env python3
"""
Fix inbox assignment for existing contacts
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

def get_support_inbox_id():
    """Get the support inbox ID"""
    inboxes_url = f"{CHATWOOT_BASE_URL}/inboxes"
    inboxes_headers = {'Api-Access-Token': CHATWOOT_API_KEY}
    inboxes_response = requests.get(inboxes_url, headers=inboxes_headers, timeout=30)
    
    if inboxes_response.status_code == 200:
        inboxes_data = inboxes_response.json()
        inboxes = inboxes_data.get('payload', inboxes_data.get('data', []))
        # Find the Support Email inbox
        for inbox in inboxes:
            if 'support' in inbox.get('name', '').lower() or inbox.get('channel_type') == 'Channel::Email':
                return inbox.get('id'), inbox.get('name')
    
    return None, None

def assign_contact_to_inbox(contact_id, inbox_id, contact_name):
    """Assign a contact to an inbox"""
    assign_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/contact_inboxes"
    assign_data = {'inbox_id': inbox_id}
    assign_headers = {'Api-Access-Token': CHATWOOT_API_KEY, 'Content-Type': 'application/json'}
    
    response = requests.post(assign_url, json=assign_data, headers=assign_headers, timeout=30)
    if response.status_code == 200:
        print(f"✅ Assigned {contact_name} to support inbox")
        return True
    else:
        print(f"⚠️ Could not assign {contact_name} to inbox: {response.status_code} - {response.text}")
        return False

def main():
    print("🔧 Fixing inbox assignment for existing contacts")
    print("=" * 50)
    
    # Get support inbox ID
    support_inbox_id, inbox_name = get_support_inbox_id()
    if not support_inbox_id:
        print("❌ Could not find support inbox")
        return
    
    print(f"📧 Using inbox: {inbox_name} (ID: {support_inbox_id})")
    
    # Get all contacts from database
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT name, chatwoot_contact_id FROM organizations WHERE chatwoot_contact_id IS NOT NULL")
            contacts = cursor.fetchall()
            
            print(f"📊 Found {len(contacts)} contacts to fix")
            
            assigned_count = 0
            error_count = 0
            
            for contact in contacts:
                contact_name = contact['name']
                contact_id = contact['chatwoot_contact_id']
                
                print(f"🔧 Processing: {contact_name} (ID: {contact_id})")
                
                if assign_contact_to_inbox(contact_id, support_inbox_id, contact_name):
                    assigned_count += 1
                else:
                    error_count += 1
                
                # Rate limiting
                time.sleep(1)
            
            print(f"\n✅ Fixed {assigned_count} contacts, {error_count} errors")
            
    finally:
        conn.close()

if __name__ == "__main__":
    main()
