from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Goal, LearningSession


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
