from .models import Goal, LearningSession


class InvalidStatusError(Exception):
    pass


class InvalidGoalIdError(Exception):
    pass


class GoalNotOwnedError(Exception):
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


def update_session(session, **fields):
    for field, value in fields.items():
        setattr(session, field, value)
    session.save()
    return session


def delete_session(session):
    session.delete()
