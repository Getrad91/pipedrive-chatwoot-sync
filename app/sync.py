#!/usr/bin/env python3
"""
Simple, clean Pipedrive to Chatwoot sync you

Syncs ONLY Customer organizations (label 5) from Pipedrive to Chatwoot
"""

import os
import sys
import time
import json
import logging
import requests
import pymysql
import random
import psutil
from dotenv import load_dotenv
from contextlib import contextmanager
from typing import Dict, Optional

# Load environment variables
load_dotenv()

# Configuration
PIPEDRIVE_API_KEY = os.getenv('PIPEDRIVE_API_KEY')
CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')
PIPEDRIVE_BASE_URL = os.getenv('PIPEDRIVE_BASE_URL', 'https://api.pipedrive.com/v1')

# Performance configuration
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50'))
RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))

# Database configuration
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3307')),
    'user': os.getenv('MYSQL_USER', 'sync_user'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE', 'pipedrive_chatwoot_sync'),
    'charset': 'utf8mb4'
}

pipedrive_session = None
chatwoot_session = None
contact_cache = {}


def setup_logging():
    """Set up logging"""
    log_dir = "/home/n8n/pipedrive-chatwoot-sync/logs"
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"{log_dir}/sync.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def setup_sessions():
    """Set up persistent HTTP sessions for connection pooling"""
    global pipedrive_session, chatwoot_session

    pipedrive_session = requests.Session()
    pipedrive_session.timeout = 30

    chatwoot_session = requests.Session()
    chatwoot_session.timeout = 30

    # Configure retry adapters
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT"],
        backoff_factor=1
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    pipedrive_session.mount("http://", adapter)
    pipedrive_session.mount("https://", adapter)
    chatwoot_session.mount("http://", adapter)
    chatwoot_session.mount("https://", adapter)


def exponential_backoff_retry(func, max_retries: int = RETRY_ATTEMPTS,
                              base_delay: int = RETRY_DELAY):
    """Retry function with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logging.getLogger(__name__).warning(
                f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: "
                f"{str(e)}")
            time.sleep(delay)


@contextmanager
def get_db_connection():
    """Get database connection with context manager"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def log_performance_metrics(operation: str, start_time: float,
                            api_calls: int = 0, db_operations: int = 0):
    """Log performance metrics for operations"""
    logger = logging.getLogger(__name__)
    duration = time.time() - start_time
    memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # MB

    logger.info(f"📊 Performance - {operation}: {duration:.2f}s, "
                f"API calls: {api_calls}, DB ops: {db_operations}, "
                f"Memory: {memory_usage:.1f}MB")


def get_customer_organizations():
    """Get all Customer organizations from Pipedrive"""
    logger = logging.getLogger(__name__)
    start_time = time.time()
    organizations = []
    start = 0
    limit = 100
    api_calls = 0

    while True:
        try:
            params = {
                'api_token': PIPEDRIVE_API_KEY,
                'start': start,
                'limit': limit
            }

            def make_request():
                nonlocal api_calls
                api_calls += 1
                return pipedrive_session.get(
                    f"{PIPEDRIVE_BASE_URL}/organizations", params=params)

            response = exponential_backoff_retry(make_request)
            response.raise_for_status()

            data = response.json()
            page_orgs = data.get('data', [])

            # Filter for Customer organizations only (label 5)
            customer_orgs = [org for org in page_orgs if org.get('label') == 5]
            organizations.extend(customer_orgs)

            logger.info(f"Page {start // limit + 1}: Found "
                        f"{len(customer_orgs)} Customer organizations")

            # Check pagination
            pagination = data.get('additional_data', {}).get('pagination', {})
            if not pagination.get('more_items_in_collection', False):
                break

            start = pagination.get('next_start', start + limit)
            time.sleep(0.5)  # Reduced rate limiting

        except Exception as e:
            logger.error(f"Error fetching organizations: {e}")
            break

    log_performance_metrics("Pipedrive Fetch", start_time, api_calls)
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
        'owner_name': (org.get('owner_id', {}).get('name', '')
                       if org.get('owner_id') else ''),
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
    """Store organizations in database using batch operations"""
    logger = logging.getLogger(__name__)
    start_time = time.time()
    db_operations = 0

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Clear existing data
            cursor.execute("DELETE FROM organizations")
            db_operations += 1

            # Prepare batch insert data
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

            batch_data = []
            for i, org in enumerate(organizations):
                batch_data.append(clean_organization_data(org))

                if len(batch_data) >= BATCH_SIZE or i == len(organizations) - 1:
                    cursor.executemany(sql, batch_data)
                    db_operations += 1
                    logger.info(f"Inserted batch of {len(batch_data)} "
                                f"organizations")
                    batch_data = []

            conn.commit()
            db_operations += 1

    log_performance_metrics("Database Store", start_time, 0, db_operations)
    logger.info(f"Stored {len(organizations)} organizations in database")


