#!/usr/bin/env python3
"""
Production-ready one-time fix for incorrect inbox assignments.

This script fixes inbox assignments with:
- Structured logging with rotating file handlers
- Connection pooling with requests.Session
- Cross-checks existing contacts' inbox assignments
- Reassigns contacts where mismatch is found
- Handles large datasets efficiently with batching
- Logs all corrections (old inbox → new inbox)
- Dry-run mode (--dry-run flag) to preview changes before execution
- Error handling with retries and exponential backoff
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

SCRIPT_NAME = "fix_inbox_assignment"

@retry_with_backoff()
def get_inboxes(session, logger):
    """Get all available inboxes"""
    inboxes_url = f"{CHATWOOT_BASE_URL}/inboxes"
    response = session.get(inboxes_url, timeout=30)
    
    if response.status_code == 200:
        inboxes_data = response.json()
        inboxes = inboxes_data.get('payload', inboxes_data.get('data', []))
        return inboxes
    else:
        logger.error(f"Failed to fetch inboxes: {response.status_code}")
        return []

def find_support_inbox(inboxes, logger):
    """Find the support inbox from available inboxes"""
    for inbox in inboxes:
        inbox_name = inbox.get('name', '').lower()
        if 'support' in inbox_name or inbox.get('channel_type') == 'Channel::Email':
            logger.info(f"Found support inbox: {inbox.get('name')} (ID: {inbox.get('id')})")
            return inbox.get('id'), inbox.get('name')
    
    logger.warning("Could not find support inbox")
    return None, None

@retry_with_backoff()
def get_contact_inboxes(session, contact_id, logger):
    """Get current inbox assignments for a contact"""
    url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/contact_inboxes"
    response = session.get(url, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        return data.get('payload', data.get('data', []))
    else:
        logger.debug(f"Could not fetch inbox assignments for contact {contact_id}: {response.status_code}")
        return []

@retry_with_backoff()
def assign_contact_to_inbox(session, contact_id, inbox_id, contact_name, logger):
    """Assign a contact to an inbox with retry logic"""
    assign_url = f"{CHATWOOT_BASE_URL}/contacts/{contact_id}/contact_inboxes"
    assign_data = {'inbox_id': inbox_id}
    
    response = session.post(assign_url, json=assign_data, timeout=30)
    if response.status_code == 200:
        logger.info(f"✅ Assigned {contact_name} to inbox {inbox_id}")
        return True
    else:
        logger.error(f"Could not assign {contact_name} to inbox {inbox_id}: {response.status_code} - {response.text}")
        return False

def check_and_fix_contact(session, contact, target_inbox_id, inbox_name, dry_run, logger):
    """Check and fix inbox assignment for a single contact"""
    contact_name = contact['name']
    contact_id = contact['chatwoot_contact_id']
    
    current_inboxes = get_contact_inboxes(session, contact_id, logger)
    current_inbox_ids = [inbox.get('inbox_id') for inbox in current_inboxes]
    
    if target_inbox_id in current_inbox_ids:
        logger.debug(f"✅ {contact_name} already assigned to {inbox_name}")
        return 'skipped'
    
    old_inboxes = ', '.join([str(id) for id in current_inbox_ids]) if current_inbox_ids else 'None'
    logger.info(f"🔧 {contact_name}: {old_inboxes} → {target_inbox_id}")
    
    if dry_run:
        logger.info(f"[DRY RUN] Would assign {contact_name} to {inbox_name}")
        return 'would_fix'
    
    if assign_contact_to_inbox(session, contact_id, target_inbox_id, contact_name, logger):
        return 'fixed'
    else:
        return 'failed'

def process_contact_batch(session, contacts_batch, target_inbox_id, inbox_name, dry_run, logger, progress_reporter):
    """Process a batch of contacts for inbox assignment checking/fixing"""
    for contact in contacts_batch:
        progress_reporter.log_progress()
        
        try:
            result = check_and_fix_contact(session, contact, target_inbox_id, inbox_name, dry_run, logger)
            
            if result == 'fixed' or result == 'would_fix':
                progress_reporter.update(success=True)
            elif result == 'skipped':
                progress_reporter.update(skipped=True)
            else:
                progress_reporter.update(failed=True)
                
        except Exception as e:
            logger.error(f"Error processing {contact['name']}: {e}")
            progress_reporter.update(failed=True)
        
        time.sleep(0.5)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Fix inbox assignments for existing contacts')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Preview changes without making actual assignments')
    parser.add_argument('--target-inbox-id', type=int, 
                       help='Specific inbox ID to assign contacts to (auto-detects support inbox if not provided)')
    parser.add_argument('--batch-size', type=int, help='Batch size for processing contacts')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Logging level')
    args = parser.parse_args()
    
    logger = setup_logging(SCRIPT_NAME)
    if args.log_level:
        logger.setLevel(getattr(logging, args.log_level))
    
    mode_text = "DRY RUN - " if args.dry_run else ""
    logger.info(f"🔧 {mode_text}Starting inbox assignment fix")
    logger.info("=" * 60)
    
    session = get_http_session()
    
    if not validate_api_token(session, logger):
        logger.error("❌ API token validation failed. Exiting.")
        return 1
    
    if args.target_inbox_id:
        target_inbox_id = args.target_inbox_id
        inbox_name = f"Inbox {target_inbox_id}"
        logger.info(f"📧 Using specified inbox: {inbox_name}")
    else:
        inboxes = get_inboxes(session, logger)
        if not inboxes:
            logger.error("❌ Could not fetch inboxes")
            return 1
        
        target_inbox_id, inbox_name = find_support_inbox(inboxes, logger)
        if not target_inbox_id:
            logger.error("❌ Could not find support inbox")
            return 1
    
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT name, chatwoot_contact_id FROM organizations WHERE chatwoot_contact_id IS NOT NULL")
            contacts = cursor.fetchall()
            
            if not contacts:
                logger.info("No contacts found to process")
                return 0
            
            logger.info(f"📊 Found {len(contacts)} contacts to check")
            
            operation_name = "Checking inbox assignments (DRY RUN)" if args.dry_run else "Fixing inbox assignments"
            progress_reporter = ProgressReporter(len(contacts), logger, operation_name)
            batch_size = args.batch_size if args.batch_size else None
            
            for batch in process_in_batches(contacts, batch_size):
                process_contact_batch(session, batch, target_inbox_id, inbox_name, args.dry_run, logger, progress_reporter)
            
            progress_reporter.log_summary()
            
            if args.dry_run:
                logger.info("🔍 Dry run completed. Use without --dry-run to apply changes.")
            elif progress_reporter.successful > 0:
                logger.info(f"🎉 Successfully fixed {progress_reporter.successful} contact assignments")
            
    except Exception as e:
        logger.error(f"Database error: {e}")
        return 1
    finally:
        conn.close()
        session.close()
    
    return 0

if __name__ == "__main__":
    exit(main())
