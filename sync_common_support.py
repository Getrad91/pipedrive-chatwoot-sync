#!/usr/bin/env python3
"""
Sync Common Support Link from Pipedrive to Chatwoot Common Support field
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

def sync_common_support(contact_id, contact_name, common_support_link):
    """Sync Common Support Link to Chatwoot"""
    update_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}"
    
    # Get current contact data first
    headers = {'Api-Access-Token': CHATWOOT_API_KEY}
    get_response = requests.get(update_url, headers=headers)
    
    if get_response.status_code != 200:
        print(f"⚠️ Could not fetch {contact_name}: {get_response.status_code}")
        return False
    
    current_data = get_response.json()['payload']
    current_additional_attrs = current_data.get('additional_attributes', {})
    current_custom_attrs = current_data.get('custom_attributes', {})
    
    # Update both additional_attributes and custom_attributes with Common Support Link
    updated_additional_attrs = current_additional_attrs.copy()
    updated_additional_attrs['common_support_link'] = common_support_link
    updated_additional_attrs['support_link'] = common_support_link
    
    updated_custom_attrs = current_custom_attrs.copy()
    updated_custom_attrs['common_support_link'] = common_support_link
    updated_custom_attrs['support_link'] = common_support_link
    
    update_data = {
        'additional_attributes': updated_additional_attrs,
        'custom_attributes': updated_custom_attrs
    }
    
    try:
        response = requests.put(update_url, json=update_data, headers=headers, timeout=30)
        if response.status_code == 200:
            if common_support_link and common_support_link != 'None':
                print(f"✅ Updated {contact_name}: Common Support Link synced")
            else:
                print(f"✅ Updated {contact_name}: No Common Support Link to sync")
            return True
        else:
            print(f"⚠️ Failed to update {contact_name}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error updating {contact_name}: {str(e)}")
        return False

def main():
    print("🔧 Syncing Common Support Link to Chatwoot")
    print("=" * 50)
    
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get all contacts with their Pipedrive data
            cursor.execute("""
                SELECT name, chatwoot_contact_id, data 
                FROM organizations 
                WHERE chatwoot_contact_id IS NOT NULL AND data IS NOT NULL
                ORDER BY name
            """)
            contacts = cursor.fetchall()
            
            print(f"📊 Found {len(contacts)} contacts to sync")
            print()
            
            synced_count = 0
            error_count = 0
            no_link_count = 0
            
            for i, contact in enumerate(contacts, 1):
                contact_name = contact['name']
                contact_id = contact['chatwoot_contact_id']
                
                print(f"[{i}/{len(contacts)}] Processing: {contact_name}")
                
                try:
                    import json
                    pipedrive_data = json.loads(contact['data'])
                    
                    # Get Common Support Link from Pipedrive
                    common_support_link = pipedrive_data.get('f9c6c562ac9d61e1880fe4b5675d3a64f2bbcc6c', '')
                    
                    if common_support_link and common_support_link != 'None':
                        if sync_common_support(contact_id, contact_name, common_support_link):
                            synced_count += 1
                        else:
                            error_count += 1
                    else:
                        print(f"   No Common Support Link found for {contact_name}")
                        no_link_count += 1
                        
                except json.JSONDecodeError:
                    print(f"⚠️ Invalid JSON data for {contact_name}")
                    error_count += 1
                
                # Rate limiting
                time.sleep(0.3)
            
            print(f"\n✅ Summary:")
            print(f"   Synced: {synced_count} contacts")
            print(f"   No link: {no_link_count} contacts")
            print(f"   Errors: {error_count} contacts")
            
            if synced_count > 0:
                print(f"\n🎉 Common Support Links have been synced to Chatwoot!")
                print(f"   Check the Chatwoot interface for the updated Common Support fields.")
            
    finally:
        conn.close()

if __name__ == "__main__":
    main()