def get_cached_contact_search(org_name: str) -> Optional[Dict]:
    """Get cached contact search result"""
    return contact_cache.get(org_name)


def cache_contact_search(org_name: str, contact: Optional[Dict]):
    """Cache contact search result"""
    contact_cache[org_name] = contact


def sync_to_chatwoot():
    """Sync organizations to Chatwoot with optimizations"""
    logger = logging.getLogger(__name__)
    start_time = time.time()
    api_calls = 0
    db_operations = 0

    contact_cache.clear()

    with get_db_connection() as conn:
        # Get the Customer Database inbox ID
        def get_inbox():
            nonlocal api_calls
            api_calls += 1
            inboxes_url = f"{CHATWOOT_BASE_URL}/inboxes"
            inboxes_headers = {'Api-Access-Token': CHATWOOT_API_KEY}
            return chatwoot_session.get(inboxes_url, headers=inboxes_headers)

        inboxes_response = exponential_backoff_retry(get_inbox)

        customer_database_inbox_id = None
        if inboxes_response.status_code == 200:
            inboxes_data = inboxes_response.json()
            inboxes = inboxes_data.get('payload', inboxes_data.get('data', []))
            # Find the Customer Database inbox
            for inbox in inboxes:
                if 'customer database' in inbox.get('name', '').lower():
                    customer_database_inbox_id = inbox.get('id')
                    logger.info(f"Using inbox: {inbox.get('name')} "
                                f"(ID: {customer_database_inbox_id})")
                    break

        if not customer_database_inbox_id:
            logger.warning("Could not find Customer Database inbox, "
                           "contacts may not be visible in Chatwoot interface")

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM organizations WHERE "
                           "synced_to_chatwoot = 0")
            organizations = cursor.fetchall()
            db_operations += 1

            logger.info(f"Syncing {len(organizations)} organizations to "
                        f"Chatwoot")

            synced_count = 0
            error_count = 0
            batch_updates = []

            for org in organizations:
                try:
                    existing_contact = get_cached_contact_search(org['name'])

                    if existing_contact is None:
                        # Search for existing contact
                        def search_contact():
                            nonlocal api_calls
                            api_calls += 1
                            search_url = f"{CHATWOOT_BASE_URL}/contacts/search"
                            search_params = {'q': org['name']}
                            search_headers = {'Api-Access-Token':
                                              CHATWOOT_API_KEY}
                            return chatwoot_session.get(
                                search_url, params=search_params,
                                headers=search_headers)

                        search_response = exponential_backoff_retry(
                            search_contact)

                        if search_response.status_code == 200:
                            search_data = search_response.json()
                            contacts = search_data.get(
                                'payload', search_data.get('data', []))
                            existing_contact = contacts[0] if contacts else None
                        else:
                            existing_contact = None

                        cache_contact_search(org['name'], existing_contact)

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
                    time.sleep(0.5)  # Reduced rate limiting

                    if existing_contact:
                        # Update existing contact
                        def update_contact():
                            nonlocal api_calls
                            api_calls += 1
                            update_url = (f"{CHATWOOT_BASE_URL}/contacts/"
                                          f"{existing_contact['id']}")
                            update_headers = {
                                'Api-Access-Token': CHATWOOT_API_KEY,
                                'Content-Type': 'application/json'}
                            return chatwoot_session.put(
                                update_url, json=contact_data,
                                headers=update_headers)

                        response = exponential_backoff_retry(update_contact)
                        chatwoot_id = existing_contact['id']
                    else:
                        # Create new contact
                        def create_contact():
                            nonlocal api_calls
                            api_calls += 1
                            create_url = f"{CHATWOOT_BASE_URL}/contacts"
                            create_headers = {
                                'Api-Access-Token': CHATWOOT_API_KEY,
                                'Content-Type': 'application/json'}
                            return chatwoot_session.post(
                                create_url, json=contact_data,
                                headers=create_headers)

                        response = exponential_backoff_retry(create_contact)
                        if response.status_code == 200:
                            response_data = response.json()
                            # Chatwoot API returns contact ID in
                            # payload.contact.id
                            chatwoot_id = (response_data.get('payload', {})
                                           .get('contact', {}).get('id'))
                        else:
                            chatwoot_id = None

                    if response.status_code in [200, 201]:
                        # Assign contact to Customer Database inbox if we have
                        # the inbox ID
                        if chatwoot_id and customer_database_inbox_id:
                            try:
                                def assign_contact():
                                    nonlocal api_calls
                                    api_calls += 1
                                    assign_url = (f"{CHATWOOT_BASE_URL}/"
                                                  f"contacts/{chatwoot_id}/"
                                                  f"contact_inboxes")
                                    assign_data = {
                                        'inbox_id': customer_database_inbox_id,
                                        'source_id': f'pipedrive_{chatwoot_id}'
                                    }
                                    assign_headers = {
                                        'Api-Access-Token': CHATWOOT_API_KEY,
                                        'Content-Type': 'application/json'
                                    }
                                    return chatwoot_session.post(
                                        assign_url, json=assign_data,
                                        headers=assign_headers)

                                assign_response = exponential_backoff_retry(
                                    assign_contact)
                                if assign_response.status_code == 200:
                                    logger.info(f"✅ Assigned {org['name']} to "
                                                f"Customer Database inbox")
                                else:
                                    logger.warning(
                                        f"⚠️ Could not assign {org['name']} "
                                        f"to inbox: "
                                        f"{assign_response.status_code}")
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to assign "
                                               f"{org['name']} to inbox: "
                                               f"{str(e)}")

                        batch_updates.append((chatwoot_id,
                                              org['pipedrive_org_id']))
                        synced_count += 1
                        logger.info(f"✅ Synced: {org['name']} → "
                                    f"Chatwoot ID {chatwoot_id}")

                        if len(batch_updates) >= BATCH_SIZE:
                            cursor.executemany(
                                "UPDATE organizations SET "
                                "synced_to_chatwoot = 1, "
                                "chatwoot_contact_id = %s WHERE "
                                "pipedrive_org_id = %s",
                                batch_updates
                            )
                            db_operations += 1
                            batch_updates = []
                    else:
                        error_count += 1
                        logger.error(f"❌ Failed to sync: {org['name']} - "
                                     f"{response.status_code}")
                        logger.error(f"Response text: {response.text}")

                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Error syncing {org['name']}: {e}")
                    import traceback
                    logger.error(f"Full error: {traceback.format_exc()}")

            if batch_updates:
                cursor.executemany(
                    "UPDATE organizations SET synced_to_chatwoot = 1, "
                    "chatwoot_contact_id = %s WHERE pipedrive_org_id = %s",
                    batch_updates
                )
                db_operations += 1

            conn.commit()
            db_operations += 1

    log_performance_metrics("Chatwoot Sync", start_time, api_calls,
                            db_operations)
    logger.info(f"Sync completed: {synced_count} synced, {error_count} errors")
    logger.info(f"Contact cache size: {len(contact_cache)} entries")


