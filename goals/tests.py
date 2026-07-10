from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .ai_client import AIConfigurationError, get_client
from .models import Goal, LearningSession, Resource


class FakeOpenAIClient:
    """Stands in for openai.OpenAI() in tests — never makes a network call."""

    def __init__(self, content=None, exception=None, raw_response=None):
        self._content = content
        self._exception = exception
        self._raw_response = raw_response
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        if self._exception:
            raise self._exception
        if self._raw_response is not None:
            return self._raw_response
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))])


class GoalModelTest(APITestCase):
    def test_create_and_reload_goal_with_defaults(self):
        user = User.objects.create_user(username="alice", password="s3cret-pass")

        goal = Goal.objects.create(user=user, title="Learn Django", desc="Ship an app")

        reloaded = Goal.objects.get(pk=goal.pk)
        self.assertEqual(reloaded.title, "Learn Django")
        self.assertEqual(reloaded.desc, "Ship an app")
        self.assertEqual(reloaded.status, Goal.Status.PLANNED)
        self.assertIsNotNone(reloaded.created_at)
        self.assertIsNotNone(reloaded.updated_at)


class LearningSessionModelTest(APITestCase):
    def test_create_and_reload_session_with_tags(self):
        user = User.objects.create_user(username="bob", password="s3cret-pass")
        goal = Goal.objects.create(user=user, title="Learn Django")

        session = LearningSession.objects.create(
            goal=goal,
            date="2026-07-10",
            duration=45,
            notes="Read the ORM docs",
            tags=["orm", "reading"],
        )

        reloaded = LearningSession.objects.get(pk=session.pk)
        self.assertEqual(reloaded.goal, goal)
        self.assertEqual(reloaded.duration, 45)
        self.assertEqual(reloaded.tags, ["orm", "reading"])


class GoalCRUDTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="s3cret-pass")
        self.client.login(username="carol", password="s3cret-pass")

    def test_create_list_retrieve_update_delete_goal(self):
        create_response = self.client.post(
            reverse("goal-list"),
            {"title": "Learn DRF", "desc": "Build an API", "status": "planned"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        goal_id = create_response.data["id"]

        list_response = self.client.get(reverse("goal-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)

        detail_url = reverse("goal-detail", args=[goal_id])
        retrieve_response = self.client.get(detail_url)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data["title"], "Learn DRF")

        update_response = self.client.patch(
            detail_url, {"status": "in-progress"}, format="json"
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["status"], "in-progress")

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Goal.objects.filter(pk=goal_id).exists())

    def test_unauthenticated_request_is_rejected(self):
        self.client.logout()

        response = self.client.get(reverse("goal-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_browsable_api_renders_list_page(self):
        response = self.client.get(reverse("goal-list"), HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_response_excludes_resources_by_type_but_detail_includes_it(self):
        goal = Goal.objects.create(user=self.user, title="Has resources")
        Resource.objects.create(
            goal=goal, title="A resource", url="https://example.com", type="article"
        )

        list_response = self.client.get(reverse("goal-list"))
        detail_response = self.client.get(reverse("goal-detail", args=[goal.pk]))

        self.assertNotIn("resources_by_type", list_response.data[0])
        self.assertIn("resources_by_type", detail_response.data)
        self.assertEqual(len(detail_response.data["resources_by_type"]["article"]), 1)

    def test_listing_many_goals_with_resources_does_not_scale_query_count(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        goal = Goal.objects.create(user=self.user, title="One goal")
        Resource.objects.create(
            goal=goal, title="R", url="https://example.com", type="article"
        )
        with CaptureQueriesContext(connection) as one_goal_queries:
            self.client.get(reverse("goal-list"))

        for i in range(4):
            extra_goal = Goal.objects.create(user=self.user, title=f"Goal {i}")
            Resource.objects.create(
                goal=extra_goal, title="R", url="https://example.com", type="article"
            )
        with CaptureQueriesContext(connection) as five_goals_queries:
            response = self.client.get(reverse("goal-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)
        self.assertEqual(len(one_goal_queries), len(five_goals_queries))


class LearningSessionCRUDTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dave", password="s3cret-pass")
        self.client.login(username="dave", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn DRF")

    def test_browsable_api_renders_list_page(self):
        response = self.client.get(reverse("session-list"), HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_list_retrieve_update_delete_session(self):
        create_response = self.client.post(
            reverse("session-list"),
            {
                "goal": self.goal.pk,
                "date": "2026-07-10",
                "duration": 30,
                "notes": "Watched a tutorial",
                "tags": ["video"],
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.data["id"]

        list_response = self.client.get(reverse("session-list"), {"goal": self.goal.pk})
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)

        detail_url = reverse("session-detail", args=[session_id])
        retrieve_response = self.client.get(detail_url)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data["duration"], 30)

        update_response = self.client.patch(detail_url, {"duration": 60}, format="json")
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["duration"], 60)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LearningSession.objects.filter(pk=session_id).exists())

    def test_update_rejects_reassigning_goal_to_another_users_goal(self):
        session = LearningSession.objects.create(goal=self.goal, date="2026-07-10", duration=20)
        other_user = User.objects.create_user(username="oscar", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Not yours")

        response = self.client.patch(
            reverse("session-detail", args=[session.pk]),
            {"goal": other_goal.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        session.refresh_from_db()
        self.assertEqual(session.goal_id, self.goal.pk)

    def test_create_session_rejects_goal_owned_by_another_user(self):
        other_user = User.objects.create_user(username="erin", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Not yours")

        response = self.client.post(
            reverse("session-list"),
            {
                "goal": other_goal.pk,
                "date": "2026-07-10",
                "duration": 30,
                "notes": "",
                "tags": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(LearningSession.objects.filter(goal=other_goal).exists())

    def test_foreign_and_nonexistent_goal_ids_give_the_same_error(self):
        other_user = User.objects.create_user(username="erin", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Not yours")
        nonexistent_goal_id = other_goal.pk + 1000

        foreign_response = self.client.post(
            reverse("session-list"),
            {"goal": other_goal.pk, "date": "2026-07-10", "duration": 30, "notes": "", "tags": []},
            format="json",
        )
        nonexistent_response = self.client.post(
            reverse("session-list"),
            {
                "goal": nonexistent_goal_id,
                "date": "2026-07-10",
                "duration": 30,
                "notes": "",
                "tags": [],
            },
            format="json",
        )

        self.assertEqual(foreign_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(nonexistent_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            foreign_response.data["goal"][0].code, nonexistent_response.data["goal"][0].code
        )
        self.assertEqual(foreign_response.data["goal"][0].code, "does_not_exist")

    def test_invalid_goal_query_param_returns_400(self):
        response = self.client.get(reverse("session-list"), {"goal": "not-a-number"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_non_list_tags(self):
        response = self.client.post(
            reverse("session-list"),
            {
                "goal": self.goal.pk,
                "date": "2026-07-10",
                "duration": 30,
                "notes": "",
                "tags": {"not": "a list"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_zero_duration(self):
        response = self.client.post(
            reverse("session-list"),
            {"goal": self.goal.pk, "date": "2026-07-10", "duration": 0, "notes": "", "tags": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class GoalFilterTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="frank", password="s3cret-pass")
        self.client.login(username="frank", password="s3cret-pass")
        Goal.objects.create(user=self.user, title="Planned goal", status=Goal.Status.PLANNED)
        Goal.objects.create(user=self.user, title="Done goal", status=Goal.Status.DONE)

    def test_filters_goals_by_status(self):
        response = self.client.get(reverse("goal-list"), {"status": "done"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Done goal")

    def test_omitting_status_returns_all_goals(self):
        response = self.client.get(reverse("goal-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_unknown_status_value_is_rejected(self):
        response = self.client.get(reverse("goal-list"), {"status": "not-a-real-status"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class GoalIsolationTest(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="grace", password="s3cret-pass")
        self.goal_a = Goal.objects.create(user=self.user_a, title="Grace's goal")
        self.user_b = User.objects.create_user(username="heidi", password="s3cret-pass")
        self.goal_b = Goal.objects.create(user=self.user_b, title="Heidi's goal")

    def test_list_only_returns_own_goals(self):
        self.client.login(username="grace", password="s3cret-pass")

        response = self.client.get(reverse("goal-list"))

        titles = [g["title"] for g in response.data]
        self.assertIn("Grace's goal", titles)
        self.assertNotIn("Heidi's goal", titles)

    def test_cannot_retrieve_update_or_delete_another_users_goal(self):
        self.client.login(username="grace", password="s3cret-pass")
        detail_url = reverse("goal-detail", args=[self.goal_b.pk])

        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(detail_url, {"title": "hijacked"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Goal.objects.get(pk=self.goal_b.pk).title, "Heidi's goal")


class LearningSessionIsolationTest(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="ivan", password="s3cret-pass")
        self.goal_a = Goal.objects.create(user=self.user_a, title="Ivan's goal")
        self.session_a = LearningSession.objects.create(
            goal=self.goal_a, date="2026-07-10", duration=20
        )
        self.user_b = User.objects.create_user(username="judy", password="s3cret-pass")
        self.goal_b = Goal.objects.create(user=self.user_b, title="Judy's goal")
        self.session_b = LearningSession.objects.create(
            goal=self.goal_b, date="2026-07-10", duration=20
        )

    def test_list_only_returns_sessions_for_own_goals(self):
        self.client.login(username="ivan", password="s3cret-pass")

        response = self.client.get(reverse("session-list"))

        session_ids = [s["id"] for s in response.data]
        self.assertIn(self.session_a.pk, session_ids)
        self.assertNotIn(self.session_b.pk, session_ids)

    def test_cannot_retrieve_update_or_delete_another_users_session(self):
        self.client.login(username="ivan", password="s3cret-pass")
        detail_url = reverse("session-detail", args=[self.session_b.pk])

        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(detail_url, {"duration": 5}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(LearningSession.objects.get(pk=self.session_b.pk).duration, 20)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(reverse("session-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ResourceModelTest(APITestCase):
    def test_create_and_reload_resource(self):
        user = User.objects.create_user(username="karen", password="s3cret-pass")
        goal = Goal.objects.create(user=user, title="Learn Django")

        resource = Resource.objects.create(
            goal=goal, title="Django docs", url="https://docs.djangoproject.com", type="doc"
        )

        reloaded = Resource.objects.get(pk=resource.pk)
        self.assertEqual(reloaded.goal, goal)
        self.assertEqual(reloaded.title, "Django docs")
        self.assertEqual(reloaded.type, "doc")
        self.assertIsNotNone(reloaded.created_at)


class ResourceCRUDTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="liam", password="s3cret-pass")
        self.client.login(username="liam", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn DRF")

    def test_browsable_api_renders_list_page(self):
        response = self.client.get(reverse("resource-list"), HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_list_retrieve_update_delete_resource(self):
        create_response = self.client.post(
            reverse("resource-list"),
            {
                "goal": self.goal.pk,
                "title": "DRF tutorial",
                "url": "https://www.django-rest-framework.org/tutorial/1-serialization/",
                "type": "article",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        resource_id = create_response.data["id"]

        list_response = self.client.get(reverse("resource-list"), {"goal": self.goal.pk})
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)

        detail_url = reverse("resource-detail", args=[resource_id])
        retrieve_response = self.client.get(detail_url)
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data["title"], "DRF tutorial")

        update_response = self.client.patch(detail_url, {"type": "doc"}, format="json")
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["type"], "doc")

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Resource.objects.filter(pk=resource_id).exists())

    def test_create_resource_rejects_goal_owned_by_another_user(self):
        other_user = User.objects.create_user(username="mia", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Not yours")

        response = self.client.post(
            reverse("resource-list"),
            {
                "goal": other_goal.pk,
                "title": "Sneaky",
                "url": "https://example.com",
                "type": "article",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Resource.objects.filter(goal=other_goal).exists())

    def test_foreign_and_nonexistent_goal_ids_give_the_same_error(self):
        other_user = User.objects.create_user(username="mia", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Not yours")
        nonexistent_goal_id = other_goal.pk + 1000

        foreign_response = self.client.post(
            reverse("resource-list"),
            {
                "goal": other_goal.pk,
                "title": "Sneaky",
                "url": "https://example.com",
                "type": "article",
            },
            format="json",
        )
        nonexistent_response = self.client.post(
            reverse("resource-list"),
            {
                "goal": nonexistent_goal_id,
                "title": "Sneaky",
                "url": "https://example.com",
                "type": "article",
            },
            format="json",
        )

        self.assertEqual(foreign_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(nonexistent_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            foreign_response.data["goal"][0].code, nonexistent_response.data["goal"][0].code
        )
        self.assertEqual(foreign_response.data["goal"][0].code, "does_not_exist")

    def test_invalid_goal_query_param_returns_400(self):
        response = self.client.get(reverse("resource-list"), {"goal": "not-a-number"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_unknown_type(self):
        response = self.client.post(
            reverse("resource-list"),
            {
                "goal": self.goal.pk,
                "title": "Bad type",
                "url": "https://example.com",
                "type": "not-a-real-type",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_invalid_url(self):
        response = self.client.post(
            reverse("resource-list"),
            {
                "goal": self.goal.pk,
                "title": "Bad url",
                "url": "not-a-url",
                "type": "article",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_returns_newest_resource_first(self):
        first = Resource.objects.create(
            goal=self.goal, title="First", url="https://example.com/1", type="article"
        )
        second = Resource.objects.create(
            goal=self.goal, title="Second", url="https://example.com/2", type="article"
        )

        response = self.client.get(reverse("resource-list"))

        ids = [r["id"] for r in response.data]
        self.assertEqual(ids, [second.pk, first.pk])

    def test_update_rejects_reassigning_goal_to_another_users_goal(self):
        resource = Resource.objects.create(
            goal=self.goal, title="Mine", url="https://example.com", type="article"
        )
        other_user = User.objects.create_user(username="noah", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Not yours")

        response = self.client.patch(
            reverse("resource-detail", args=[resource.pk]),
            {"goal": other_goal.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Resource.objects.get(pk=resource.pk).goal, self.goal)


class ResourceIsolationTest(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="nina", password="s3cret-pass")
        self.goal_a = Goal.objects.create(user=self.user_a, title="Nina's goal")
        self.resource_a = Resource.objects.create(
            goal=self.goal_a, title="A's resource", url="https://example.com/a", type="article"
        )
        self.user_b = User.objects.create_user(username="oscar", password="s3cret-pass")
        self.goal_b = Goal.objects.create(user=self.user_b, title="Oscar's goal")
        self.resource_b = Resource.objects.create(
            goal=self.goal_b, title="B's resource", url="https://example.com/b", type="article"
        )

    def test_list_only_returns_resources_for_own_goals(self):
        self.client.login(username="nina", password="s3cret-pass")

        response = self.client.get(reverse("resource-list"))

        resource_ids = [r["id"] for r in response.data]
        self.assertIn(self.resource_a.pk, resource_ids)
        self.assertNotIn(self.resource_b.pk, resource_ids)

    def test_cannot_retrieve_update_or_delete_another_users_resource(self):
        self.client.login(username="nina", password="s3cret-pass")
        detail_url = reverse("resource-detail", args=[self.resource_b.pk])

        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(detail_url, {"title": "hijacked"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Resource.objects.get(pk=self.resource_b.pk).title, "B's resource")

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(reverse("resource-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GoalResourcesByTypeTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="peggy", password="s3cret-pass")
        self.client.login(username="peggy", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn Django")
        self.other_goal = Goal.objects.create(user=self.user, title="Learn Vue")

    def test_goal_detail_groups_resources_by_type(self):
        Resource.objects.create(
            goal=self.goal, title="Article 1", url="https://example.com/1", type="article"
        )
        Resource.objects.create(
            goal=self.goal, title="Video 1", url="https://example.com/2", type="video"
        )
        Resource.objects.create(
            goal=self.other_goal, title="Not this goal", url="https://example.com/3", type="article"
        )

        response = self.client.get(reverse("goal-detail", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        grouped = response.data["resources_by_type"]
        self.assertEqual(len(grouped["article"]), 1)
        self.assertEqual(grouped["article"][0]["title"], "Article 1")
        self.assertEqual(len(grouped["video"]), 1)
        self.assertNotIn("repo", grouped)

    def test_goal_with_no_resources_returns_empty_grouping(self):
        response = self.client.get(reverse("goal-detail", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["resources_by_type"], {})

    def test_another_users_resources_never_appear_in_grouping(self):
        other_user = User.objects.create_user(username="quinn", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Quinn's goal")
        Resource.objects.create(
            goal=other_goal, title="Quinn's resource", url="https://example.com/4", type="article"
        )

        response = self.client.get(reverse("goal-detail", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["resources_by_type"], {})


class AIClientConfigTest(APITestCase):
    @override_settings(OPENAI_API_KEY="")
    def test_get_client_raises_when_key_missing(self):
        with self.assertRaises(AIConfigurationError):
            get_client()

    @override_settings(OPENAI_API_KEY="sk-fake-test-key")
    def test_get_client_returns_client_when_key_set(self):
        client = get_client()
        self.assertIsNotNone(client)


class GatherGoalContextTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="victor", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn Django")

    def test_caps_number_of_sessions_and_resources(self):
        from .services import MAX_ITEMS_PER_GOAL, gather_goal_context

        for i in range(MAX_ITEMS_PER_GOAL + 5):
            LearningSession.objects.create(
                goal=self.goal, date="2026-07-10", duration=10, notes=f"session {i}"
            )
            Resource.objects.create(
                goal=self.goal, title=f"resource {i}", url="https://example.com", type="doc"
            )

        context = gather_goal_context(self.goal)

        self.assertEqual(len(context["sessions"]), MAX_ITEMS_PER_GOAL)
        self.assertEqual(len(context["resources"]), MAX_ITEMS_PER_GOAL)

    def test_truncates_long_session_notes(self):
        from .services import MAX_NOTE_LENGTH, gather_goal_context

        LearningSession.objects.create(
            goal=self.goal, date="2026-07-10", duration=10, notes="x" * (MAX_NOTE_LENGTH + 100)
        )

        context = gather_goal_context(self.goal)

        self.assertEqual(len(context["sessions"][0]["notes"]), MAX_NOTE_LENGTH)


class GenerateSummaryTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rachel", password="s3cret-pass")
        self.client.login(username="rachel", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn Testing")
        LearningSession.objects.create(
            goal=self.goal, date="2026-07-10", duration=30, notes="Wrote tests"
        )
        Resource.objects.create(
            goal=self.goal, title="Docs", url="https://example.com", type="doc"
        )

    @patch("goals.services.get_client")
    def test_generate_summary_returns_summary(self, mock_get_client):
        mock_get_client.return_value = FakeOpenAIClient(content="You're making good progress.")

        response = self.client.post(reverse("goal-generate-summary", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"], "You're making good progress.")

    def test_rejects_goal_with_no_sessions_or_resources(self):
        empty_goal = Goal.objects.create(user=self.user, title="Empty goal")

        response = self.client.post(reverse("goal-generate-summary", args=[empty_goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("goals.services.get_client")
    def test_maps_upstream_api_error_to_502(self, mock_get_client):
        mock_get_client.return_value = FakeOpenAIClient(exception=RuntimeError("boom"))

        response = self.client.post(reverse("goal-generate-summary", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    @patch("goals.services.get_client")
    def test_upstream_error_message_is_not_leaked_to_client(self, mock_get_client):
        mock_get_client.return_value = FakeOpenAIClient(
            exception=RuntimeError("super secret internal detail")
        )

        response = self.client.post(reverse("goal-generate-summary", args=[self.goal.pk]))

        self.assertNotIn("super secret internal detail", str(response.data))

    @patch("goals.services.get_client")
    def test_malformed_response_with_no_choices_returns_502_not_500(self, mock_get_client):
        mock_get_client.return_value = FakeOpenAIClient(raw_response=SimpleNamespace(choices=[]))

        response = self.client.post(reverse("goal-generate-summary", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    @patch("goals.services.get_client")
    def test_empty_completion_content_returns_502_not_500(self, mock_get_client):
        mock_get_client.return_value = FakeOpenAIClient(content=None)

        response = self.client.post(reverse("goal-generate-summary", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_cannot_generate_summary_for_another_users_goal(self):
        other_user = User.objects.create_user(username="sam", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Not yours")

        response = self.client.post(reverse("goal-generate-summary", args=[other_goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_is_rejected(self):
        self.client.logout()

        response = self.client.post(reverse("goal-generate-summary", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SuggestNextStepsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tina", password="s3cret-pass")
        self.client.login(username="tina", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn Testing")
        LearningSession.objects.create(
            goal=self.goal, date="2026-07-10", duration=30, notes="Wrote tests"
        )

    @patch("goals.services.get_client")
    def test_truncates_more_than_three_steps(self, mock_get_client):
        content = "1. Step one\n2. Step two\n3. Step three\n4. Step four"
        mock_get_client.return_value = FakeOpenAIClient(content=content)

        response = self.client.post(reverse("goal-suggest-next-steps", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["steps"], ["Step one", "Step two", "Step three"])

    @patch("goals.services.get_client")
    def test_returns_fewer_than_three_without_error(self, mock_get_client):
        mock_get_client.return_value = FakeOpenAIClient(content="- Only step")

        response = self.client.post(reverse("goal-suggest-next-steps", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["steps"], ["Only step"])

    def test_rejects_goal_with_no_sessions_or_resources(self):
        empty_goal = Goal.objects.create(user=self.user, title="Empty goal")

        response = self.client.post(reverse("goal-suggest-next-steps", args=[empty_goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("goals.services.get_client")
    def test_maps_upstream_api_error_to_502(self, mock_get_client):
        mock_get_client.return_value = FakeOpenAIClient(exception=RuntimeError("boom"))

        response = self.client.post(reverse("goal-suggest-next-steps", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_cannot_suggest_next_steps_for_another_users_goal(self):
        other_user = User.objects.create_user(username="uma", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other_user, title="Not yours")

        response = self.client.post(reverse("goal-suggest-next-steps", args=[other_goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_is_rejected(self):
        self.client.logout()

        response = self.client.post(reverse("goal-suggest-next-steps", args=[self.goal.pk]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
