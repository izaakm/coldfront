from coldfront.config.base import INSTALLED_APPS
from coldfront.config.env import ENV
from django.core.exceptions import ImproperlyConfigured

try:
    import ldap3
except ImportError:
    raise ImproperlyConfigured('Please run: pip install ldap3')

try:
    import ldap
    HAS_PYTHON_LDAP = True
except ImportError:
    HAS_PYTHON_LDAP = False

# ----------------------------------------------------------------------------
#  This enables writing users to LDAP when they are created in ColdFront
#  DEV ENVIRONMENT ONLY - NO PRODUCTION REFERENCES
# ----------------------------------------------------------------------------

# Safety check - only run in debug mode
if not ENV.bool('DEBUG', default=False):
    raise ImproperlyConfigured('LDAP Write plugin can only run in DEBUG mode during development')


INSTALLED_APPS += [
    'coldfront.plugins.ldap_write',
]

# LDAP connection settings - DEV ONLY - READ-ONLY CREDENTIALS
# Using ldap_user (read-only) instead of ldap_mgmt (write access)
LDAP_WRITE_SERVER_URI = ENV.str('LDAP_WRITE_SERVER_URI', default='ldap://ldap-dev.isaac.utk.edu')
LDAP_WRITE_BASE_DN = ENV.str('LDAP_WRITE_BASE_DN', default='dc=hpsc,dc=tennessee,dc=edu')

# Read-only bind credentials (ldap_user from legacy Gold portal)
LDAP_WRITE_BIND_DN = ENV.str('LDAP_WRITE_BIND_DN', default='uid=ldap_user,ou=People,dc=hpsc,dc=tennessee,dc=edu')
LDAP_WRITE_BIND_PASSWORD = ENV.str('LDAP_WRITE_BIND_PASSWORD', default='')


LDAP_WRITE_PEOPLE_OU = ENV.str('LDAP_WRITE_PEOPLE_OU', default='ou=People')
LDAP_WRITE_GROUPS_OU = ENV.str('LDAP_WRITE_GROUPS_OU', default='ou=Groups')

# Safety and operational settings - ALWAYS DEV MODE, READ-ONLY
LDAP_WRITE_DRY_RUN = ENV.bool('LDAP_WRITE_DRY_RUN', default=True)
LDAP_WRITE_READ_ONLY = ENV.bool('LDAP_WRITE_READ_ONLY', default=True)  # Force read-only mode
LDAP_WRITE_CONNECT_TIMEOUT = ENV.float('LDAP_WRITE_CONNECT_TIMEOUT', default=5.0)


LDAP_WRITE_RESTRICTED_COUNTRIES = ENV.list('LDAP_WRITE_RESTRICTED_COUNTRIES', default=['IR', 'KP', 'CU', 'SD', 'SY'])

# Safety check - ensure we're in read-only mode during development
if not ENV.bool('LDAP_WRITE_READ_ONLY', default=True):
    raise ImproperlyConfigured('LDAP Write plugin must be in read-only mode during development')
