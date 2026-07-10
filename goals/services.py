import logging
import re

from django.db.models import Count, Sum
from django.db.models.functions import TruncWeek

from .ai_client import get_client
from .models import Goal, LearningSession, Resource

logger = logging.getLogger(__name__)

UNTAGGED_LABEL = "Untagged"


class InvalidStatusError(Exception):
    pass


class InvalidGoalIdError(Exception):
    pass


class GoalNotOwnedError(Exception):
    pass


class NoSessionDataError(Exception):
    pass


class AIServiceError(Exception):
    pass


def goals_for_user(user):
    return Goal.objects.filter(user=user)


def list_goals_for_user(user, status=None):
    queryset = goals_for_user(user)
    if status is not None:
        if status not in Goal.Status.values:
            raise InvalidStatusError(f"Unknown status '{status}'.")
        queryset = queryset.filter(status=status)
    return queryset


def create_goal(*, user, title, desc="", status=Goal.Status.PLANNED):
    return Goal.objects.create(user=user, title=title, desc=desc, status=status)


def get_goal_for_user(user, pk):
    return goals_for_user(user).get(pk=pk)


def update_goal(goal, **fields):
    for field, value in fields.items():
        setattr(goal, field, value)
    goal.save()
    return goal


def delete_goal(goal):
    goal.delete()


def sessions_for_user(user):
    return LearningSession.objects.filter(goal__user=user)


def list_sessions_for_user(user, goal_id=None):
    queryset = sessions_for_user(user)
    if goal_id is not None:
        try:
            goal_id = int(goal_id)
        except (TypeError, ValueError):
            raise InvalidGoalIdError(f"Invalid goal id '{goal_id}'.")
        queryset = queryset.filter(goal_id=goal_id)
    return queryset


def create_session(*, user, goal, date, duration, notes="", tags=None):
    if goal.user_id != user.id:
        raise GoalNotOwnedError("Goal does not belong to this user.")
    return LearningSession.objects.create(
        goal=goal, date=date, duration=duration, notes=notes, tags=tags or []
    )


def get_session_for_user(user, pk):
    return sessions_for_user(user).get(pk=pk)


def update_session(session, *, user, **fields):
    goal = fields.get("goal")
    if goal is not None and goal.user_id != user.id:
        raise GoalNotOwnedError("Goal does not belong to this user.")
    for field, value in fields.items():
        setattr(session, field, value)
    session.save()
    return session


def delete_session(session):
    session.delete()


def resources_for_user(user):
    return Resource.objects.filter(goal__user=user)


def list_resources_for_user(user, goal_id=None):
    queryset = resources_for_user(user)
    if goal_id is not None:
        try:
            goal_id = int(goal_id)
        except (TypeError, ValueError):
            raise InvalidGoalIdError(f"Invalid goal id '{goal_id}'.")
        queryset = queryset.filter(goal_id=goal_id)
    return queryset


def create_resource(*, user, goal, title, url, type):
    if goal.user_id != user.id:
        raise GoalNotOwnedError("Goal does not belong to this user.")
    return Resource.objects.create(goal=goal, title=title, url=url, type=type)


def get_resource_for_user(user, pk):
    return resources_for_user(user).get(pk=pk)


def update_resource(resource, *, user, **fields):
    goal = fields.get("goal")
    if goal is not None and goal.user_id != user.id:
        raise GoalNotOwnedError("Goal does not belong to this user.")
    for field, value in fields.items():
        setattr(resource, field, value)
    resource.save()
    return resource


def delete_resource(resource):
    resource.delete()


def resources_by_type_for_goal(goal):
    grouped = {}
    for resource in Resource.objects.filter(goal=goal).order_by("type", "-created_at"):
        grouped.setdefault(resource.type, []).append(resource)
    return grouped


MAX_ITEMS_PER_GOAL = 20
MAX_NOTE_LENGTH = 500


def gather_goal_context(goal):
    # Capped to bound prompt size/token cost — goal.sessions/goal.resources are
    # already ordered newest-first (Goal/LearningSession/Resource Meta.ordering),
    # so this keeps the most recent activity, not an arbitrary slice.
    sessions = list(goal.sessions.all()[:MAX_ITEMS_PER_GOAL])
    resources = list(goal.resources.all()[:MAX_ITEMS_PER_GOAL])
    if not sessions and not resources:
        raise NoSessionDataError("This goal has no sessions or resources yet.")
    return {
        "title": goal.title,
        "desc": goal.desc,
        "status": goal.status,
        "sessions": [
            {
                "date": str(s.date),
                "duration": s.duration,
                "notes": s.notes[:MAX_NOTE_LENGTH],
                "tags": s.tags,
            }
            for s in sessions
        ],
        "resources": [{"title": r.title, "url": r.url, "type": r.type} for r in resources],
    }


def _context_to_prompt(context):
    lines = [f"Goal: {context['title']} (status: {context['status']})"]
    if context["desc"]:
        lines.append(f"Description: {context['desc']}")
    if context["sessions"]:
        lines.append("Learning sessions:")
        for session in context["sessions"]:
            tags = ", ".join(session["tags"]) if session["tags"] else "none"
            lines.append(
                f"- {session['date']}, {session['duration']} min, tags: {tags}. "
                f"Notes: {session['notes'] or 'none'}"
            )
    if context["resources"]:
        lines.append("Resources:")
        for resource in context["resources"]:
            lines.append(f"- [{resource['type']}] {resource['title']} ({resource['url']})")
    return "\n".join(lines)


def _complete(prompt, client):
    # get_client() runs outside the try below so a missing/invalid API key
    # (AIConfigurationError) propagates untouched, not wrapped as AIServiceError.
    client = client or get_client()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
    except Exception as exc:
        # Full detail is logged server-side only — the exception's own string
        # form could contain upstream error bodies or other internals that
        # shouldn't be echoed back to the client verbatim.
        logger.exception("OpenAI request failed")
        raise AIServiceError("The AI service is temporarily unavailable.") from exc
    if not content:
        logger.error("OpenAI returned an empty completion")
        raise AIServiceError("The AI service returned an empty response.")
    return content


def generate_summary_for_goal(goal, *, client=None):
    context = gather_goal_context(goal)
    prompt = (
        "Summarize this learning goal's progress in a short paragraph, "
        f"based on the following data:\n\n{_context_to_prompt(context)}"
    )
    return _complete(prompt, client)


def suggest_next_steps_for_goal(goal, *, client=None):
    context = gather_goal_context(goal)
    prompt = (
        "Based on the following learning goal data, suggest 2-3 concrete next "
        f"steps, one per line:\n\n{_context_to_prompt(context)}"
    )
    content = _complete(prompt, client)
    steps = []
    for line in content.strip().splitlines():
        line = re.sub(r"^[\-\*\d]+[\.\)]?\s*", "", line.strip())
        if line:
            steps.append(line)
    return steps[:3]


def goal_counts_by_status(user):
    counts = {status: 0 for status in Goal.Status.values}
    for row in goals_for_user(user).values("status").annotate(count=Count("id")):
        counts[row["status"]] = row["count"]
    return counts


def duration_by_tag_for_goal(goal):
    totals = {}
    for session in goal.sessions.all():
        tags = session.tags or [UNTAGGED_LABEL]
        for tag in tags:
            totals[tag] = totals.get(tag, 0) + session.duration
    return totals


def duration_by_week_for_user(user):
    rows = (
        sessions_for_user(user)
        .annotate(week=TruncWeek("date"))
        .values("week")
        .annotate(total=Sum("duration"))
        .order_by("week")
    )
    return [{"week": row["week"], "total": row["total"]} for row in rows]
