import unicodedata
def generate_username(email):
    # Using Python 3 and Django 1.11+, usernames can contain alphanumeric
    # (ascii and unicode), _, @, +, . and - characters. So we normalize
    # it and slice at 150 characters.
    return str(unicodedata.normalize('NFKC', email)[:150]).split('@')[0]

from mozilla_django_oidc.auth import OIDCAuthenticationBackend
#from coldfront.models import Profile

class MyOIDCAB(OIDCAuthenticationBackend):
        def create_user(self, claims):
            user = super(MyOIDCAB, self).create_user(claims)
            user.first_name = claims.get('given_name', '')
            user.last_name = claims.get('family_name', '')
            user.username = generate_username(claims.get('email',''))
            user.save()
            return user

        def update_user(self, user, claims):
            user.first_name = claims.get('given_name', '')
            user.last_name = claims.get('family_name', '')
            user.save()
            return user
