from django.db import models

#This was created because of UID Race conditions that occured when creating users in LDAP. 
#In development there were instances where a user would be created in LDAP quicker than the UIDCounter was incremented.
#It avoids 2 users having the same UID.

class UIDCounter(models.Model):
    """
    Atomic UID counter to prevent race conditions in LDAP user creation.
    """
    id = models.IntegerField(primary_key=True, default=1)
    next_uid = models.IntegerField(
        help_text="Next UID number to assign to new LDAP users"
    )
    updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "UID Counter"
        verbose_name_plural = "UID Counters"
    
    def __str__(self):
        return f"Next UID: {self.next_uid}"
    
    @classmethod
    def get_next_uid_atomic(cls):
        """Atomically get and increment the next UID number."""
        from django.db import transaction
        
        with transaction.atomic():
            counter, created = cls.objects.select_for_update().get_or_create(
                id=1,
                defaults={'next_uid': 12000}  # Safe default above conflicts
            )
            
            current_uid = counter.next_uid
            counter.next_uid += 1
            counter.save()
            
            return current_uid
