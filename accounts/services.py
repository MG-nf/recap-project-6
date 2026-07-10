from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction

from .models import FocusArea, Profile


class InvalidCredentialsError(Exception):
    pass


class UsernameTakenError(Exception):
    pass


def register_user(*, username, password, name, cohort, focus_area):
    validate_password(password, user=User(username=username))

    try:
        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password)
            profile = Profile.objects.create(user=user, name=name, cohort=cohort)
            if focus_area:
                profile.focus_area.set(FocusArea.objects.filter(name__in=focus_area))
    except IntegrityError as exc:
        raise UsernameTakenError("A user with this username already exists.") from exc
    return user, profile


def authenticate_user(*, username, password):
    user = authenticate(username=username, password=password)
    if user is None:
        raise InvalidCredentialsError("Invalid username or password.")
    return user


def get_profile_for_user(user):
    return Profile.objects.get(user=user)
