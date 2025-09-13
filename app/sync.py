#!/usr/bin/env python3
"""
<<<<<<< HEAD
Simple, clean Pipedrive to Chatwoot sync you
||||||| f1b27bb
Simple, clean Pipedrive to Chatwoot sync you 
=======
Simple, clean Pipedrive to Chatwoot sync
>>>>>>> main

Syncs ONLY Customer organizations (label 5) from Pipedrive to Chatwoot
"""

import os
import sys
import time
import json
import logging
import requests
import pymysql
import pymysql.cursors
from datetime import datetime
from dotenv import load_dotenv

sys.path.append('/app')
from logging_config import get_sync_logger, log_with_extra  # noqa: E402
from notifications import send_sync_alert  # noqa: E402

# Load environment variables
load_dotenv()

# Configuration
PIPEDRIVE_API_KEY = os.getenv('PIPEDRIVE_API_KEY')
CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')
PIPEDRIVE_BASE_URL = os.getenv('PIPEDRIVE_BASE_URL', 'https://api.pipedrive.com/v1')

# Database configuration
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3307')),
    'user': os.getenv('MYSQL_USER', 'sync_user'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE', 'pipedrive_chatwoot_sync'),
    'charset': 'utf8mb4'
}


def setup_logging():
    """Set up logging using centralized configuration"""
    return get_sync_logger()


def get_db_connection():
    """Get database connection"""
    return pymysql.connect(**DB_CONFIG)


