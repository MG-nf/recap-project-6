from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("goals/", views.goal_list, name="goal-list"),
    path("goals/create/", views.goal_create, name="goal-create"),
    path("goals/<int:pk>/", views.goal_detail, name="goal-detail"),
    path("goals/<int:pk>/edit/", views.goal_edit, name="goal-edit"),
    path("goals/<int:pk>/delete/", views.goal_delete, name="goal-delete"),
    path("sessions/", views.session_list, name="session-list"),
    path("sessions/create/", views.session_create, name="session-create"),
    path("sessions/<int:pk>/edit/", views.session_edit, name="session-edit"),
    path("sessions/<int:pk>/delete/", views.session_delete, name="session-delete"),
    path("resources/", views.resource_list, name="resource-list"),
    path("resources/create/", views.resource_create, name="resource-create"),
    path("resources/<int:pk>/edit/", views.resource_edit, name="resource-edit"),
    path("resources/<int:pk>/delete/", views.resource_delete, name="resource-delete"),
]
