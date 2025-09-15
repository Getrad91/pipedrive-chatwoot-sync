#!/usr/bin/env python3
"""
Simple, clean Pipedrive to Chatwoot sync

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


def get_organization_phone_number(org_id):
    """Get phone number for an organization from custom fields first, then associated persons"""
    logger = logging.getLogger(__name__)

    try:
        # Step 1: Check organization-level custom fields first
        org_params = {'api_token': PIPEDRIVE_API_KEY}
        org_response = requests.get(f"{PIPEDRIVE_BASE_URL}/organizations/{org_id}", 
                                   params=org_params, timeout=30)
        
        if org_response.status_code == 200:
            org_data = org_response.json().get('data', {})
            
            main_phone_hash = 'a677b0cd218332b9f490ce565603a8d2efc2ff65'
            main_phone = org_data.get(main_phone_hash, '').strip()
            
            if main_phone:
                logger.info(f"Found Main Phone Number custom field for org {org_id}: {main_phone}")
                return main_phone
            
            for key, value in org_data.items():
                if value and isinstance(value, str):
                    if ('phone' in key.lower() or 'main' in key.lower()) and any(char.isdigit() for char in value):
                        logger.info(f"Found phone in custom field {key} for org {org_id}: {value}")
                        return value.strip()

        # Step 2: Fall back to person-level phone data (existing logic)
        logger.debug(f"No organization-level phone found for org {org_id}, checking persons...")
        
        params = {
            'api_token': PIPEDRIVE_API_KEY,
            'org_id': org_id
        }

        response = requests.get(f"{PIPEDRIVE_BASE_URL}/persons", params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        persons = data.get('data', [])

        for person in persons:
            phone_data = person.get('phone', [])
            if phone_data and isinstance(phone_data, list):
                primary_phone = None
                first_phone = None

                for phone_entry in phone_data:
                    if isinstance(phone_entry, dict):
                        phone_value = phone_entry.get('value', '').strip()
                        if phone_value:
                            if not first_phone:
                                first_phone = phone_value
                            if phone_entry.get('primary', False):
                                primary_phone = phone_value
                                break

                if primary_phone:
                    logger.info(f"Found primary phone from person for org {org_id}: {primary_phone}")
                    return primary_phone
                elif first_phone:
                    logger.info(f"Found phone from person for org {org_id}: {first_phone}")
                    return first_phone

        logger.info(f"No phone number found for org {org_id}")
        return ""

    except Exception as e:
        logger.error(f"Error fetching phone for org {org_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return ""


def get_organizations_phone_numbers_batch(org_ids):
    """Get phone numbers for multiple organizations, checking custom fields first, then persons"""
    logger = logging.getLogger(__name__)
    phone_map = {}
    
    # First, check organization-level custom fields for all organizations
    logger.info("Checking organization-level custom fields for phone numbers...")
    for org_id in org_ids:
        try:
            org_params = {'api_token': PIPEDRIVE_API_KEY}
            org_response = requests.get(f"{PIPEDRIVE_BASE_URL}/organizations/{org_id}", 
                                       params=org_params, timeout=30)
            
            if org_response.status_code == 200:
                org_data = org_response.json().get('data', {})
                
                main_phone_hash = 'a677b0cd218332b9f490ce565603a8d2efc2ff65'
                main_phone = org_data.get(main_phone_hash, '').strip()
                
                if main_phone:
                    phone_map[org_id] = main_phone
                    logger.info(f"Found Main Phone Number custom field for org {org_id}: {main_phone}")
                    continue
                
                for key, value in org_data.items():
                    if value and isinstance(value, str):
                        if ('phone' in key.lower() or 'main' in key.lower()) and any(char.isdigit() for char in value):
                            phone_map[org_id] = value.strip()
                            logger.info(f"Found phone in custom field {key} for org {org_id}: {value}")
                            break
            
            time.sleep(0.2)  # Small delay to avoid rate limiting
            
        except Exception as e:
            logger.error(f"Error checking custom fields for org {org_id}: {e}")
    
    remaining_org_ids = [org_id for org_id in org_ids if org_id not in phone_map]
    
    if remaining_org_ids:
        logger.info(f"Checking person-level phone data for {len(remaining_org_ids)} organizations...")
        batch_size = 20  # Process in smaller batches to avoid URL length limits

        for i in range(0, len(remaining_org_ids), batch_size):
            batch_org_ids = remaining_org_ids[i:i + batch_size]

            try:
                params = {
                    'api_token': PIPEDRIVE_API_KEY,
                    'org_id': ','.join(batch_org_ids),
                    'limit': 500  # Increase limit to get more persons per request
                }

                response = requests.get(f"{PIPEDRIVE_BASE_URL}/persons", params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                persons = data.get('data', [])

                logger.info(f"Person batch {i // batch_size + 1}: Fetched {len(persons)} persons "
                            f"for {len(batch_org_ids)} organizations")

                org_phones = {}
                for person in persons:
                    org_id = person.get('org_id', {})
                    if isinstance(org_id, dict):
                        org_id_value = str(org_id.get('value', ''))
                    else:
                        org_id_value = str(org_id) if org_id else ''

                    if org_id_value and org_id_value in batch_org_ids:
                        phone_data = person.get('phone', [])
                        if phone_data and isinstance(phone_data, list):
                            for phone_entry in phone_data:
                                if isinstance(phone_entry, dict):
                                    phone_value = phone_entry.get('value', '').strip()
                                    if phone_value:
                                        if org_id_value not in org_phones:
                                            org_phones[org_id_value] = phone_value
                                        elif phone_entry.get('primary', False):
                                            org_phones[org_id_value] = phone_value
                                            break

                phone_map.update(org_phones)

                if i + batch_size < len(remaining_org_ids):
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error fetching phones for person batch {i // batch_size + 1}: {e}")
                for org_id in batch_org_ids:
                    if org_id not in phone_map:
                        phone_map[org_id] = get_organization_phone_number(org_id)
                        time.sleep(0.5)

    logger.info(f"Retrieved phone numbers for {len(phone_map)} out of {len(org_ids)} organizations")
    return phone_map


def get_last_sync_timestamp():
    """Get the last sync timestamp for incremental sync"""
    logger = logging.getLogger(__name__)
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT last_sync_timestamp FROM sync_metadata WHERE sync_type = 'organizations'"
            )
            result = cursor.fetchone()
            if result and result[0]:
                logger.info(f"Last sync timestamp: {result[0]}")
                return result[0].strftime('%Y-%m-%d %H:%M:%S')
            else:
                logger.info("No previous sync timestamp found, performing full sync")
                return None
    except Exception as e:
        logger.warning(f"Error getting last sync timestamp: {e}")
        return None
    finally:
        conn.close()


def update_sync_timestamp():
    """Update the last sync timestamp"""
    logger = logging.getLogger(__name__)
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO sync_metadata (sync_type, last_sync_timestamp)
                VALUES ('organizations', NOW())
                ON DUPLICATE KEY UPDATE
                last_sync_timestamp = NOW()
            """)
            conn.commit()
            logger.info("Updated sync timestamp")
    except Exception as e:
        logger.error(f"Error updating sync timestamp: {e}")
    finally:
        conn.close()


