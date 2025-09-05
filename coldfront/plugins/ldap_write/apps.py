from django.apps import AppConfig


class LdapWriteConfig(AppConfig):
    name = 'coldfront.plugins.ldap_write'
    
    def ready(self):
        """Import signal handlers when Django starts"""
        import coldfront.plugins.ldap_write.signals
