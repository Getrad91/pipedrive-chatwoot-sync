#!/usr/bin/env python3
"""
Production-ready maintenance script to clean/remove all contacts from Chatwoot.

This script provides safe contact cleanup with:
- Structured logging with rotating file handlers
- Connection pooling with requests.Session
- Safeguard: requires explicit --confirm flag before deletion
- Batch deletion to avoid rate-limit issues
- Logs all deleted contact IDs for audit trail
- Error handling with retries and exponential backoff
"""

import time
import logging
import argparse
from utils.common import (
    setup_logging, get_http_session, retry_with_backoff,
    process_in_batches, ProgressReporter, CHATWOOT_BASE_URL,
    validate_api_token
)

SCRIPT_NAME = "clean_chatwoot"


@retry_with_backoff()
def get_contacts_page(session, page, per_page, logger):
    """Get a page of contacts from Chatwoot with retry logic"""
    url = f"{CHATWOOT_BASE_URL}/contacts"
    params = {'page': page, 'per_page': per_page}

    logger.debug(f"Fetching page {page}...")
    response = session.get(url, params=params, timeout=30)

    if response.status_code != 200:
        logger.error(f"Error fetching page {page}: {response.status_code}")
        return []

    data = response.json()
    contacts = data.get('payload', data.get('data', []))
    logger.debug(f"Found {len(contacts)} contacts on page {page}")

    return contacts


def get_all_contacts(session, logger):
    """Get all contacts from Chatwoot with pagination"""
    all_contacts = []
    page = 1
    per_page = 50

    logger.info("📄 Fetching all contacts from Chatwoot...")

    while True:
        contacts = get_contacts_page(session, page, per_page, logger)

        if not contacts:
            logger.info("✅ No more contacts found")
            break

        all_contacts.extend(contacts)
        logger.info(f"Page {page}: Found {len(contacts)} contacts (Total: {len(all_contacts)})")

        page += 1
        time.sleep(0.5)

    return all_contacts


@retry_with_backoff()
def delete_contact(session, contact_id, contact_name, logger):
    """Delete a single contact with retry logic"""
    url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}"

    response = session.delete(url, timeout=30)

    if response.status_code in [200, 204]:
        logger.info(f"✅ Deleted contact: {contact_name} (ID: {contact_id})")
        return True
    else:
        logger.error(f"Failed to delete {contact_name} (ID: {contact_id}): {response.status_code}")
        return False


def process_deletion_batch(session, contacts_batch, logger, progress_reporter):
    """Process a batch of contacts for deletion"""
    for contact in contacts_batch:
        contact_id = contact['id']
        contact_name = contact.get('name', f'Contact {contact_id}')

        progress_reporter.log_progress()

        try:
            if delete_contact(session, contact_id, contact_name, logger):
                progress_reporter.update(success=True)
            else:
                progress_reporter.update(failed=True)
        except Exception as e:
            logger.error(f"Error deleting {contact_name}: {e}")
            progress_reporter.update(failed=True)

        time.sleep(0.5)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Clean all contacts from Chatwoot')
    parser.add_argument('--confirm', action='store_true', required=True,
                        help='Required flag to confirm deletion of ALL contacts')
    parser.add_argument('--batch-size', type=int,
                        help='Batch size for deletion processing')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level')
    args = parser.parse_args()

    logger = setup_logging(SCRIPT_NAME)
    if args.log_level:
        logger.setLevel(getattr(logging, args.log_level))

    logger.info("🧹 Starting Chatwoot Contact Cleanup")
    logger.info("=" * 50)

    if not args.confirm:
        logger.error("❌ --confirm flag is required to proceed with deletion")
        return 1

    session = get_http_session()

    if not validate_api_token(session, logger):
        logger.error("❌ API token validation failed. Exiting.")
        return 1

    try:
        contacts = get_all_contacts(session, logger)

        if not contacts:
            logger.info("✅ No contacts found to delete")
            return 0

        logger.info(f"📊 Found {len(contacts)} contacts to delete")
        logger.warning("⚠️ This will DELETE ALL contacts from Chatwoot!")

        final_confirm = input(f"\nType 'DELETE ALL {len(contacts)} CONTACTS' to proceed: ")
        if final_confirm != f"DELETE ALL {len(contacts)} CONTACTS":
            logger.info("❌ Operation cancelled by user")
            return 0

        logger.info("🗑️ Starting contact deletion...")

        progress_reporter = ProgressReporter(len(contacts), logger, "Deleting contacts")
        batch_size = args.batch_size if args.batch_size else None

        for batch in process_in_batches(contacts, batch_size):
            process_deletion_batch(session, batch, logger, progress_reporter)

        progress_reporter.log_summary()

        if progress_reporter.successful > 0:
            logger.info(f"🎉 Successfully deleted {progress_reporter.successful} contacts")

        if progress_reporter.failed > 0:
            logger.warning(f"⚠️ Failed to delete {progress_reporter.failed} contacts")

    except KeyboardInterrupt:
        logger.info("❌ Operation cancelled by user (Ctrl+C)")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    exit(main())