def get_customer_organizations():
    """Get Customer organizations from Pipedrive with incremental sync support"""
    logger = logging.getLogger(__name__)
    organizations = []
    start = 0
    limit = 100

    since_timestamp = get_last_sync_timestamp()

    if since_timestamp:
        logger.info(f"🔄 Performing incremental sync since: {since_timestamp}")
    else:
        logger.info("🔄 Performing full sync (no previous timestamp)")

    while True:
        try:
            params = {
                'api_token': PIPEDRIVE_API_KEY,
                'start': start,
                'limit': limit
            }

            if since_timestamp:
                params['since'] = since_timestamp

            response = requests.get(f"{PIPEDRIVE_BASE_URL}/organizations", params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            page_orgs = data.get('data', [])

            if not page_orgs:
                logger.info("No organizations returned from API")
                break

            # Filter for Customer organizations only (label 5)
            customer_orgs = [org for org in page_orgs if org.get('label') == 5]

            if customer_orgs:
                org_ids = [str(org['id']) for org in customer_orgs]
                phone_map = get_organizations_phone_numbers_batch(org_ids)

                for org in customer_orgs:
                    org_id = org['id']
                    org['phone'] = phone_map.get(str(org_id), '')
                    logger.debug(f"Org {org_id} ({org.get('name', 'Unknown')}) "
                                 f"phone: {repr(org['phone'])}")

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

    if organizations or since_timestamp:
        update_sync_timestamp()

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
    """Normalize phone number to Australian format"""
    if not phone:
        return ""

    phone = "".join(c for c in phone if c.isdigit() or c in "+() -")

    phone = "".join(c for c in phone if c.isdigit() or c == "+")

    if not phone:
        return ""

    if not phone.startswith("+"):
        phone = phone.lstrip("0")
        phone = "+61" + phone

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
            cursor.execute("TRUNCATE TABLE organizations")

            # Insert new data in batches to avoid long transactions
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

            batch_size = int(os.getenv('BATCH_SIZE', 50))
            for i in range(0, len(organizations), batch_size):
                batch = organizations[i:i + batch_size]
                for org in batch:
                    cleaned_data = clean_organization_data(org)
                    logger.debug(f"Storing org {cleaned_data['name']} with phone: {repr(cleaned_data['phone'])}")
                    cursor.execute(sql, cleaned_data)
                conn.commit()  # Commit each batch
                logger.info(f"Stored batch {i // batch_size + 1}: {len(batch)} organizations")

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
            used_phone_numbers = set()

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

                    # Handle duplicate phone numbers by making them optional for subsequent organizations
                    normalized_phone = org['phone'] if org['phone'] else None
                    if normalized_phone and normalized_phone in used_phone_numbers:
                        logger.info(f"Phone number {normalized_phone} already used, "
                                    f"syncing {org['name']} without phone number")
                        normalized_phone = None  # Don't include phone for duplicates
                    elif normalized_phone:
                        used_phone_numbers.add(normalized_phone)

                    # Prepare contact data
                    contact_data = {
                        'name': org['name'],
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

                    if normalized_phone:
                        contact_data['phone_number'] = normalized_phone

                    # Create or update contact
                    time.sleep(1)  # Rate limiting

                    if existing_contact:
                        # Update existing contact
                        update_url = f"{CHATWOOT_BASE_URL}/contacts/{existing_contact['id']}"
                        update_headers = {'Api-Access-Token': CHATWOOT_API_KEY,
                                          'Content-Type': 'application/json'}

                        response = requests.put(update_url, json=contact_data,
                                                headers=update_headers, timeout=30)
                        chatwoot_id = existing_contact['id']
                    else:
                        # Create new contact
                        create_url = f"{CHATWOOT_BASE_URL}/contacts"
                        create_headers = {'Api-Access-Token': CHATWOOT_API_KEY,
                                          'Content-Type': 'application/json'}

                        response = requests.post(create_url, json=contact_data,
                                                 headers=create_headers, timeout=30)
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
                                if assign_response.status_code == 200:
                                    logger.info(f"✅ Assigned {org['name']} to Customer Database inbox")
                                else:
                                    logger.warning(
                                        f"⚠️ Could not assign {org['name']} to inbox: "
                                        f"{assign_response.status_code}")
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to assign {org['name']} to inbox: {str(e)}")

                        # Mark as synced
                        cursor.execute(
                            "UPDATE organizations SET synced_to_chatwoot = 1, "
                            "chatwoot_contact_id = %s WHERE pipedrive_org_id = %s",
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
