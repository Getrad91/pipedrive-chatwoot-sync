#!/usr/bin/env python3
"""
Test script to reproduce and investigate Chatwoot labels API persistence issue
"""

import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')

def test_labels_api():
    """Test Chatwoot labels API functionality"""
    print("🔍 Testing Chatwoot Labels API Persistence Issue")
    print("=" * 60)
    
    print("\n1. Confirming Chatwoot version and features...")
    account_url = f"{CHATWOOT_BASE_URL.replace('/accounts/2', '')}/accounts/2"
    headers = {'Api-Access-Token': CHATWOOT_API_KEY}
    
    response = requests.get(account_url, headers=headers)
    if response.status_code == 200:
        account_data = response.json()
        version = account_data.get('latest_chatwoot_version', 'Unknown')
        labels_enabled = account_data.get('features', {}).get('labels', False)
        print(f"   ✅ Chatwoot version: {version}")
        print(f"   ✅ Labels feature enabled: {labels_enabled}")
    else:
        print(f"   ❌ Failed to get account info: {response.status_code}")
        return
    
    print("\n2. Getting available labels...")
    labels_url = f"{CHATWOOT_BASE_URL}/labels"
    response = requests.get(labels_url, headers=headers)
    if response.status_code == 200:
        labels_data = response.json()
        labels = labels_data.get('payload', [])
        print(f"   ✅ Found {len(labels)} labels:")
        for label in labels:
            print(f"      - {label['title']} (ID: {label['id']}, Color: {label['color']})")
    else:
        print(f"   ❌ Failed to get labels: {response.status_code}")
        return
    
    print("\n3. Getting test contact...")
    contacts_url = f"{CHATWOOT_BASE_URL}/contacts"
    response = requests.get(contacts_url, headers=headers, params={'page': 1, 'per_page': 1})
    if response.status_code == 200:
        contacts_data = response.json()
        contacts = contacts_data.get('payload', [])
        if contacts:
            test_contact = contacts[0]
            contact_id = test_contact['id']
            contact_name = test_contact['name']
            print(f"   ✅ Using test contact: {contact_name} (ID: {contact_id})")
        else:
            print("   ❌ No contacts found")
            return
    else:
        print(f"   ❌ Failed to get contacts: {response.status_code}")
        return
    
    print("\n4. Checking current labels on contact...")
    contact_labels_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/labels"
    response = requests.get(contact_labels_url, headers=headers)
    if response.status_code == 200:
        current_labels = response.json().get('payload', [])
        print(f"   ✅ Current labels: {current_labels}")
    else:
        print(f"   ❌ Failed to get contact labels: {response.status_code}")
        return
    
    print("\n5. Adding 'customer' label to contact...")
    add_data = {'labels': ['customer']}
    response = requests.post(contact_labels_url, headers=headers, json=add_data)
    if response.status_code == 200:
        result = response.json().get('payload', [])
        print(f"   ✅ API response after adding label: {result}")
    else:
        print(f"   ❌ Failed to add label: {response.status_code} - {response.text}")
        return
    
    print("\n6. Verifying label persistence (immediate check)...")
    time.sleep(1)  # Brief pause
    response = requests.get(contact_labels_url, headers=headers)
    if response.status_code == 200:
        labels_after_add = response.json().get('payload', [])
        print(f"   ✅ Labels after adding: {labels_after_add}")
        if 'customer' in labels_after_add:
            print("   ✅ Label persisted successfully!")
        else:
            print("   ❌ Label NOT persisted - this is the bug!")
    else:
        print(f"   ❌ Failed to verify labels: {response.status_code}")
    
    print("\n7. Checking if labels appear in contacts list...")
    response = requests.get(f"{CHATWOOT_BASE_URL}/contacts/{contact_id}", headers=headers)
    if response.status_code == 200:
        contact_data = response.json().get('payload', {})
        if 'labels' in contact_data:
            print(f"   ✅ Contact has labels field: {contact_data['labels']}")
        else:
            print("   ⚠️ Contact data does not include labels field")
            print("   📝 This suggests labels are stored separately from contact data")
    
    print("\n8. Testing with 'suspended' label...")
    add_data = {'labels': ['suspended']}
    response = requests.post(contact_labels_url, headers=headers, json=add_data)
    if response.status_code == 200:
        result = response.json().get('payload', [])
        print(f"   ✅ API response: {result}")
        
        time.sleep(1)
        response = requests.get(contact_labels_url, headers=headers)
        if response.status_code == 200:
            final_labels = response.json().get('payload', [])
            print(f"   ✅ Final labels: {final_labels}")
        
    print("\n" + "=" * 60)
    print("🔍 INVESTIGATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_labels_api()