def get_customer_organizations():
    """Get all Customer organizations from Pipedrive"""
    logger = logging.getLogger(__name__)
    organizations = []
    start = 0
    limit = 100

    while True:
        try:
            params = {
                'api_token': PIPEDRIVE_API_KEY,
                'start': start,
                'limit': limit
            }

            response = requests.get(f"{PIPEDRIVE_BASE_URL}/organizations", params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            page_orgs = data.get('data', [])

            # Filter for Customer organizations only (label 5)
            customer_orgs = [org for org in page_orgs if org.get('label') == 5]
            organizations.extend(customer_orgs)

            logger.info(f"Page {start // limit + 1}: Found {len(customer_orgs)} Customer organizations")

            # Check pagination
            pagination = data.get('additional_data', {}).get('pagination', {})
            if not pagination.get('more_items_in_collection', False):
                break

            start = pagination.get('next_start', start + limit)
            time.sleep(1)  # Rate limiting

        except Exception as e:
            logger.error(f"Error fetching organizations: {e}")
            break

    logger.info(f"Total Customer organizations found: {len(organizations)}")
    return organizations


def clean_organization_data(org):
    """Clean organization data"""
    return {
        'pipedrive_org_id': org['id'],
        'name': (org.get('name') or '').strip(),
        'phone': normalize_phone(org.get('phone', '')),
        'email': (org.get('email') or '').strip(),
        'city': (org.get('address_locality') or '').strip(),
        'country': (org.get('address_country') or '').strip(),
        'status': 'Customer',
        'support_link': org.get('Common Support Link') or org.get('Main Support Link', ''),
        'notes': (org.get('notes') or '').strip(),
        'deal_title': (org.get('deal_title') or '').strip(),
        'owner_name': org.get('owner_id', {}).get('name', '') if org.get('owner_id') else '',
        'raw_data': json.dumps(org)
    }


def normalize_phone(phone):
    """Normalize phone number"""
    if not phone:
        return ""
    phone = "".join(c for c in phone if c.isdigit() or c == "+")
    if not phone.startswith("+"):
        phone = "+61" + phone.lstrip("0")
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 8 or len(digits) > 15:
        return ""
    return phone


def store_organizations(organizations):
    """Store organizations in database"""
    logger = logging.getLogger(__name__)
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            # Clear existing data
            cursor.execute("DELETE FROM organizations")

            # Insert new data
            sql = """
            INSERT INTO organizations
              (pipedrive_org_id, name, phone, support_link, city, country,
               email, status, data, notes, deal_title, owner_name,
               synced_to_chatwoot)
            VALUES
              (%(pipedrive_org_id)s, %(name)s, %(phone)s, %(support_link)s,
               %(city)s, %(country)s, %(email)s, %(status)s, %(raw_data)s,
               %(notes)s, %(deal_title)s, %(owner_name)s, 0)
            """

            for org in organizations:
                cursor.execute(sql, clean_organization_data(org))

            conn.commit()
            logger.info(f"Stored {len(organizations)} organizations in database")

    finally:
        conn.close()


def sync_to_chatwoot():
    """Sync organizations to Chatwoot"""
    logger = logging.getLogger(__name__)
    conn = get_db_connection()

    try:
        # Get the Customer Database inbox ID
        inboxes_url = f"{CHATWOOT_BASE_URL}/inboxes"
        inboxes_headers = {'Api-Access-Token': CHATWOOT_API_KEY}
        inboxes_response = requests.get(inboxes_url, headers=inboxes_headers, timeout=30)

        customer_database_inbox_id = None
        if inboxes_response.status_code == 200:
            inboxes_data = inboxes_response.json()
            inboxes = inboxes_data.get('payload', inboxes_data.get('data', []))
            # Find the Customer Database inbox
            for inbox in inboxes:
                if 'customer database' in inbox.get('name', '').lower():
                    customer_database_inbox_id = inbox.get('id')
                    logger.info(f"Using inbox: {inbox.get('name')} (ID: {customer_database_inbox_id})")
                    break

        if not customer_database_inbox_id:
            logger.warning("Could not find Customer Database inbox, contacts may not be visible in Chatwoot interface")

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM organizations WHERE synced_to_chatwoot = 0")
            organizations = cursor.fetchall()

            logger.info(f"Syncing {len(organizations)} organizations to Chatwoot")

            synced_count = 0
            error_count = 0

            for org in organizations:
                try:
                    # Search for existing contact
                    search_url = f"{CHATWOOT_BASE_URL}/contacts/search"
                    search_params = {'q': org['name']}
                    search_headers = {'Api-Access-Token': CHATWOOT_API_KEY}

                    search_response = requests.get(search_url, params=search_params,
                                                   headers=search_headers, timeout=30)

                    if search_response.status_code == 429:
                        logger.warning("Rate limited, waiting 60 seconds...")
                        time.sleep(60)
                        search_response = requests.get(search_url, params=search_params,
                                                       headers=search_headers, timeout=30)

                    existing_contact = None
                    if search_response.status_code == 200:
                        search_data = search_response.json()
                        contacts = search_data.get('payload', search_data.get('data', []))
                        if contacts:
                            existing_contact = contacts[0]

                    # Prepare contact data
                    contact_data = {
                        'name': org['name'],
                        'phone_number': org['phone'] if org['phone'] else None,
                        'custom_attributes': {
                            'pipedrive_org_id': org['pipedrive_org_id'],
                            'type': 'organization',
                            'status': org['status'],
                            'city': org['city'],
                            'country': org['country'],
                            'support_link': org['support_link'],
                            'company_name': org['name'],
                            'organization_name': org['name']
                        }
                    }

                    # Create or update contact
                    time.sleep(1)  # Rate limiting

                    if existing_contact:
                        # Update existing contact
                        update_url = f"{CHATWOOT_BASE_URL}/contacts/{existing_contact['id']}"
<<<<<<< HEAD
                        update_headers = {'Api-Access-Token': CHATWOOT_API_KEY, 'Content-Type': 'application/json'}

                        response = requests.put(update_url, json=contact_data, headers=update_headers, timeout=30)
||||||| f1b27bb
                        update_headers = {'Api-Access-Token': CHATWOOT_API_KEY, 'Content-Type': 'application/json'}
                        
                        response = requests.put(update_url, json=contact_data, headers=update_headers, timeout=30)
=======
                        update_headers = {'Api-Access-Token': CHATWOOT_API_KEY,
                                          'Content-Type': 'application/json'}

                        response = requests.put(update_url, json=contact_data,
                                                headers=update_headers, timeout=30)
>>>>>>> main
                        chatwoot_id = existing_contact['id']
                    else:
                        # Create new contact
                        create_url = f"{CHATWOOT_BASE_URL}/contacts"
<<<<<<< HEAD
                        create_headers = {'Api-Access-Token': CHATWOOT_API_KEY, 'Content-Type': 'application/json'}

                        response = requests.post(create_url, json=contact_data, headers=create_headers, timeout=30)
||||||| f1b27bb
                        create_headers = {'Api-Access-Token': CHATWOOT_API_KEY, 'Content-Type': 'application/json'}
                        
                        response = requests.post(create_url, json=contact_data, headers=create_headers, timeout=30)
=======
                        create_headers = {'Api-Access-Token': CHATWOOT_API_KEY,
                                          'Content-Type': 'application/json'}

                        response = requests.post(create_url, json=contact_data,
                                                 headers=create_headers, timeout=30)
>>>>>>> main
                        if response.status_code == 200:
                            response_data = response.json()
                            # Chatwoot API returns contact ID in payload.contact.id
                            chatwoot_id = response_data.get('payload', {}).get('contact', {}).get('id')
                        else:
                            chatwoot_id = None

                    if response.status_code == 429:
                        logger.warning("Rate limited, waiting 60 seconds...")
                        time.sleep(60)
                        continue

                    if response.status_code in [200, 201]:
                        # Assign contact to Customer Database inbox if we have the inbox ID
                        if chatwoot_id and customer_database_inbox_id:
                            try:
                                assign_url = f"{CHATWOOT_BASE_URL}/contacts/{chatwoot_id}/contact_inboxes"
<<<<<<< HEAD
                                assign_data = {'inbox_id': customer_database_inbox_id,
                                               'source_id': f'pipedrive_{chatwoot_id}'}
                                assign_headers = {'Api-Access-Token': CHATWOOT_API_KEY,
                                                  'Content-Type': 'application/json'}

                                assign_response = requests.post(assign_url, json=assign_data,
                                                                headers=assign_headers, timeout=30)
||||||| f1b27bb
                                assign_data = {'inbox_id': customer_database_inbox_id, 'source_id': f'pipedrive_{chatwoot_id}'}
                                assign_headers = {'Api-Access-Token': CHATWOOT_API_KEY, 'Content-Type': 'application/json'}
                                
                                assign_response = requests.post(assign_url, json=assign_data, headers=assign_headers, timeout=30)
=======
                                assign_data = {
                                    'inbox_id': customer_database_inbox_id,
                                    'source_id': f'pipedrive_{chatwoot_id}'
                                }
                                assign_headers = {
                                    'Api-Access-Token': CHATWOOT_API_KEY,
                                    'Content-Type': 'application/json'
                                }

                                assign_response = requests.post(
                                    assign_url, json=assign_data,
                                    headers=assign_headers, timeout=30)
>>>>>>> main
                                if assign_response.status_code == 200:
                                    logger.info(f"✅ Assigned {org['name']} to Customer Database inbox")
                                else:
<<<<<<< HEAD
                                    logger.warning(f"⚠️ Could not assign {org['name']} to inbox: "
                                                   f"{assign_response.status_code}")
||||||| f1b27bb
                                    logger.warning(f"⚠️ Could not assign {org['name']} to inbox: {assign_response.status_code}")
=======
                                    logger.warning(
                                        f"⚠️ Could not assign {org['name']} to inbox: "
                                        f"{assign_response.status_code}")
>>>>>>> main
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to assign {org['name']} to inbox: {str(e)}")

                        # Mark as synced
                        cursor.execute(
<<<<<<< HEAD
                            "UPDATE organizations SET synced_to_chatwoot = 1, chatwoot_contact_id = %s "
                            "WHERE pipedrive_org_id = %s",
||||||| f1b27bb
                            "UPDATE organizations SET synced_to_chatwoot = 1, chatwoot_contact_id = %s WHERE pipedrive_org_id = %s",
=======
                            "UPDATE organizations SET synced_to_chatwoot = 1, "
                            "chatwoot_contact_id = %s WHERE pipedrive_org_id = %s",
>>>>>>> main
                            (chatwoot_id, org['pipedrive_org_id'])
                        )
                        synced_count += 1
                        logger.info(f"✅ Synced: {org['name']} → Chatwoot ID {chatwoot_id}")
                    else:
                        error_count += 1
                        logger.error(f"❌ Failed to sync: {org['name']} - {response.status_code}")
                        logger.error(f"Response text: {response.text}")

                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Error syncing {org['name']}: {e}")
                    import traceback
                    logger.error(f"Full error: {traceback.format_exc()}")

            conn.commit()
            logger.info(f"Sync completed: {synced_count} synced, {error_count} errors")

            try:
                with conn.cursor() as log_cursor:
                    total_processed = synced_count + error_count
                    status = 'success' if error_count == 0 else (
                        'partial' if synced_count > 0 else 'error')

                    log_cursor.execute("""
                        INSERT INTO sync_log (sync_type, status, records_processed,
                                            records_synced, error_message, completed_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        'organizations',
                        status,
                        total_processed,
                        synced_count,
                        f"{error_count} errors occurred" if error_count > 0 else None,
                        datetime.now()
                    ))
                    conn.commit()
            except Exception as e:
                logger.warning(f"Failed to log sync results: {e}")

            if total_processed > 0:
                error_rate = (error_count / total_processed) * 100
                if error_rate > 10:  # Alert if more than 10% errors
                    send_sync_alert(
                        'sync',
                        'high error rate',
                        f"Sync completed with high error rate: {error_rate:.1f}%",
                        {
                            'total_processed': total_processed,
                            'synced_count': synced_count,
                            'error_count': error_count,
                            'error_rate': f"{error_rate:.1f}%"
                        },
                        'WARNING'
                    )

            log_with_extra(logger, 20, "Sync operation completed", {
                'synced_count': synced_count,
                'error_count': error_count,
                'total_processed': total_processed,
                'error_rate': f"{(error_count / total_processed * 100):.1f}%" if total_processed > 0 else "0%"
            })

    finally:
        conn.close()


def main():
    """Main function"""
    logger = setup_logging()

    logger.info("🚀 Starting Pipedrive to Chatwoot sync")
    logger.info("=" * 50)

    try:
        # Step 1: Get Customer organizations from Pipedrive
        logger.info("📥 Fetching Customer organizations from Pipedrive...")
        organizations = get_customer_organizations()

        if not organizations:
            logger.error("❌ No Customer organizations found")
            send_sync_alert(
                'sync',
                'no data',
                "No Customer organizations found in Pipedrive",
                {'label_filter': 5},
                'WARNING'
            )
            return

        # Step 2: Store in database
        logger.info("💾 Storing organizations in database...")
        store_organizations(organizations)

        # Step 3: Sync to Chatwoot
        logger.info("🔄 Syncing organizations to Chatwoot...")
        sync_to_chatwoot()

        logger.info("✅ Sync completed!")

    except Exception as e:
        error_msg = f"Sync process failed with critical error: {e}"
        logger.error(error_msg)
        send_sync_alert(
            'sync',
            'system error',
            error_msg,
            {'error': str(e)},
            'ERROR'
        )
        raise



if __name__ == "__main__":
    main()
