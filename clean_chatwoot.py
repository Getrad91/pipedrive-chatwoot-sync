#!/usr/bin/env python3
"""
Simple script to clean all contacts from Chatwoot
"""

import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')

def get_all_contacts():
    """Get all contacts from Chatwoot"""
    all_contacts = []
    page = 1
    
    while True:
        url = f"{CHATWOOT_BASE_URL}/contacts"
        params = {'page': page, 'per_page': 50}
        headers = {'Api-Access-Token': CHATWOOT_API_KEY}
        
        print(f"📄 Fetching page {page}...")
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            break
        
        data = response.json()
        contacts = data.get('payload', data.get('data', []))
        
        if not contacts:
            print("✅ No more contacts found")
            break
        
        all_contacts.extend(contacts)
        print(f"   Found {len(contacts)} contacts")
        
        page += 1
        time.sleep(1)
    
    return all_contacts

def delete_contact(contact_id, contact_name):
    """Delete a single contact"""
    url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}"
    headers = {'Api-Access-Token': CHATWOOT_API_KEY}
    
    response = requests.delete(url, headers=headers, timeout=30)
    
    if response.status_code in [200, 204]:
        return True
    else:
        print(f"❌ Failed to delete {contact_name}: {response.status_code}")
        return False

def main():
    """Main function"""
    print("🧹 Chatwoot Contact Cleanup")
    print("=" * 30)
    
    # Get all contacts
    contacts = get_all_contacts()
    
    if not contacts:
        print("✅ No contacts found to delete")
        return
    
    print(f"📊 Found {len(contacts)} contacts to delete")
    
    # Confirm deletion
    confirm = input(f"\nDelete ALL {len(contacts)} contacts? (type 'YES' to confirm): ")
    if confirm != "YES":
        print("❌ Operation cancelled")
        return
    
    # Delete contacts
    deleted = 0
    for i, contact in enumerate(contacts, 1):
        contact_id = contact['id']
        contact_name = contact.get('name', f'Contact {contact_id}')
        
        print(f"[{i}/{len(contacts)}] Deleting: {contact_name}")
        
        if delete_contact(contact_id, contact_name):
            deleted += 1
        
        time.sleep(1)
    
    print(f"\n✅ Deleted {deleted} contacts")

if __name__ == "__main__":
    main()
