#!/usr/bin/env python3
"""
Test script to verify the labels fix is working correctly
"""

import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')

def test_labels_fix():
    """Test that labels are being added correctly"""
    print("🧪 Testing Labels Fix Implementation")
    print("=" * 50)
    
    headers = {'Api-Access-Token': CHATWOOT_API_KEY}
    
    print("\n1. Getting sample contacts...")
    contacts_url = f"{CHATWOOT_BASE_URL}/contacts"
    response = requests.get(contacts_url, headers=headers, params={'page': 1, 'per_page': 5})
    
    if response.status_code != 200:
        print(f"❌ Failed to get contacts: {response.status_code}")
        return
    
    contacts = response.json().get('payload', [])
    print(f"✅ Found {len(contacts)} contacts to test")
    
    print("\n2. Checking labels on contacts...")
    labeled_contacts = 0
    
    for contact in contacts:
        contact_id = contact['id']
        contact_name = contact['name']
        
        labels_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/labels"
        response = requests.get(labels_url, headers=headers)
        
        if response.status_code == 200:
            labels = response.json().get('payload', [])
            if labels:
                print(f"   ✅ {contact_name}: {labels}")
                labeled_contacts += 1
            else:
                print(f"   ⚪ {contact_name}: No labels")
        else:
            print(f"   ❌ {contact_name}: Failed to get labels")
    
    print(f"\n📊 Results: {labeled_contacts}/{len(contacts)} contacts have labels")
    
    if labeled_contacts > 0:
        print("✅ Labels functionality is working!")
    else:
        print("⚠️ No contacts have labels - may need to run sync or add_labels script")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_labels_fix()
