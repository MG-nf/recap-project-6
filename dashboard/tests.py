from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from goals.models import Goal, LearningSession, Resource


class DashboardGoalStatusTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="s3cret-pass")
        self.client.login(username="alice", password="s3cret-pass")

    def test_shows_goal_counts_by_status(self):
        Goal.objects.create(user=self.user, title="A", status=Goal.Status.PLANNED)
        Goal.objects.create(user=self.user, title="B", status=Goal.Status.PLANNED)
        Goal.objects.create(user=self.user, title="C", status=Goal.Status.DONE)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["status_counts"]["planned"], 2)
        self.assertEqual(response.context["status_counts"]["done"], 1)
        self.assertEqual(response.context["status_counts"]["in-progress"], 0)

    def test_another_users_goals_do_not_affect_counts(self):
        other = User.objects.create_user(username="bob", password="s3cret-pass")
        Goal.objects.create(user=other, title="Not mine", status=Goal.Status.DONE)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.context["status_counts"]["done"], 0)

    def test_unauthenticated_redirects_to_login(self):
        self.client.logout()

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response.url)


class DashboardReportingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="s3cret-pass")
        self.client.login(username="carol", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn Django")

    def test_tag_breakdown_includes_untagged_bucket(self):
        LearningSession.objects.create(
            goal=self.goal, date="2026-07-01", duration=30, tags=["reading"]
        )
        LearningSession.objects.create(goal=self.goal, date="2026-07-02", duration=20, tags=[])

        response = self.client.get(reverse("dashboard:index"))

        breakdown = response.context["goal_tag_breakdowns"][0]["tags"]
        self.assertEqual(breakdown["reading"], 30)
        self.assertEqual(breakdown["Untagged"], 20)

    def test_week_totals_sum_across_goals(self):
        other_goal = Goal.objects.create(user=self.user, title="Learn Testing")
        LearningSession.objects.create(goal=self.goal, date="2026-07-06", duration=30, tags=[])
        LearningSession.objects.create(goal=other_goal, date="2026-07-07", duration=45, tags=[])

        response = self.client.get(reverse("dashboard:index"))

        week_totals = response.context["week_totals"]
        self.assertEqual(len(week_totals), 1)
        self.assertEqual(week_totals[0]["total"], 75)

    def test_another_users_sessions_never_appear(self):
        other = User.objects.create_user(username="dave", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other, title="Not mine")
        LearningSession.objects.create(
            goal=other_goal, date="2026-07-01", duration=99, tags=["sneaky"]
        )

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.context["week_totals"], [])
        self.assertEqual(response.context["goal_tag_breakdowns"][0]["tags"], {})


class GoalTemplateViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="erin", password="s3cret-pass")
        self.client.login(username="erin", password="s3cret-pass")

    def test_create_list_detail_edit_delete_goal(self):
        create_response = self.client.post(
            reverse("dashboard:goal-create"),
            {"title": "Learn Testing", "desc": "Write tests", "status": "planned"},
        )
        goal = Goal.objects.get(title="Learn Testing")
        self.assertRedirects(create_response, reverse("dashboard:goal-detail", args=[goal.pk]))

        list_response = self.client.get(reverse("dashboard:goal-list"))
        self.assertContains(list_response, "Learn Testing")

        detail_response = self.client.get(reverse("dashboard:goal-detail", args=[goal.pk]))
        self.assertContains(detail_response, "Learn Testing")

        edit_response = self.client.post(
            reverse("dashboard:goal-edit", args=[goal.pk]),
            {"title": "Learn Testing", "desc": "Write tests", "status": "done"},
        )
        self.assertRedirects(edit_response, reverse("dashboard:goal-detail", args=[goal.pk]))
        goal.refresh_from_db()
        self.assertEqual(goal.status, "done")

        delete_response = self.client.post(reverse("dashboard:goal-delete", args=[goal.pk]))
        self.assertRedirects(delete_response, reverse("dashboard:goal-list"))
        self.assertFalse(Goal.objects.filter(pk=goal.pk).exists())

    def test_cannot_view_or_edit_another_users_goal(self):
        other = User.objects.create_user(username="frank", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other, title="Not yours")

        self.assertEqual(
            self.client.get(reverse("dashboard:goal-detail", args=[other_goal.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:goal-edit", args=[other_goal.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:goal-delete", args=[other_goal.pk])).status_code,
            404,
        )

    def test_unauthenticated_redirects_to_login(self):
        self.client.logout()

        response = self.client.get(reverse("dashboard:goal-list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response.url)


class SessionTemplateViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="grace", password="s3cret-pass")
        self.client.login(username="grace", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn DRF")

    def test_create_list_edit_delete_session(self):
        create_response = self.client.post(
            reverse("dashboard:session-create"),
            {
                "goal": self.goal.pk,
                "date": "2026-07-10",
                "duration": 30,
                "notes": "Watched a tutorial",
                "tags": "video, tutorial",
            },
        )
        session = LearningSession.objects.get(goal=self.goal)
        self.assertRedirects(create_response, reverse("dashboard:session-list"))
        self.assertEqual(session.tags, ["video", "tutorial"])

        list_response = self.client.get(reverse("dashboard:session-list"))
        self.assertContains(list_response, "Learn DRF")

        edit_response = self.client.post(
            reverse("dashboard:session-edit", args=[session.pk]),
            {
                "goal": self.goal.pk,
                "date": "2026-07-10",
                "duration": 60,
                "notes": "Watched a tutorial",
                "tags": "video",
            },
        )
        self.assertRedirects(edit_response, reverse("dashboard:session-list"))
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)

        delete_response = self.client.post(reverse("dashboard:session-delete", args=[session.pk]))
        self.assertRedirects(delete_response, reverse("dashboard:session-list"))
        self.assertFalse(LearningSession.objects.filter(pk=session.pk).exists())

    def test_cannot_attach_session_to_another_users_goal(self):
        other = User.objects.create_user(username="heidi", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other, title="Not yours")

        response = self.client.post(
            reverse("dashboard:session-create"),
            {"goal": other_goal.pk, "date": "2026-07-10", "duration": 30, "notes": "", "tags": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(LearningSession.objects.filter(goal=other_goal).exists())

    def test_update_rejects_reassigning_session_to_another_users_goal(self):
        session = LearningSession.objects.create(goal=self.goal, date="2026-07-10", duration=20)
        other = User.objects.create_user(username="nadia", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other, title="Not yours")

        response = self.client.post(
            reverse("dashboard:session-edit", args=[session.pk]),
            {
                "goal": other_goal.pk,
                "date": "2026-07-10",
                "duration": 20,
                "notes": "",
                "tags": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.goal_id, self.goal.pk)

    def test_cannot_edit_or_delete_another_users_session(self):
        other = User.objects.create_user(username="ike", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other, title="Not yours")
        other_session = LearningSession.objects.create(
            goal=other_goal, date="2026-07-10", duration=10
        )

        self.assertEqual(
            self.client.get(reverse("dashboard:session-edit", args=[other_session.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("dashboard:session-delete", args=[other_session.pk])
            ).status_code,
            404,
        )


class ResourceTemplateViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ivan", password="s3cret-pass")
        self.client.login(username="ivan", password="s3cret-pass")
        self.goal = Goal.objects.create(user=self.user, title="Learn DRF")

    def test_create_list_edit_delete_resource(self):
        create_response = self.client.post(
            reverse("dashboard:resource-create"),
            {"goal": self.goal.pk, "title": "Docs", "url": "https://example.com", "type": "doc"},
        )
        resource = Resource.objects.get(goal=self.goal)
        self.assertRedirects(create_response, reverse("dashboard:resource-list"))

        list_response = self.client.get(reverse("dashboard:resource-list"))
        self.assertContains(list_response, "Docs")

        edit_response = self.client.post(
            reverse("dashboard:resource-edit", args=[resource.pk]),
            {
                "goal": self.goal.pk,
                "title": "Docs v2",
                "url": "https://example.com",
                "type": "doc",
            },
        )
        self.assertRedirects(edit_response, reverse("dashboard:resource-list"))
        resource.refresh_from_db()
        self.assertEqual(resource.title, "Docs v2")

        delete_response = self.client.post(reverse("dashboard:resource-delete", args=[resource.pk]))
        self.assertRedirects(delete_response, reverse("dashboard:resource-list"))
        self.assertFalse(Resource.objects.filter(pk=resource.pk).exists())

    def test_cannot_attach_resource_to_another_users_goal(self):
        other = User.objects.create_user(username="judy", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other, title="Not yours")

        response = self.client.post(
            reverse("dashboard:resource-create"),
            {"goal": other_goal.pk, "title": "Sneaky", "url": "https://example.com", "type": "doc"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resource.objects.filter(goal=other_goal).exists())

    def test_cannot_edit_or_delete_another_users_resource(self):
        other = User.objects.create_user(username="kim", password="s3cret-pass")
        other_goal = Goal.objects.create(user=other, title="Not yours")
        other_resource = Resource.objects.create(
            goal=other_goal, title="Not yours", url="https://example.com", type="doc"
        )

        self.assertEqual(
            self.client.get(
                reverse("dashboard:resource-edit", args=[other_resource.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("dashboard:resource-delete", args=[other_resource.pk])
            ).status_code,
            404,
        )


class NavigationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="karen", password="s3cret-pass")

    def test_authenticated_nav_links_present(self):
        self.client.login(username="karen", password="s3cret-pass")

        response = self.client.get(reverse("dashboard:index"))

        self.assertContains(response, reverse("dashboard:index"))
        self.assertContains(response, reverse("dashboard:goal-list"))
        self.assertContains(response, reverse("dashboard:session-list"))
        self.assertContains(response, reverse("dashboard:resource-list"))
        self.assertContains(response, reverse("dashboard:logout"))

    def test_logged_out_nav_shows_login_link(self):
        response = self.client.get(reverse("dashboard:login"))

        self.assertContains(response, reverse("dashboard:login"))
        self.assertNotContains(response, reverse("dashboard:logout"))


class AuthViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="liam", password="s3cret-pass")

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("dashboard:login"), {"username": "liam", "password": "s3cret-pass"}
        )

        self.assertRedirects(response, reverse("dashboard:index"))

    def test_login_failure_shows_generic_error(self):
        response = self.client.post(
            reverse("dashboard:login"), {"username": "liam", "password": "wrong"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_logout_requires_post(self):
        self.client.login(username="liam", password="s3cret-pass")

        get_response = self.client.get(reverse("dashboard:logout"))
        self.assertRedirects(get_response, reverse("dashboard:index"))

        still_authed_response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(still_authed_response.status_code, 200)

        post_response = self.client.post(reverse("dashboard:logout"))
        self.assertRedirects(post_response, reverse("dashboard:login"))

        after_logout_response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(after_logout_response.status_code, 302)

    def test_login_redirects_back_to_originally_requested_page(self):
        goal_url = reverse("dashboard:goal-list")

        get_response = self.client.get(f"{reverse('dashboard:login')}?next={goal_url}")
        self.assertContains(get_response, f'value="{goal_url}"')

        post_response = self.client.post(
            reverse("dashboard:login"),
            {"username": "liam", "password": "s3cret-pass", "next": goal_url},
        )

        self.assertRedirects(post_response, goal_url)

    def test_login_ignores_unsafe_next_url(self):
        response = self.client.post(
            reverse("dashboard:login"),
            {"username": "liam", "password": "s3cret-pass", "next": "https://evil.example/"},
        )

        self.assertRedirects(response, reverse("dashboard:index"))

    def test_login_ignores_scheme_relative_next_url(self):
        response = self.client.post(
            reverse("dashboard:login"),
            {"username": "liam", "password": "s3cret-pass", "next": "//evil.example/"},
        )

        self.assertRedirects(response, reverse("dashboard:index"))


class AccessibilityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mia", password="s3cret-pass")
        self.client.login(username="mia", password="s3cret-pass")

    def test_pages_have_exactly_one_h1(self):
        urls = [
            reverse("dashboard:index"),
            reverse("dashboard:goal-list"),
            reverse("dashboard:goal-create"),
            reverse("dashboard:session-list"),
            reverse("dashboard:resource-list"),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(
                response.content.decode().count("<h1"), 1, f"{url} should have exactly one <h1>"
            )

    def test_login_form_fields_have_labels(self):
        self.client.logout()

        response = self.client.get(reverse("dashboard:login"))
        content = response.content.decode()

        self.assertIn('for="id_username"', content)
        self.assertIn('for="id_password"', content)

    def test_goal_form_fields_have_labels(self):
        response = self.client.get(reverse("dashboard:goal-create"))
        content = response.content.decode()

        self.assertIn('for="id_title"', content)
        self.assertIn('for="id_status"', content)
