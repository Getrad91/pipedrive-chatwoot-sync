#!/usr/bin/env python3
"""
Production-ready script to sync Common Support Link from Pipedrive to Chatwoot.

This script syncs common support links (specialized feature) with:
- Structured logging with rotating file handlers
- Connection pooling with requests.Session
- Error handling with retries and exponential backoff
- Batch API calls for efficiency
- Configurable via .env file
- Proper label/custom attribute persistence
"""

import json
import time
import logging
import argparse
import pymysql
from utils.common import (
    setup_logging, get_db_connection, get_http_session,
    retry_with_backoff, process_in_batches, ProgressReporter,
    CHATWOOT_BASE_URL, validate_api_token
)

SCRIPT_NAME = "sync_common_support"

@retry_with_backoff()
def sync_common_support(session, contact_id, contact_name, common_support_link, logger):
    """Sync Common Support Link to Chatwoot with retry logic"""
    update_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}"

    get_response = session.get(update_url, timeout=30)

    if get_response.status_code != 200:
        logger.warning(f"Could not fetch {contact_name}: {get_response.status_code}")
        return False

    current_data = get_response.json()['payload']
    current_additional_attrs = current_data.get('additional_attributes', {})
    current_custom_attrs = current_data.get('custom_attributes', {})

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

    response = session.put(update_url, json=update_data, timeout=30)
    if response.status_code == 200:
        if common_support_link and common_support_link != 'None':
            logger.info(f"✅ Updated {contact_name}: Common Support Link synced")
        else:
            logger.info(f"✅ Updated {contact_name}: No Common Support Link to sync")
        return True
    else:
        logger.error(f"Failed to update {contact_name}: {response.status_code} - {response.text}")
        return False


def process_contact_batch(session, contacts_batch, logger, progress_reporter):
    """Process a batch of contacts"""
    for contact in contacts_batch:
        contact_name = contact['name']
        contact_id = contact['chatwoot_contact_id']

        progress_reporter.log_progress()
        logger.info(f"Processing: {contact_name}")

        try:
            pipedrive_data = json.loads(contact['data'])
            common_support_link = pipedrive_data.get('f9c6c562ac9d61e1880fe4b5675d3a64f2bbcc6c', '')

            if common_support_link and common_support_link != 'None':
                if sync_common_support(session, contact_id, contact_name, common_support_link, logger):
                    progress_reporter.update(success=True)
                else:
                    progress_reporter.update(failed=True)
            else:
                logger.info(f"No Common Support Link found for {contact_name}")
                progress_reporter.update(skipped=True)

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON data for {contact_name}")
            progress_reporter.update(failed=True)
        except Exception as e:
            logger.error(f"Error processing {contact_name}: {e}")
            progress_reporter.update(failed=True)

        time.sleep(0.3)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Sync Common Support Links from Pipedrive to Chatwoot')
    parser.add_argument('--batch-size', type=int, 
                        help='Batch size for processing contacts')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                        help='Logging level')
    args = parser.parse_args()

    logger = setup_logging(SCRIPT_NAME)
    if args.log_level:
        logger.setLevel(getattr(logging, args.log_level))

    logger.info("🔧 Starting Common Support Link sync to Chatwoot")
    logger.info("=" * 60)

    session = get_http_session()

    if not validate_api_token(session, logger):
        logger.error("❌ API token validation failed. Exiting.")
        return 1

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT name, chatwoot_contact_id, data
                FROM organizations
                WHERE chatwoot_contact_id IS NOT NULL AND data IS NOT NULL
                ORDER BY name
            """)
            contacts = cursor.fetchall()

            if not contacts:
                logger.info("No contacts found to sync")
                return 0

            logger.info(f"📊 Found {len(contacts)} contacts to sync")

            progress_reporter = ProgressReporter(len(contacts), logger, 
                                                "Syncing Common Support Links")
            batch_size = args.batch_size if args.batch_size else None

            for batch in process_in_batches(contacts, batch_size):
                process_contact_batch(session, batch, logger, progress_reporter)

            progress_reporter.log_summary()

            if progress_reporter.successful > 0:
                logger.info("🎉 Common Support Links have been synced to Chatwoot!")
                logger.info("Check the Chatwoot interface for the updated "
                          "Common Support fields.")

    except Exception as e:
        logger.error(f"Database error: {e}")
        return 1
    finally:
        conn.close()
        session.close()

    return 0


if __name__ == "__main__":
    exit(main())
