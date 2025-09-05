import logging
import ldap3
import hashlib
import base64
import os
import random
import string
from django.conf import settings
from typing import Optional, Dict, List, Any
from .models import UIDCounter

logger = logging.getLogger(__name__)

class LDAPClient:
    """
    LDAP client for both read and write operations on DEV LDAP server
    This class provides safe access to ISAAC's development LDAP directory
    """
    
    def __init__(self):
        self.server_uri = getattr(settings, 'LDAP_WRITE_SERVER_URI', 'ldap://ldap-dev.isaac.utk.edu')
        self.base_dn = getattr(settings, 'LDAP_WRITE_BASE_DN', 'dc=hpsc,dc=tennessee,dc=edu')
        self.bind_dn = getattr(settings, 'LDAP_WRITE_BIND_DN', 'uid=portaladm,ou=Applications,dc=hpsc,dc=tennessee,dc=edu')
        self.bind_password = (
            getattr(settings, 'LDAP_WRITE_BIND_PASSWORD', None) or
            os.environ.get('LDAP_WRITE_BIND_PASSWORD')
        )
        self.people_ou = getattr(settings, 'LDAP_WRITE_PEOPLE_OU', 'ou=People')
        self.groups_ou = getattr(settings, 'LDAP_WRITE_GROUPS_OU', 'ou=Groups')
        self.timeout = getattr(settings, 'LDAP_WRITE_CONNECT_TIMEOUT', 5.0)
        
        self.server = None
        self.connection = None
        
        # Safety check - ensure we're only connecting to DEV server we can change when we move to production
        if 'ldap-dev' not in self.server_uri:
            raise ValueError(f"LDAP Client can only connect to DEV server. Current URI: {self.server_uri}")
        
        logger.info(f"LDAP Client initialized for server: {self.server_uri}")
        
    def connect(self, read_only: bool = True) -> bool:
        """
        Establish connection to LDAP server
        Args:
            read_only: If True, creates read-only connection. If False, enables write operations.
        Returns:
            True or False based on success of connection
        """
        try:
            # server setup
            self.server = ldap3.Server(
                self.server_uri,
                get_info=ldap3.ALL,
                connect_timeout=self.timeout
            )
            
            # create connection
            if self.bind_dn and self.bind_password:
                self.connection = ldap3.Connection(
                    self.server,
                    user=self.bind_dn,
                    password=self.bind_password,
                    auto_bind=True,
                    read_only=read_only  
                )
                mode = "READ-ONLY" if read_only else "READ/WRITE"
                logger.info(f"Connected to LDAP with {mode} authentication (portaladm)")
            else:
                # Anonymous connection (always read-only)
                self.connection = ldap3.Connection(
                    self.server,
                    auto_bind=True,
                    read_only=True  
                )
                logger.info("Connected to LDAP anonymously (read-only)")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to LDAP server: {e}")
            return False
            
    def disconnect(self):
        """Close LDAP connection"""
        if self.connection:
            self.connection.unbind()
            self.connection = None
            logger.info("Disconnected from LDAP server")
        
    def search_users(self, search_filter: str = "(objectClass=person)", limit: int = 10, use_existing_connection: bool = False) -> List[Dict[str, Any]]:
        """
        Search for users in LDAP
        """
        results = []
        connection_created = False
        
        try:
            if not use_existing_connection or not self.connection:
                if not self.connect():
                    logger.error("Cannot search users - connection failed")
                    return results
                connection_created = True
                
            search_base = f"{self.people_ou},{self.base_dn}"
            
            success = self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=['cn', 'uid', 'mail', 'uidNumber', 'gidNumber', 'homeDirectory'],
                size_limit=limit
            )
            
            if success:
                for entry in self.connection.entries:
                    user_data = {
                        'dn': entry.entry_dn,
                        'cn': str(entry.cn) if 'cn' in entry else None,
                        'uid': str(entry.uid) if 'uid' in entry else None,
                        'mail': str(entry.mail) if 'mail' in entry else None,
                        'uidNumber': str(entry.uidNumber) if 'uidNumber' in entry else None,
                        'gidNumber': str(entry.gidNumber) if 'gidNumber' in entry else None,
                        'homeDirectory': str(entry.homeDirectory) if 'homeDirectory' in entry else None
                    }
                    results.append(user_data)
                    
                logger.info(f"Found {len(results)} users matching filter: {search_filter}")
            else:
                logger.warning(f"User search failed: {self.connection.result}")
                
        except Exception as e:
            logger.error(f"Error searching users: {e}")
        finally:
            if connection_created:
                self.disconnect()
            
        return results
        
    def search_groups(self, search_filter: str = "(objectClass=posixGroup)", limit: int = 10, use_existing_connection: bool = False) -> List[Dict[str, Any]]:
        """
        Search for groups in LDAP
        """
        results = []
        connection_created = False
        
        try:
            if not use_existing_connection or not self.connection:
                if not self.connect():
                    logger.error("Cannot search groups - connection failed")
                    return results
                connection_created = True
                
            search_base = f"{self.groups_ou},{self.base_dn}"
            
            success = self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=['cn', 'gidNumber', 'memberUid', 'description'],
                size_limit=limit
            )
            
            if success:
                for entry in self.connection.entries:
                    group_data = {
                        'dn': entry.entry_dn,
                        'cn': str(entry.cn) if 'cn' in entry else None,
                        'gidNumber': str(entry.gidNumber) if 'gidNumber' in entry else None,
                        'memberUid': [str(uid) for uid in entry.memberUid] if 'memberUid' in entry else [],
                        'description': str(entry.description) if 'description' in entry else None
                    }
                    results.append(group_data)
                    
                logger.info(f"Found {len(results)} groups matching filter: {search_filter}")
            else:
                logger.warning(f"Group search failed: {self.connection.result}")
                
        except Exception as e:
            logger.error(f"Error searching groups: {e}")
        finally:
            if connection_created:
                self.disconnect()
            
        return results
        
    def find_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Find a specific user by UID
        """
        users = self.search_users(search_filter=f"(uid={uid})", limit=1)
        return users[0] if users else None
        
    def find_group_by_name(self, group_name: str, use_existing_connection: bool = False) -> Optional[Dict[str, Any]]:
        """
        Find a specific group by name
        """
        groups = self.search_groups(search_filter=f"(cn={group_name})", limit=1, use_existing_connection=use_existing_connection)
        return groups[0] if groups else None
        

    def hash_password(self, password: str) -> str:
        """
        Hash password using SSHA (Salted SHA-1) format for LDAP
        """
        
        salt = os.urandom(4)
        
        sha1_hash = hashlib.sha1(password.encode('utf-8') + salt).digest()
        
        hash_with_salt = base64.b64encode(sha1_hash + salt).decode('utf-8')
        
        return f"{{SSHA}}{hash_with_salt}"

    def add_user_to_group(self, username: str, groupname: str = "users") -> bool:
        """
        Add user to LDAP group by adding username to memberUid attribute, this is going to be replaced with
        the coldfront update when we migrate the codebase
        """
        try:
            if not self.connect(read_only=False):
                logger.error(f"Cannot add user {username} to group {groupname} - connection failed")
                return False
                
            # locate the group
            group_dn = f"cn={groupname},{self.groups_ou},{self.base_dn}"
            
            # Check if group exists and get current members
            if not self.connection.search(search_base=group_dn, search_filter="(objectClass=*)", 
                                        attributes=['memberUid'], search_scope=ldap3.BASE):
                logger.error(f"Group {groupname} not found at {group_dn}")
                return False
            
            # Check if user is already in the group in case of user already existing in group
            group_entry = self.connection.entries[0]
            current_members = group_entry.memberUid.values if hasattr(group_entry, 'memberUid') else []
            if username in current_members:
                logger.info(f"User {username} already in group {groupname} - skipping")
                return True  # Already in group = success
                
            # if user is not in group, add them to the group
            success = self.connection.modify(
                group_dn,
                {'memberUid': [(ldap3.MODIFY_ADD, [username])]}
            )
            
            if success:
                logger.info(f"Successfully added user {username} to group {groupname}")
                return True
            else:
                # Handle the case where user was added between our check and modify because of ldap time delays
                if (self.connection.result.get('description') == 'attributeOrValueExists'):
                    logger.info(f"User {username} already in group {groupname} (race condition) - treating as success")
                    return True
                else:
                    logger.error(f"Failed to add user {username} to group {groupname}: {self.connection.result}")
                    return False
                
        except Exception as e:
            logger.error(f"Error adding user {username} to group {groupname}: {e}")
            return False
        finally:
            self.disconnect()

    def create_user(self, user, enabled: bool = True) -> bool:
        """
        Create a new user entry in LDAP
        
        Args:
            user: Django User instance (User.userprofile contains citizenship_code)
            enabled: Whether the user should be enabled (affects shell assignment)
            
        Returns:
            bool: True if user was successfully created, False otherwise
        """
        try:
            if not self.connect(read_only=False):
                logger.error(f"Cannot create user {user.username} - connection failed")
                return False
                
            # Generate UID using atomic counter to prevent race conditions. More info in models.py
            uid_number = UIDCounter.get_next_uid_atomic()
            logger.info(f"Assigned UID {uid_number} to user {user.username} using atomic counter")
                
            # Try to get GID from tug2106 group (largest UTK group), fallback to UID (Default)
            group = self.find_group_by_name("tug2106", use_existing_connection=True)
            if group and group.get("gidNumber"):
                gid_number = int(group["gidNumber"])
                logger.info(f"Using GID {gid_number} from tug2106 group for user {user.username}")
            else:
                gid_number = uid_number  # Fallback to UID as GID
                logger.info(f"tug2106 group not found or missing gidNumber, using UID {uid_number} as GID for user {user.username}")
            
            # Determine shell based on export control
            restricted_countries = ["IR", "KP", "CU", "SD", "SY"]
            
            citizenship_code = None
            try:
                citizenship_code = user.userprofile.citizenship_code
            except AttributeError:
                pass  # UserProfile doesn't exist or no citizenship_code, redundant except
            
            # Determine shell based on export control
            if citizenship_code and citizenship_code in restricted_countries:
                login_shell = "/sbin/nologin"
                logger.info(f"User {user.username} from restricted country {citizenship_code} - setting shell to nologin")
            else:
                login_shell = "/bin/bash"
                if citizenship_code:
                    logger.info(f"User {user.username} from allowed country {citizenship_code} - setting shell to bash")
                else:
                    logger.info(f"User {user.username} has no citizenship set - setting shell to bash")
                
            # Parse name components
            if user.first_name and user.last_name:
                cn = user.first_name
                sn = user.last_name
                full_name = f"{user.first_name} {user.last_name}"
            else:
                # Fallback to parsing full name if available
                if hasattr(user, 'full_name') and user.full_name:
                    name_parts = user.full_name.split()
                    cn = name_parts[0] if name_parts else user.username
                    sn = name_parts[-1] if len(name_parts) > 1 else user.username
                    full_name = user.full_name
                else:
                    cn = user.username
                    sn = user.username
                    full_name = user.username
                    
            # Generate hashed password
            pwchars = string.ascii_letters + string.digits + "!@#$%^&*()"
            dummy_password = ''.join(random.choices(pwchars, k=20))
            hashed_password = self.hash_password(dummy_password)
            logger.info(f"Generated secure random password for user {user.username}")
            
            # DN Construction
            user_dn = f"uid={user.username},{self.people_ou},{self.base_dn}"
            
            # Assign the user ldap attributes
            attributes = {
                'objectClass': [
                    'inetOrgPerson',
                    'organizationalPerson', 
                    'person',
                    'posixAccount',
                    'shadowAccount',
                    'top',
                    'hostObject'
                ],
                'uid': user.username,
                'cn': cn,
                'sn': sn,
                'mail': user.email,
                'uidNumber': str(uid_number),
                'gidNumber': str(gid_number),
                'homeDirectory': f"/nfs/home/{user.username}",
                'loginShell': login_shell,
                'gecos': full_name,
                'userPassword': hashed_password,
                'shadowLastChange': '13773',
                'shadowMax': '99999',
                'shadowWarning': '7',
                'host': ['isaac']
            }
            
            logger.info(f"Creating LDAP user: {user_dn}")
            logger.info(f"UID/GID: {uid_number}, Shell: {login_shell}")
            
            # Create user entry
            success = self.connection.add(user_dn, attributes=attributes)
            
            if success:
                logger.info(f"Successfully created LDAP user {user.username} with UID {uid_number}")
                
                # Determine campus affiliation from email domain and assign appropriate groups. Probably a better way to do this.
                email_domain = user.email.lower().split('@')[-1] if user.email else ""
                groups_assigned = []
                groups_failed = []
                
                if email_domain in ['utk.edu', 'vols.utk.edu']:
                    # UTK users get: tug2106, utksoftware, utsoftware
                    campus_groups = ['tug2106', 'utksoftware', 'utsoftware']
                    campus_type = "UTK"
                elif email_domain == 'uthsc.edu':
                    # UTHSC users get: tug2105, utsoftware
                    campus_groups = ['tug2105', 'utsoftware']
                    campus_type = "UTHSC"
                else:
                    # Unknown domain - assign to basic software group only
                    campus_groups = ['utsoftware']
                    campus_type = "Unknown"
                    logger.warning(f"Unknown email domain {email_domain} for user {user.username}, assigning to utsoftware only")
                
                logger.info(f"Assigning {campus_type} user {user.username} ({user.email}) to groups: {campus_groups}")
                
                # Add user to all appropriate groups using the old method for now, will be using newer add to group/project method later
                for group_name in campus_groups:
                    if self.add_user_to_group(user.username, group_name):
                        groups_assigned.append(group_name)
                        logger.info(f"Successfully added user {user.username} to {group_name} group")
                    else:
                        groups_failed.append(group_name)
                        logger.error(f"Failed to add user {user.username} to {group_name} group")
                
                # Log final assignment results for sanity
                if groups_assigned:
                    logger.info(f"User {user.username} successfully assigned to groups: {groups_assigned}")
                if groups_failed:
                    logger.warning(f"User {user.username} failed to be assigned to groups: {groups_failed}")
                    
                return True
            else:
                logger.error(f"Failed to create LDAP user {user.username}: {self.connection.result}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating LDAP user {user.username}: {e}")
            return False
        finally:
            self.disconnect()
