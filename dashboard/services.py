# dashboard/services.py
from __future__ import annotations

from datetime import date

from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from usermanagement.services import (
    get_primary_position,
    get_user_positions,
    user_has_jkoms_permission,
)


def safe_reverse(url_name, *, args=None, kwargs=None):
    try:
        return reverse(
            url_name,
            args=args,
            kwargs=kwargs,
        )
    except NoReverseMatch:
        return "#"


def user_can_access_module(
    *,
    user,
    permission_code,
    organization_unit=None,
):
    if not user or not user.is_authenticated:
        return False

    if not user.is_active:
        return False

    if user.is_superuser:
        return True

    return user_has_jkoms_permission(
        user=user,
        permission_code=permission_code,
        organization_unit=organization_unit,
    )


def get_user_identity(user):
    employee = getattr(user, "employee", None)
    primary_position = get_primary_position(user)

    return {
        "employee": employee,
        "primary_position": primary_position,
        "positions": get_user_positions(user),
    }


def _build_capa_workspace(user, *, limit=10):
    """
    Build the CAPA contribution to the common LTPOMS workspace.

    Imports remain local so the dashboard can still load if a business
    application is temporarily unavailable during development.
    """
    from quality_capa.models import (
        CAPA,
        CAPAAction,
    )
    from quality_capa.services import (
        PERMISSION_CODES,
    )

    today = timezone.localdate()

    capa_queryset = (
        CAPA.objects
        .filter(is_active=True)
        .select_related(
            "organization_unit",
            "owner_employee",
            "owner_position",
            "workflow_instance__current_step",
        )
    )

    if user.is_superuser:
        visible_capas = list(capa_queryset)
    else:
        visible_capas = [
            capa
            for capa in capa_queryset
            if user_has_jkoms_permission(
                user=user,
                permission_code=PERMISSION_CODES["view"],
                organization_unit=capa.organization_unit,
            )
        ]

    visible_capa_ids = [
        capa.pk
        for capa in visible_capas
    ]

    terminal_statuses = {
        CAPA.Status.CLOSED,
        CAPA.Status.REJECTED,
        CAPA.Status.CANCELLED,
    }

    open_capas = [
        capa
        for capa in visible_capas
        if capa.status not in terminal_statuses
    ]

    overdue_capas = [
        capa
        for capa in open_capas
        if (
            capa.target_completion_date
            and capa.target_completion_date < today
        )
    ]

    tasks = []

    workflow_task_labels = {
        CAPA.Status.DRAFT: "Complete and submit CAPA",
        CAPA.Status.SUBMITTED: "Review submitted CAPA",
        CAPA.Status.UNDER_REVIEW: "Complete CAPA review",
        CAPA.Status.ROOT_CAUSE_ANALYSIS: (
            "Complete root-cause analysis"
        ),
        CAPA.Status.ACTION_PLAN_REVIEW: (
            "Review and approve action plan"
        ),
        CAPA.Status.ACTION_IN_PROGRESS: (
            "Complete assigned CAPA actions"
        ),
        CAPA.Status.VERIFICATION: (
            "Verify completed CAPA actions"
        ),
        CAPA.Status.EFFECTIVENESS_REVIEW: (
            "Review CAPA effectiveness"
        ),
    }

    status_permissions = {
        CAPA.Status.DRAFT: PERMISSION_CODES["edit"],
        CAPA.Status.SUBMITTED: PERMISSION_CODES["review"],
        CAPA.Status.UNDER_REVIEW: PERMISSION_CODES["review"],
        CAPA.Status.ROOT_CAUSE_ANALYSIS: (
            PERMISSION_CODES["review"]
        ),
        CAPA.Status.ACTION_PLAN_REVIEW: (
            PERMISSION_CODES["approve"]
        ),
        CAPA.Status.ACTION_IN_PROGRESS: (
            PERMISSION_CODES["update_action"]
        ),
        CAPA.Status.VERIFICATION: (
            PERMISSION_CODES["verify"]
        ),
        CAPA.Status.EFFECTIVENESS_REVIEW: (
            PERMISSION_CODES["effectiveness_review"]
        ),
    }

    for capa in open_capas:
        permission_code = status_permissions.get(
            capa.status
        )

        if not permission_code:
            continue

        if not user_has_jkoms_permission(
            user=user,
            permission_code=permission_code,
            organization_unit=capa.organization_unit,
        ):
            continue

        tasks.append(
            {
                "module_code": "QUALITY-CAPA",
                "module_name": "Quality CAPA",
                "module_icon": (
                    "fa-solid fa-list-check"
                ),
                "record_type": "CAPA",
                "record_id": capa.pk,
                "record_number": capa.capa_number,
                "title": capa.title,
                "task": workflow_task_labels.get(
                    capa.status,
                    "Process CAPA",
                ),
                "workflow_step": (
                    str(
                        capa.workflow_instance.current_step
                    )
                    if (
                        capa.workflow_instance_id
                        and capa.workflow_instance.current_step_id
                    )
                    else capa.get_status_display()
                ),
                "priority": capa.get_priority_display(),
                "due_date": capa.target_completion_date,
                "is_overdue": bool(
                    capa.target_completion_date
                    and capa.target_completion_date < today
                ),
                "organization_unit": str(
                    capa.organization_unit
                ),
                "url": safe_reverse(
                    "quality_capa:detail",
                    args=[capa.pk],
                ),
            }
        )

    employee = getattr(user, "employee", None)

    position_ids = list(
        get_user_positions(user).values_list(
            "pk",
            flat=True,
        )
    )

    action_queryset = (
        CAPAAction.objects
        .filter(capa_id__in=visible_capa_ids)
        .select_related(
            "capa__organization_unit",
            "responsible_employee",
            "responsible_position",
        )
        .exclude(
            status__in=[
                CAPAAction.Status.COMPLETED,
                CAPAAction.Status.VERIFIED,
                CAPAAction.Status.CANCELLED,
            ]
        )
    )

    if not user.is_superuser:
        employee_id = (
            employee.pk
            if employee
            else None
        )

        from django.db.models import Q

        action_queryset = action_queryset.filter(
            Q(responsible_employee_id=employee_id)
            | Q(
                responsible_position_id__in=(
                    position_ids
                )
            )
        )

    my_actions = []

    for action in action_queryset.order_by(
        "target_date",
        "sequence",
    ):
        due_date = (
            action.revised_target_date
            or action.target_date
        )

        my_actions.append(
            {
                "module_code": "QUALITY-CAPA",
                "module_name": "Quality CAPA",
                "module_icon": (
                    "fa-solid fa-list-check"
                ),
                "record_type": "CAPA Action",
                "record_id": action.pk,
                "record_number": (
                    action.capa.capa_number
                ),
                "title": (
                    action.title
                    or action.description
                    or action.get_action_type_display()
                ),
                "task": "Complete assigned CAPA action",
                "workflow_step": (
                    action.get_status_display()
                ),
                "priority": (
                    action.capa.get_priority_display()
                ),
                "due_date": due_date,
                "is_overdue": bool(
                    due_date
                    and due_date < today
                ),
                "organization_unit": str(
                    action.capa.organization_unit
                ),
                "url": safe_reverse(
                    "quality_capa:action_progress",
                    args=[action.pk],
                ),
            }
        )

    tasks.extend(my_actions)

    tasks.sort(
        key=lambda item: (
            not item["is_overdue"],
            item["due_date"] or date.max,
            item["record_number"],
        )
    )

    can_create = user.is_superuser or any(
        user_has_jkoms_permission(
            user=user,
            permission_code=PERMISSION_CODES["create"],
            organization_unit=capa.organization_unit,
        )
        for capa in visible_capas
    )

    quick_actions = []

    if can_create:
        quick_actions.append(
            {
                "label": "Create CAPA",
                "description": (
                    "Raise a corrective or preventive "
                    "action record."
                ),
                "icon": "fa-solid fa-plus",
                "url": safe_reverse(
                    "quality_capa:create"
                ),
                "color": "yellow",
            }
        )

    module_summary = {
        "code": "QUALITY-CAPA",
        "name": "Quality CAPA",
        "description": (
            "Corrective and preventive action "
            "management."
        ),
        "icon": "fa-solid fa-list-check",
        "url": safe_reverse(
            "quality_capa:list"
        ),
        "open": len(open_capas),
        "pending": len(tasks),
        "overdue": (
            len(overdue_capas)
            + sum(
                1
                for action in my_actions
                if action["is_overdue"]
            )
        ),
    }

    return {
        "module": module_summary,
        "tasks": tasks[:limit],
        "quick_actions": quick_actions,
        "owned_count": sum(
            1
            for capa in open_capas
            if (
                (
                    employee
                    and capa.owner_employee_id
                    == employee.pk
                )
                or (
                    capa.owner_position_id
                    in position_ids
                )
                or capa.created_by_id == user.pk
            )
        ),
    }


