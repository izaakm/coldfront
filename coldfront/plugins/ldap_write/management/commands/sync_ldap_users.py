import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
from coldfront.core.user.models import UserProfile
from coldfront.plugins.ldap_write.ldap_client import LDAPClient
from coldfront.core.utils.mail import send_email
from coldfront.core.utils.common import import_from_settings

logger = logging.getLogger(__name__)

# Email settings
EMAIL_ENABLED = import_from_settings('EMAIL_ENABLED', False)
EMAIL_SENDER = import_from_settings('EMAIL_SENDER')

# Email notification tracking settings
NOTIFICATION_COOLDOWN_DAYS = 30  # Don't re-notify for 30 days to prevent spam

class Command(BaseCommand):
    help = 'Sync users from ColdFront database to HPSC LDAP directory'

    def add_arguments(self, parser):

        #useful for testing without actually creating users in LDAP
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show what would be done without actually creating users in LDAP'
        )

        #created to allow a short ldap sync test with limited # of users
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of users to process (useful for testing)'
        )

        #to sync a specific user
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='Process only a specific user by username'
        )

    def should_notify_restricted_user(self, username):
        """Check if we should send email notification for restricted user"""
        cache_key = f"ldap_sync_notified_{username}"
        last_notified = cache.get(cache_key)
        
        self.stdout.write(f'    [DEBUG] Cache key: {cache_key}')
        self.stdout.write(f'    [DEBUG] Cache value: {last_notified}')
        

        #debug log
        if last_notified is None:
            self.stdout.write(f' No previous notification found - should notify')
            return True  # Never notified before
            
        # Check if cooldown period has passed to allow notification
        days_since_notification = (timezone.now() - last_notified).days
        should_notify = days_since_notification >= NOTIFICATION_COOLDOWN_DAYS
        return should_notify
    
    def record_restricted_user_notification(self, username):
        """Record that we've sent a notification for this restricted user"""
        cache_key = f"ldap_sync_notified_{username}"
        # Cache for slightly longer than cooldown to ensure we don't miss edge cases
        cache_timeout = (NOTIFICATION_COOLDOWN_DAYS + 1) * 24 * 60 * 60  # seconds
        current_time = timezone.now()
        
        
        cache.set(cache_key, current_time, cache_timeout)
        # Verify it was set
        verify_value = cache.get(cache_key)

    def send_restricted_user_notification(self, user, citizenship_code):
        """Send email notification about restricted user"""
        if not EMAIL_ENABLED:
            logger.warning("Email not enabled - restricted user notification not sent")
            self.stdout.write(f'    Email not enabled - restricted user notification not sent')
            return False
            
        subject = "ColdFront: New user from restricted country requires review"
        
        body = f"""
                A new user has been created in ColdFront from a restricted country and their LDAP access has been restricted pending review.

                User Details:
                - Username: {user.username}
                - Name: {user.first_name} {user.last_name}
                - Email: {user.email}
                - Citizenship: {citizenship_code}

                This user has NOT been created in LDAP due to export control restrictions.
                Please review this user account and take appropriate action.

                This is an automated notification from the ColdFront LDAP sync process.

                This is a test, please ignore. - Cameron
                """
        
        self.stdout.write(f'    Sending email notification to oit_hpsc_accounts@utk.edu...')
        
        try:
            send_email(
                subject=subject,
                body=body,
                sender=EMAIL_SENDER,
                receiver_list=['oit_hpsc_accounts@utk.edu']
            )
            logger.info(f"Sent restricted user notification email for {user.username}")
            self.stdout.write(f'    Email notification sent successfully')
            return True
        except Exception as e:
            logger.error(f"Failed to send restricted user notification email: {e}")
            self.stdout.write(f'    Email notification failed: {str(e)}')
            return False

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        specific_user = options['user']
        
        restricted_countries = ["IR", "KP", "CU", "SD", "SY"]
        
        self.stdout.write(self.style.SUCCESS(f'Starting LDAP user sync - {"DRY RUN" if dry_run else "LIVE RUN"}'))
        
        total_coldfront_users = 0
        users_already_in_ldap = 0
        users_created = 0
        users_failed = 0
        users_restricted = 0
        
        try:
            
            ldap_client = LDAPClient()
            
            # Get all users from ColdFront if no specific user is provided
            if specific_user:
                try:
                    coldfront_users = [UserProfile.objects.get(user__username=specific_user)]
                    self.stdout.write(f'Processing specific user: {specific_user}')
                except UserProfile.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'User {specific_user} not found in ColdFront'))
                    return
            else:
                coldfront_users = UserProfile.objects.all()
                if limit:
                    coldfront_users = coldfront_users[:limit]
                    self.stdout.write(f'Processing first {limit} users from ColdFront')
                else:
                    self.stdout.write('Processing all users from ColdFront')
            
            total_coldfront_users = len(coldfront_users)
            self.stdout.write(f'Found {total_coldfront_users} users in ColdFront database')
            
            
            # Compare and sync users
            for user_profile in coldfront_users:
                user = user_profile.user
                username = user.username
                
                self.stdout.write(f'Processing user: {username}')
                
                # Check for citizenship restrictions FIRST (before LDAP lookup)
                citizenship_code = getattr(user_profile, 'citizenship_code', None)
                if citizenship_code and citizenship_code in restricted_countries:
                    users_restricted += 1
                    self.stdout.write(
                        self.style.WARNING(f'   User {username} from restricted country ({citizenship_code}) - blocked from LDAP')
                    )
                    
                    # Send email notification if we haven't notified about this user recently
                    if self.should_notify_restricted_user(username):
                        self.stdout.write(f'     First time detecting restricted user - sending notification email')
                        
                        if not dry_run:
                            if self.send_restricted_user_notification(user, citizenship_code):
                                self.record_restricted_user_notification(username)
                        else:
                            self.stdout.write(f'    [DRY RUN] Would send restricted user notification email')
                            # Record the notification even in dry-run for realistic testing behavior
                            self.record_restricted_user_notification(username)
                    else:
                        self.stdout.write(f'    Already notified about this user recently - skipping email')
                    
                    continue  # Skip to next user - restricted users don't get LDAP accounts
                
                # Check if user exists in LDAP (only for non-restricted users)
                existing_user = ldap_client.find_user_by_uid(username)
                if existing_user:
                    users_already_in_ldap += 1
                    self.stdout.write(f'   User {username} already exists in LDAP - skipping')
                    continue
                
                
                # User is eligible, proceed with LDAP creation
                self.stdout.write(f'  User {username} eligible for LDAP - creating...')
                
                if dry_run:
                    self.stdout.write(f'  [DRY RUN] Would create user {username} in LDAP')
                    users_created += 1
                    continue
                
                try:
                    
                    success = ldap_client.create_user(user)
                    
                    if success:
                        users_created += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  Successfully created user {username} in LDAP')
                        )
                    else:
                        users_failed += 1
                        self.stdout.write(
                            self.style.ERROR(f'   Failed to create user {username} in LDAP')
                        )
                        
                except Exception as e:
                    users_failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'  Error creating user {username}: {str(e)}')
                    )
                    logger.error(f'Error creating LDAP user {username}: {e}', exc_info=True)
            
            # Summary
            self.stdout.write('\n' + '=' * 50)
            self.stdout.write(self.style.SUCCESS('LDAP User Sync Summary:'))
            self.stdout.write(f'Total ColdFront users processed: {total_coldfront_users}')
            self.stdout.write(f'Users already in LDAP: {users_already_in_ldap}')
            self.stdout.write(f'Users created: {users_created}')
            self.stdout.write(f'Users restricted (blocked): {users_restricted}')
            if users_failed > 0:
                self.stdout.write(self.style.WARNING(f'Users failed: {users_failed}'))
            
            if dry_run:
                self.stdout.write(self.style.WARNING('This was a DRY RUN - no actual changes were made'))
            else:
                self.stdout.write(self.style.SUCCESS('Sync completed successfully!'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Fatal error during sync: {str(e)}'))
            logger.error(f'Fatal error during LDAP sync: {e}', exc_info=True)
            raise 