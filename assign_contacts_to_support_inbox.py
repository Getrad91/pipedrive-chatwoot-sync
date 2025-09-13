#!/usr/bin/env python3
"""
Production-ready script to assign contacts to a specific support inbox.

This script assigns contacts to support inbox with:
- Structured logging with rotating file handlers
- Connection pooling with requests.Session
- API token permission validation
- Batch assignment processing for efficiency
- Comprehensive summary reporting (assigned, failed, skipped)
- Error handling with retries and exponential backoff
- Handles partial failures without halting execution
"""

import time
import logging
import argparse
import pymysql
from utils.common import (
    setup_logging, get_db_connection, get_http_session,
    retry_with_backoff, process_in_batches, ProgressReporter,
    CHATWOOT_BASE_URL, validate_api_token
)

SCRIPT_NAME = "assign_contacts_to_support_inbox"
CUSTOMER_DATABASE_INBOX_ID = 9


@retry_with_backoff()
def assign_contact_to_inbox(session, contact_id, contact_name, inbox_id, logger):
    """Assign a contact to the specified inbox with retry logic"""
    assign_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/contact_inboxes"
    assign_data = {
        'inbox_id': inbox_id,
        'source_id': f'pipedrive_{contact_id}'
    }

    response = session.post(assign_url, json=assign_data, timeout=30)
    if response.status_code == 200:
        logger.info(f"✅ Assigned {contact_name} to inbox {inbox_id}")
        return True
    else:
        logger.error(f"Could not assign {contact_name} to inbox {inbox_id}: {response.status_code} - {response.text}")
        return False


def get_inbox_info(session, inbox_id, logger):
    """Get inbox information for validation"""
    try:
        inboxes_url = f"{CHATWOOT_BASE_URL}/inboxes"
        response = session.get(inboxes_url, timeout=30)

        if response.status_code == 200:
            inboxes_data = response.json()
            inboxes = inboxes_data.get('payload', inboxes_data.get('data', []))

            for inbox in inboxes:
                if inbox.get('id') == inbox_id:
                    return inbox.get('name', f'Inbox {inbox_id}')

        logger.warning(f"Could not find inbox with ID {inbox_id}")
        return f"Inbox {inbox_id}"
    except Exception as e:
        logger.error(f"Error fetching inbox info: {e}")
        return f"Inbox {inbox_id}"


def process_contact_batch(session, contacts_batch, inbox_id, logger, progress_reporter):
    """Process a batch of contacts for inbox assignment"""
    for contact in contacts_batch:
        contact_name = contact['name']
        contact_id = contact['chatwoot_contact_id']

        progress_reporter.log_progress()
        logger.info(f"Processing: {contact_name} (ID: {contact_id})")

        try:
            if assign_contact_to_inbox(session, contact_id, contact_name, inbox_id, logger):
                progress_reporter.update(success=True)
            else:
                progress_reporter.update(failed=True)
        except Exception as e:
            logger.error(f"Error assigning {contact_name}: {e}")
            progress_reporter.update(failed=True)

        time.sleep(0.5)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Assign contacts to support inbox')
    parser.add_argument('--inbox-id', type=int, default=CUSTOMER_DATABASE_INBOX_ID,
                        help=f'Target inbox ID (default: {CUSTOMER_DATABASE_INBOX_ID})')
    parser.add_argument('--batch-size', type=int,
                        help='Batch size for processing contacts')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level')
    args = parser.parse_args()

    logger = setup_logging(SCRIPT_NAME)
    if args.log_level:
        logger.setLevel(getattr(logging, args.log_level))

    logger.info("🔧 Starting contact assignment to support inbox")
    logger.info("=" * 60)

    session = get_http_session()

    if not validate_api_token(session, logger):
        logger.error("❌ API token validation failed. Exiting.")
        return 1

    inbox_name = get_inbox_info(session, args.inbox_id, logger)
    logger.info(f"📧 Target inbox: {inbox_name} (ID: {args.inbox_id})")

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT name, chatwoot_contact_id FROM organizations WHERE chatwoot_contact_id IS NOT NULL")
            contacts = cursor.fetchall()

            if not contacts:
                logger.info("No contacts found to assign")
                return 0

            logger.info(f"📊 Found {len(contacts)} contacts to assign")

            progress_reporter = ProgressReporter(len(contacts), logger,
                                                 "Assigning contacts to inbox")
            batch_size = args.batch_size if args.batch_size else None

            for batch in process_in_batches(contacts, batch_size):
                process_contact_batch(session, batch, args.inbox_id, logger, progress_reporter)

            progress_reporter.log_summary()

            if progress_reporter.successful > 0:
                base_url = CHATWOOT_BASE_URL.replace('/api/v1/accounts/2',
                                                     '/app/accounts/2/contacts')
                logger.info(f"🔍 Check the contacts at: {base_url}")

    except Exception as e:
        logger.error(f"Database error: {e}")
        return 1
    finally:
        conn.close()
        session.close()

    return 0


if __name__ == "__main__":
    exit(main())
