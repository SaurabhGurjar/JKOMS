# dashboard/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import build_user_workspace


def home(request):
    """
    General LTPOMS landing page.

    This page contains common plant information and must not expose
    personal workflow tasks or organization-restricted records.
    """
    return render(
        request,
        "dashboard/home.html",
        {
            "show_my_work_link": (
                request.user.is_authenticated
            ),
        },
    )


@login_required
def my_work(request):
    """
    Personalized and permission-scoped LTPOMS workspace.
    """
    workspace = build_user_workspace(
        user=request.user,
        task_limit=20,
    )

    identity = workspace["identity"]

    return render(
        request,
        "dashboard/my_work.html",
        {
            "user_employee": identity["employee"],
            "primary_position": (
                identity["primary_position"]
            ),
            "user_positions": identity["positions"],
            "workspace_modules": (
                workspace["modules"]
            ),
            "workspace_tasks": (
                workspace["tasks"]
            ),
            "workspace_quick_actions": (
                workspace["quick_actions"]
            ),
            "workspace_totals": (
                workspace["totals"]
            ),
        },
    )