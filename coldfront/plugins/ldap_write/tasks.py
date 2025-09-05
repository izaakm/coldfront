import logging
import os
from django.core.management import call_command
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

#This task prevents the sync_ldap_users command from running multiple times at the same time.
#Based on django_q scheduler
#A preventative measure

def sync_ldap_users_task():
    """
    Task function to run LDAP user sync with overlap prevention.
    """
    lock_key = "ldap_sync_running"
    lock_timeout = 3600  # 1 hour
    
    # Check if sync is already running
    if cache.get(lock_key):
        logger.warning("LDAP sync already running - skipping execution")
        return "LDAP sync skipped - already running"
    
    try:
        # Acquire lock with current timestamp and PID
        cache.set(lock_key, f"{timezone.now()}:{os.getpid()}", lock_timeout)
        logger.info("Starting scheduled LDAP user sync...")
        
        call_command('sync_ldap_users')
        
        logger.info("Scheduled LDAP user sync completed successfully")
        return "LDAP sync completed successfully"
    except Exception as e:
        logger.error(f"Scheduled LDAP user sync failed: {e}")
        raise
    finally:
        cache.delete(lock_key)