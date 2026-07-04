from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.core.exceptions import MultipleObjectsReturned

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        email = username or kwargs.get('email')
        try:
            # Try to grab the exact user
            user = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            return None
        except MultipleObjectsReturned:
            # If multiple records exist, fall back safely to picking the first one
            user = UserModel.objects.filter(email=email).first()
        
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None