def _build_static_module_cards(user):
    """
    Initial module cards.

    Add a module-specific permission and URL as each LTPOMS module
    completes its service layer. Cards with unavailable URLs are omitted.
    """
    definitions = [
        {
            "code": "QUALITY",
            "name": "Quality Management",
            "description": (
                "Quality systems, inspections and "
                "compliance records."
            ),
            "icon": "fa-solid fa-award",
            "url_name": "quality:home",
            "permission": "quality.view",
        },
        {
            "code": "SAFETY",
            "name": "Safety",
            "description": (
                "Safety observations, incidents and "
                "behavior-based safety."
            ),
            "icon": "fa-solid fa-shield-halved",
            "url_name": "safety:home",
            "permission": "safety.view",
        },
        {
            "code": "PRODUCTION",
            "name": "Production",
            "description": (
                "Production planning and operational "
                "performance."
            ),
            "icon": "fa-solid fa-industry",
            "url_name": "production:home",
            "permission": "production.view",
        },
        {
            "code": "ENGINEERING",
            "name": "Engineering",
            "description": (
                "Engineering activities, maintenance "
                "and project work."
            ),
            "icon": "fa-solid fa-gears",
            "url_name": "engineering:home",
            "permission": "engineering.view",
        },
        {
            "code": "TECHNOLOGY",
            "name": "Technology",
            "description": (
                "Technology projects, reviews and "
                "technical workflows."
            ),
            "icon": "fa-solid fa-microchip",
            "url_name": "technology:home",
            "permission": "technology.view",
        },
        {
            "code": "COMMERCIAL",
            "name": "Commercial",
            "description": (
                "Commercial records and business "
                "workflows."
            ),
            "icon": "fa-solid fa-briefcase",
            "url_name": "commercial:home",
            "permission": "commercial.view",
        },
        {
            "code": "HR",
            "name": "Human Resources",
            "description": (
                "Employee and workforce services."
            ),
            "icon": "fa-solid fa-users",
            "url_name": "HR:home",
            "permission": "hr.view",
        },
    ]

    modules = []

    for definition in definitions:
        url = safe_reverse(
            definition["url_name"]
        )

        if url == "#":
            continue

        if not user_can_access_module(
            user=user,
            permission_code=(
                definition["permission"]
            ),
        ):
            continue

        modules.append(
            {
                **definition,
                "url": url,
                "open": 0,
                "pending": 0,
                "overdue": 0,
            }
        )

    return modules


def build_user_workspace(
    *,
    user,
    task_limit=20,
):
    identity = get_user_identity(user)

    modules = []
    tasks = []
    quick_actions = []
    owned_count = 0

    try:
        capa_workspace = _build_capa_workspace(
            user,
            limit=task_limit,
        )
    except ImportError:
        capa_workspace = None

    if capa_workspace:
        modules.append(
            capa_workspace["module"]
        )
        tasks.extend(
            capa_workspace["tasks"]
        )
        quick_actions.extend(
            capa_workspace["quick_actions"]
        )
        owned_count += (
            capa_workspace["owned_count"]
        )

    modules.extend(
        _build_static_module_cards(user)
    )

    tasks.sort(
        key=lambda item: (
            not item["is_overdue"],
            item["due_date"] or date.max,
            item["module_name"],
        )
    )

    return {
        "identity": identity,
        "modules": modules,
        "tasks": tasks[:task_limit],
        "quick_actions": quick_actions,
        "totals": {
            "modules": len(modules),
            "pending": len(tasks),
            "overdue": sum(
                1
                for task in tasks
                if task["is_overdue"]
            ),
            "owned": owned_count,
        },
    }