def main():
    """Main function with performance monitoring"""
    logger = setup_logging()
    overall_start_time = time.time()

    logger.info("🚀 Starting Pipedrive to Chatwoot sync")
    logger.info("=" * 50)

    setup_sessions()
    logger.info("🔗 HTTP sessions initialized for connection pooling")

    try:
        # Step 1: Get Customer organizations from Pipedrive
        logger.info("📥 Fetching Customer organizations from Pipedrive...")
        organizations = get_customer_organizations()

        if not organizations:
            logger.error("❌ No Customer organizations found")
            return

        # Step 2: Store in database
        logger.info("💾 Storing organizations in database...")
        store_organizations(organizations)

        # Step 3: Sync to Chatwoot
        logger.info("🔄 Syncing organizations to Chatwoot...")
        sync_to_chatwoot()

        total_duration = time.time() - overall_start_time
        final_memory = (psutil.Process().memory_info().rss / 1024 / 1024)
        logger.info("=" * 50)
        logger.info(f"🏁 Total sync duration: {total_duration:.2f}s")
        logger.info(f"💾 Final memory usage: {final_memory:.1f}MB")
        logger.info(f"📊 Contact cache entries: {len(contact_cache)}")
        logger.info("✅ Sync completed!")

    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        import traceback
        logger.error(f"Full error: {traceback.format_exc()}")
        raise
    finally:
        if pipedrive_session:
            pipedrive_session.close()
        if chatwoot_session:
            chatwoot_session.close()
        logger.info("🔌 HTTP sessions closed")


if __name__ == "__main__":
    main()
