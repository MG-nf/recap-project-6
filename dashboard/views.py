from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.services import InvalidCredentialsError, authenticate_user
from goals.models import Goal, LearningSession, Resource
from goals.services import (
    GoalNotOwnedError,
    InvalidGoalIdError,
    InvalidStatusError,
    create_goal,
    create_resource,
    create_session,
    delete_goal,
    delete_resource,
    delete_session,
    duration_by_tag_for_goal,
    duration_by_week_for_user,
    get_goal_for_user,
    get_resource_for_user,
    get_session_for_user,
    goal_counts_by_status,
    goals_for_user,
    list_goals_for_user,
    list_resources_for_user,
    list_sessions_for_user,
    resources_by_type_for_goal,
    resources_for_user,
    sessions_for_user,
    update_goal,
    update_resource,
    update_session,
)

from .forms import GoalForm, LearningSessionForm, LoginForm, ResourceForm


def _safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return "dashboard:index"


def login_view(request):
    next_url = _safe_next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url)
    form = LoginForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        try:
            user = authenticate_user(**form.cleaned_data)
        except InvalidCredentialsError as exc:
            error = str(exc)
        else:
            auth_login(request, user)
            return redirect(next_url)
    return render(
        request, "dashboard/login.html", {"form": form, "error": error, "next": next_url}
    )


@login_required
def logout_view(request):
    if request.method == "POST":
        auth_logout(request)
        return redirect("dashboard:login")
    return redirect("dashboard:index")


@login_required
def index(request):
    status_counts = goal_counts_by_status(request.user)
    week_totals = duration_by_week_for_user(request.user)
    goal_tag_breakdowns = [
        {"goal": goal, "tags": duration_by_tag_for_goal(goal)}
        for goal in goals_for_user(request.user)
    ]
    return render(
        request,
        "dashboard/index.html",
        {
            "status_counts": status_counts,
            "week_totals": week_totals,
            "goal_tag_breakdowns": goal_tag_breakdowns,
        },
    )


@login_required
def goal_list(request):
    status = request.GET.get("status")
    try:
        goals = list_goals_for_user(request.user, status=status)
    except InvalidStatusError:
        messages.error(request, f"Unknown status '{status}'.")
        goals = goals_for_user(request.user)
    return render(request, "goals/list.html", {"goals": goals, "statuses": Goal.Status.choices})


@login_required
def goal_detail(request, pk):
    try:
        goal = get_goal_for_user(request.user, pk)
    except Goal.DoesNotExist:
        raise Http404
    return render(
        request,
        "goals/detail.html",
        {
            "goal": goal,
            "resources_by_type": resources_by_type_for_goal(goal),
            "sessions": list_sessions_for_user(request.user, goal_id=goal.pk),
        },
    )


@login_required
def goal_create(request):
    form = GoalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        goal = create_goal(user=request.user, **form.cleaned_data)
        messages.success(request, f'Goal "{goal.title}" created.')
        return redirect("dashboard:goal-detail", pk=goal.pk)
    return render(request, "goals/form.html", {"form": form, "heading": "Create Goal"})


@login_required
def goal_edit(request, pk):
    try:
        goal = get_goal_for_user(request.user, pk)
    except Goal.DoesNotExist:
        raise Http404
    initial = {"title": goal.title, "desc": goal.desc, "status": goal.status}
    form = GoalForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        update_goal(goal, **form.cleaned_data)
        messages.success(request, f'Goal "{goal.title}" updated.')
        return redirect("dashboard:goal-detail", pk=goal.pk)
    return render(request, "goals/form.html", {"form": form, "heading": "Edit Goal"})


@login_required
def goal_delete(request, pk):
    try:
        goal = get_goal_for_user(request.user, pk)
    except Goal.DoesNotExist:
        raise Http404
    if request.method == "POST":
        delete_goal(goal)
        messages.success(request, f'Goal "{goal.title}" deleted.')
        return redirect("dashboard:goal-list")
    return render(request, "goals/confirm_delete.html", {"object": goal, "type_name": "goal"})


@login_required
def session_list(request):
    goal_id = request.GET.get("goal")
    try:
        sessions = list_sessions_for_user(request.user, goal_id=goal_id)
    except InvalidGoalIdError:
        messages.error(request, "Invalid goal filter.")
        sessions = sessions_for_user(request.user)
    return render(request, "sessions/list.html", {"sessions": sessions})


@login_required
def session_create(request):
    form = LearningSessionForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            create_session(user=request.user, **form.cleaned_data)
        except GoalNotOwnedError as exc:
            form.add_error("goal", str(exc))
        else:
            messages.success(request, "Session logged.")
            return redirect("dashboard:session-list")
    return render(request, "sessions/form.html", {"form": form, "heading": "Log Session"})


@login_required
def session_edit(request, pk):
    try:
        session = get_session_for_user(request.user, pk)
    except LearningSession.DoesNotExist:
        raise Http404
    initial = {
        "goal": session.goal_id,
        "date": session.date,
        "duration": session.duration,
        "notes": session.notes,
        "tags": ", ".join(session.tags),
    }
    form = LearningSessionForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            update_session(session, user=request.user, **form.cleaned_data)
        except GoalNotOwnedError as exc:
            form.add_error("goal", str(exc))
        else:
            messages.success(request, "Session updated.")
            return redirect("dashboard:session-list")
    return render(request, "sessions/form.html", {"form": form, "heading": "Edit Session"})


@login_required
def session_delete(request, pk):
    try:
        session = get_session_for_user(request.user, pk)
    except LearningSession.DoesNotExist:
        raise Http404
    if request.method == "POST":
        delete_session(session)
        messages.success(request, "Session deleted.")
        return redirect("dashboard:session-list")
    return render(
        request, "sessions/confirm_delete.html", {"object": session, "type_name": "session"}
    )


@login_required
def resource_list(request):
    goal_id = request.GET.get("goal")
    try:
        resources = list_resources_for_user(request.user, goal_id=goal_id)
    except InvalidGoalIdError:
        messages.error(request, "Invalid goal filter.")
        resources = resources_for_user(request.user)
    return render(request, "resources/list.html", {"resources": resources})


@login_required
def resource_create(request):
    form = ResourceForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            create_resource(user=request.user, **form.cleaned_data)
        except GoalNotOwnedError as exc:
            form.add_error("goal", str(exc))
        else:
            messages.success(request, "Resource added.")
            return redirect("dashboard:resource-list")
    return render(request, "resources/form.html", {"form": form, "heading": "Add Resource"})


@login_required
def resource_edit(request, pk):
    try:
        resource = get_resource_for_user(request.user, pk)
    except Resource.DoesNotExist:
        raise Http404
    initial = {
        "goal": resource.goal_id,
        "title": resource.title,
        "url": resource.url,
        "type": resource.type,
    }
    form = ResourceForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            update_resource(resource, user=request.user, **form.cleaned_data)
        except GoalNotOwnedError as exc:
            form.add_error("goal", str(exc))
        else:
            messages.success(request, "Resource updated.")
            return redirect("dashboard:resource-list")
    return render(request, "resources/form.html", {"form": form, "heading": "Edit Resource"})


@login_required
def resource_delete(request, pk):
    try:
        resource = get_resource_for_user(request.user, pk)
    except Resource.DoesNotExist:
        raise Http404
    if request.method == "POST":
        delete_resource(resource)
        messages.success(request, "Resource deleted.")
        return redirect("dashboard:resource-list")
    return render(
        request, "resources/confirm_delete.html", {"object": resource, "type_name": "resource"}
    )
