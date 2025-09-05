from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    """ Displays a user's profile. A user can be a principal investigator (PI), manager, administrator, staff member, billing staff member, or center director.

    Attributes:
        is_pi (bool): indicates whether or not the user is a PI
        user (User): represents the Django User model
        citizenship_code (str): two-letter country code for export control compliance    
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_pi = models.BooleanField(default=False)
    citizenship_code = models.CharField(max_length=2, blank=True, null=True, help_text="Two-letter country code (e.g., US, IR, KP)")