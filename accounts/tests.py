from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import SimpleRateThrottle

from .models import FocusArea, Profile


class ProfileModelTest(APITestCase):
    def test_create_and_reload_profile_with_focus_areas(self):
        user = User.objects.create_user(username="alice", password="s3cret-pass")
        backend = FocusArea.objects.get(name="Backend")
        data = FocusArea.objects.get(name="Data")

        profile = Profile.objects.create(user=user, name="Alice", cohort="2026-01")
        profile.focus_area.set([backend, data])

        reloaded = Profile.objects.get(user=user)
        self.assertEqual(reloaded.name, "Alice")
        self.assertEqual(reloaded.cohort, "2026-01")
        self.assertCountEqual(
            reloaded.focus_area.values_list("name", flat=True), ["Backend", "Data"]
        )


class AuthFlowTest(APITestCase):
    def test_signup_creates_user_and_profile(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "bob",
                "password": "s3cret-pass",
                "name": "Bob",
                "cohort": "2026-01",
                "focus_area": ["Frontend"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="bob").exists())
        profile = Profile.objects.get(user__username="bob")
        self.assertEqual(profile.name, "Bob")
        self.assertEqual(list(profile.focus_area.values_list("name", flat=True)), ["Frontend"])

    def test_signup_rejects_weak_password(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "weakpass",
                "password": "12345678",
                "name": "Weak",
                "cohort": "2026-01",
                "focus_area": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="weakpass").exists())

    def test_signup_rejects_password_similar_to_username(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "similaruser",
                "password": "similaruser123",
                "name": "Similar",
                "cohort": "2026-01",
                "focus_area": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="similaruser").exists())

    def test_signup_rejects_duplicate_username(self):
        User.objects.create_user(username="taken", password="s3cret-pass")

        response = self.client.post(
            reverse("signup"),
            {
                "username": "taken",
                "password": "s3cret-pass",
                "name": "Someone Else",
                "cohort": "2026-01",
                "focus_area": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_rejects_invalid_username_characters(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "invalid username!",
                "password": "s3cret-pass",
                "name": "Invalid",
                "cohort": "2026-01",
                "focus_area": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="invalid username!").exists())

    def test_login_with_valid_credentials_establishes_session(self):
        user = User.objects.create_user(username="carol", password="s3cret-pass")
        Profile.objects.create(user=user, name="Carol", cohort="2026-01")

        response = self.client.post(
            reverse("login"), {"username": "carol", "password": "s3cret-pass"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        authed_response = self.client.get(reverse("profile"))
        self.assertNotEqual(authed_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_invalid_credentials_is_rejected(self):
        User.objects.create_user(username="dave", password="s3cret-pass")

        response = self.client.post(
            reverse("login"), {"username": "dave", "password": "wrong-pass"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_ends_session(self):
        user = User.objects.create_user(username="erin", password="s3cret-pass")
        Profile.objects.create(user=user, name="Erin", cohort="2026-01")
        self.client.login(username="erin", password="s3cret-pass")

        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        after_logout = self.client.get(reverse("profile"))
        self.assertEqual(after_logout.status_code, status.HTTP_403_FORBIDDEN)


class ProfileIsolationTest(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="frank", password="s3cret-pass")
        self.profile_a = Profile.objects.create(user=self.user_a, name="Frank", cohort="2026-01")
        self.user_b = User.objects.create_user(username="grace", password="s3cret-pass")
        self.profile_b = Profile.objects.create(user=self.user_b, name="Grace", cohort="2026-02")

    def test_authenticated_user_only_sees_own_profile(self):
        self.client.login(username="frank", password="s3cret-pass")

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Frank")
        self.assertNotEqual(response.data["name"], "Grace")

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@patch.object(SimpleRateThrottle, "THROTTLE_RATES", {"login": "1/min", "signup": "1/min"})
class ThrottleTest(APITestCase):
    def setUp(self):
        cache.clear()

    def test_login_is_throttled_after_rate_exceeded(self):
        User.objects.create_user(username="henry", password="s3cret-pass")

        first = self.client.post(
            reverse("login"), {"username": "henry", "password": "wrong-pass"}, format="json"
        )
        second = self.client.post(
            reverse("login"), {"username": "henry", "password": "wrong-pass"}, format="json"
        )

        self.assertEqual(first.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_signup_is_throttled_after_rate_exceeded(self):
        payload = {
            "password": "s3cret-pass",
            "name": "Throttled",
            "cohort": "2026-01",
            "focus_area": [],
        }

        first = self.client.post(reverse("signup"), {**payload, "username": "ivy"}, format="json")
        second = self.client.post(reverse("signup"), {**payload, "username": "jack"}, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_spoofed_forwarded_for_header_does_not_bypass_throttle(self):
        payload = {
            "password": "s3cret-pass",
            "name": "Spoofer",
            "cohort": "2026-01",
            "focus_area": [],
        }

        first = self.client.post(
            reverse("signup"),
            {**payload, "username": "kate"},
            format="json",
            HTTP_X_FORWARDED_FOR="1.1.1.1",
        )
        second = self.client.post(
            reverse("signup"),
            {**payload, "username": "liam"},
            format="json",
            HTTP_X_FORWARDED_FOR="2.2.2.2",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
