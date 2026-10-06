# usermanagement/views.py

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from .decorators import (
    can_manage_user,
    staff_required,
)

from .forms import (
    CreateUserForm,
    EditUserForm,
    ResetUserPasswordForm,
    RoleAssignmentForm,
    RoleAssignmentScopeFormSet,
    UserFilterForm,
)

from .models import (
    EmployeePositionAssignment,
    Role,
    RoleAssignment,
)

from .services import (
    get_direct_role_assignments,
    get_effective_roles,
    get_position_role_assignments,
    get_primary_position_assignment,
    get_reporting_manager_users,
    get_user_authorization_summary,
    get_user_position_assignments,
)


User = get_user_model()


# =============================================================================
# USER LIST
# =============================================================================


@staff_required
def user_list(request):
    """
    Display JKOMS users.

    Supports:
    - Search
    - Status filter
    - Effective role filter
    - Summary statistics

    Effective role filtering includes:
    - Direct User RoleAssignment
    - Position-based RoleAssignment
    """

    filter_form = UserFilterForm(
        request.GET or None
    )

    users = (
        User.objects
        .select_related("employee")
        .order_by("-date_joined")
    )

    search_query = ""
    status_filter = ""
    selected_role = None

    if filter_form.is_valid():

        search_query = (
            filter_form.cleaned_data.get("search")
            or ""
        ).strip()

        status_filter = (
            filter_form.cleaned_data.get("status")
            or ""
        )

        selected_role = (
            filter_form.cleaned_data.get("role")
        )

        # ---------------------------------------------------------------------
        # SEARCH
        # ---------------------------------------------------------------------

        if search_query:
            users = users.filter(
                Q(
                    username__icontains=search_query
                )
                | Q(
                    first_name__icontains=search_query
                )
                | Q(
                    last_name__icontains=search_query
                )
                | Q(
                    email__icontains=search_query
                )
                | Q(
                    employee__employee_code__icontains=search_query
                )
                | Q(
                    employee__first_name__icontains=search_query
                )
                | Q(
                    employee__middle_name__icontains=search_query
                )
                | Q(
                    employee__last_name__icontains=search_query
                )
            )

        # ---------------------------------------------------------------------
        # STATUS FILTER
        # ---------------------------------------------------------------------

        if status_filter == "active":
            users = users.filter(
                is_active=True
            )

        elif status_filter == "inactive":
            users = users.filter(
                is_active=False
            )

        # ---------------------------------------------------------------------
        # EFFECTIVE ROLE FILTER
        #
        # Includes:
        #   User -> RoleAssignment
        #
        # and:
        #   User -> Employee -> Position -> RoleAssignment
        # ---------------------------------------------------------------------

        if selected_role:

            direct_user_ids = (
                RoleAssignment.objects
                .filter(
                    role=selected_role,
                    user__isnull=False,
                    is_active=True,
                )
                .values_list(
                    "user_id",
                    flat=True,
                )
            )

            role_position_ids = (
                RoleAssignment.objects
                .filter(
                    role=selected_role,
                    position__isnull=False,
                    is_active=True,
                )
                .values_list(
                    "position_id",
                    flat=True,
                )
            )

            employee_ids = (
                EmployeePositionAssignment.objects
                .filter(
                    position_id__in=role_position_ids,
                    is_active=True,
                )
                .values_list(
                    "employee_id",
                    flat=True,
                )
            )

            users = users.filter(
                Q(
                    id__in=direct_user_ids
                )
                | Q(
                    employee_id__in=employee_ids
                )
            )

    users = users.distinct()

    # -------------------------------------------------------------------------
    # CONTEXT
    # -------------------------------------------------------------------------

    context = {
        "users": users,
        "filter_form": filter_form,

        # Kept separately because existing template may still expect them.
        "search_query": search_query,
        "status_filter": status_filter,
        "role_filter": (
            str(selected_role.pk)
            if selected_role
            else ""
        ),

        "roles": (
            Role.objects
            .filter(is_active=True)
            .select_related(
                "role_type",
                "module",
            )
            .order_by("name")
        ),

        # Dashboard counts
        "total_users": (
            User.objects.count()
        ),

        "active_users": (
            User.objects
            .filter(is_active=True)
            .count()
        ),

        "inactive_users": (
            User.objects
            .filter(is_active=False)
            .count()
        ),

        "staff_users": (
            User.objects
            .filter(is_staff=True)
            .count()
        ),
    }

    return render(
        request,
        "usermanagement/user_list.html",
        context,
    )


# =============================================================================
# USER DETAIL
# =============================================================================


@staff_required
def user_detail(request, user_id):
    """
    Detailed JKOMS User view.

    Displays:
    - Account
    - Linked Employee
    - Position assignments
    - Primary position
    - Reporting manager
    - Direct roles
    - Position inherited roles
    - Effective roles
    """

    selected_user = get_object_or_404(
        User.objects.select_related(
            "employee"
        ),
        pk=user_id,
    )

    authorization = (
        get_user_authorization_summary(
            selected_user
        )
    )

    primary_position_assignment = (
        get_primary_position_assignment(
            selected_user
        )
    )

    reporting_manager_users = (
        get_reporting_manager_users(
            selected_user
        )
    )

    context = {
        "selected_user": selected_user,

        "position_assignments": (
            authorization["positions"]
        ),

        "primary_position_assignment":
            primary_position_assignment,

        "direct_role_assignments": (
            authorization[
                "direct_role_assignments"
            ]
        ),

        "position_role_assignments": (
            authorization[
                "position_role_assignments"
            ]
        ),

        "effective_roles": (
            authorization["roles"]
        ),

        "reporting_manager_users":
            reporting_manager_users,
    }

    return render(
        request,
        "usermanagement/user_detail.html",
        context,
    )


# =============================================================================
# CREATE USER
# =============================================================================


@staff_required
def user_create(request):
    """
    Create a JKOMS User.

    Creating a User does not automatically assign Roles.

    Role authority is managed separately through RoleAssignment.
    """

    if request.method == "POST":

        form = CreateUserForm(
            request.POST
        )

        if form.is_valid():

            with transaction.atomic():
                user = form.save()

            messages.success(
                request,
                (
                    f"User '{user.username}' "
                    "was created successfully."
                ),
            )

            return redirect(
                "usermanagement:user_detail",
                user_id=user.pk,
            )

    else:

        form = CreateUserForm(
            initial={
                "is_active": True,
            }
        )

    return render(
        request,
        "usermanagement/user_form.html",
        {
            "form": form,

            "page_title": "Add User",

            "page_description": (
                "Create a JKOMS user account "
                "and link it to an employee."
            ),

            "submit_text": "Create User",

            "is_create": True,
        },
    )


# =============================================================================
# EDIT USER
# =============================================================================


@staff_required
@can_manage_user
def user_edit(request, user_id):
    """
    Edit JKOMS User account information.

    Roles are deliberately not edited through this form.
    """

    selected_user = get_object_or_404(
        User.objects.select_related(
            "employee"
        ),
        pk=user_id,
    )

    if request.method == "POST":

        form = EditUserForm(
            request.POST,
            instance=selected_user,
        )

        if form.is_valid():

            with transaction.atomic():
                updated_user = form.save()

            messages.success(
                request,
                (
                    f"User "
                    f"'{updated_user.username}' "
                    "was updated successfully."
                ),
            )

            return redirect(
                "usermanagement:user_detail",
                user_id=updated_user.pk,
            )

    else:

        form = EditUserForm(
            instance=selected_user
        )

    position_assignments = (
        get_user_position_assignments(
            selected_user
        )
    )

    direct_role_assignments = (
        get_direct_role_assignments(
            selected_user
        )
    )

    position_role_assignments = (
        get_position_role_assignments(
            selected_user
        )
    )

    context = {
        "form": form,

        "selected_user":
            selected_user,

        "position_assignments":
            position_assignments,

        "direct_role_assignments":
            direct_role_assignments,

        "position_role_assignments":
            position_role_assignments,

        "page_title":
            "Edit User",

        "page_description": (
            "Update account information "
            "and employee linkage."
        ),

        "submit_text":
            "Save Changes",

        "is_create":
            False,
    }

    return render(
        request,
        "usermanagement/user_form.html",
        context,
    )


# =============================================================================
# RESET USER PASSWORD
# =============================================================================


@staff_required
@can_manage_user
def user_password_reset(
    request,
    user_id,
):
    """
    Reset another JKOMS User password.

    Uses Django password validation.
    """

    selected_user = get_object_or_404(
        User,
        pk=user_id,
    )

    if request.method == "POST":

        form = ResetUserPasswordForm(
            selected_user,
            request.POST,
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                (
                    f"Password for "
                    f"'{selected_user.username}' "
                    "was changed successfully."
                ),
            )

            return redirect(
                "usermanagement:user_detail",
                user_id=selected_user.pk,
            )

    else:

        form = ResetUserPasswordForm(
            selected_user
        )

    return render(
        request,
        "usermanagement/password_reset.html",
        {
            "form": form,
            "selected_user": selected_user,
        },
    )


# =============================================================================
# ACTIVATE / DEACTIVATE USER
# =============================================================================


@staff_required
@can_manage_user
@require_POST
def user_status_toggle(
    request,
    user_id,
):
    """
    Activate or deactivate a JKOMS User.

    Security:
    - POST only
    - Self-deactivation blocked
    - Superuser status cannot be toggled through this screen
    """

    selected_user = get_object_or_404(
        User,
        pk=user_id,
    )

    # -------------------------------------------------------------------------
    # CANNOT DEACTIVATE OWN ACCOUNT
    # -------------------------------------------------------------------------

    if selected_user.pk == request.user.pk:

        messages.error(
            request,
            (
                "You cannot activate or deactivate "
                "your own account from this screen."
            ),
        )

        return redirect(
            "usermanagement:user_detail",
            user_id=selected_user.pk,
        )

    # -------------------------------------------------------------------------
    # PROTECT SUPERUSER
    # -------------------------------------------------------------------------

    if selected_user.is_superuser:

        messages.error(
            request,
            (
                "Superuser status cannot be changed "
                "from JKOMS User Management."
            ),
        )

        return redirect(
            "usermanagement:user_detail",
            user_id=selected_user.pk,
        )

    # -------------------------------------------------------------------------
    # TOGGLE
    # -------------------------------------------------------------------------

    selected_user.is_active = (
        not selected_user.is_active
    )

    selected_user.save(
        update_fields=[
            "is_active",
        ]
    )

    status_text = (
        "activated"
        if selected_user.is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            f"User '{selected_user.username}' "
            f"was {status_text} successfully."
        ),
    )

    return redirect(
        "usermanagement:user_detail",
        user_id=selected_user.pk,
    )


# =============================================================================
# ROLE ASSIGNMENT LIST
# =============================================================================


@staff_required
def role_assignment_list(request):
    """
    Display JKOMS Role Assignments.

    Supports User-based and Position-based assignments.
    """

    search_query = (
        request.GET.get(
            "search",
            "",
        )
        .strip()
    )

    role_filter = (
        request.GET.get(
            "role",
            "",
        )
        .strip()
    )

    assignment_type = (
        request.GET.get(
            "type",
            "",
        )
        .strip()
    )

    assignments = (
        RoleAssignment.objects
        .select_related(
            "role",
            "role__role_type",
            "role__module",
            "user",
            "user__employee",
            "position",
            "position__organization_unit",
            "assigned_by",
        )
        .prefetch_related(
            "scopes",
            "scopes__organization_unit",
            "scopes__module",
        )
        .order_by(
            "role__name"
        )
    )

    # -------------------------------------------------------------------------
    # SEARCH
    # -------------------------------------------------------------------------

    if search_query:

        assignments = assignments.filter(
            Q(
                role__code__icontains=
                search_query
            )
            | Q(
                role__name__icontains=
                search_query
            )
            | Q(
                user__username__icontains=
                search_query
            )
            | Q(
                user__employee__employee_code__icontains=
                search_query
            )
            | Q(
                position__code__icontains=
                search_query
            )
            | Q(
                position__name__icontains=
                search_query
            )
        )

    # -------------------------------------------------------------------------
    # ROLE FILTER
    # -------------------------------------------------------------------------

    if role_filter:
        assignments = assignments.filter(
            role_id=role_filter
        )

    # -------------------------------------------------------------------------
    # TARGET TYPE FILTER
    # -------------------------------------------------------------------------

    if assignment_type == "user":

        assignments = assignments.filter(
            user__isnull=False
        )

    elif assignment_type == "position":

        assignments = assignments.filter(
            position__isnull=False
        )

    context = {
        "assignments":
            assignments.distinct(),

        "roles": (
            Role.objects
            .filter(is_active=True)
            .order_by("name")
        ),

        "search_query":
            search_query,

        "role_filter":
            role_filter,

        "assignment_type":
            assignment_type,
    }

    return render(
        request,
        "usermanagement/"
        "role_assignment_list.html",
        context,
    )


# =============================================================================
# CREATE ROLE ASSIGNMENT
# =============================================================================


@staff_required
def role_assignment_create(request):
    """
    Create a RoleAssignment and zero or more Scope records.

    If no Scope rows are provided, the RoleAssignment is considered
    unrestricted by the authorization service.
    """

    assignment = RoleAssignment()

    if request.method == "POST":

        form = RoleAssignmentForm(
            request.POST,
            instance=assignment,
        )

        scope_formset = (
            RoleAssignmentScopeFormSet(
                request.POST,
                instance=assignment,
                prefix="scopes",
            )
        )

        if (
            form.is_valid()
            and scope_formset.is_valid()
        ):

            with transaction.atomic():

                assignment = form.save(
                    commit=False
                )

                assignment.assigned_by = (
                    request.user
                )

                assignment.save()

                scope_formset.instance = (
                    assignment
                )

                scope_formset.save()

            messages.success(
                request,
                (
                    f"Role '{assignment.role.name}' "
                    "was assigned successfully."
                ),
            )

            return redirect(
                "usermanagement:"
                "role_assignment_list"
            )

    else:

        form = RoleAssignmentForm(
            instance=assignment,
            initial={
                "is_active": True,
            },
        )

        scope_formset = (
            RoleAssignmentScopeFormSet(
                instance=assignment,
                prefix="scopes",
            )
        )

    return render(
        request,
        "usermanagement/"
        "role_assignment_form.html",
        {
            "form": form,
            "scope_formset":
                scope_formset,

            "page_title":
                "Add Role Assignment",

            "page_description": (
                "Assign a JKOMS role to a User "
                "or Position and configure its scope."
            ),

            "submit_text":
                "Create Assignment",

            "is_create":
                True,
        },
    )


# =============================================================================
# EDIT ROLE ASSIGNMENT
# =============================================================================


@staff_required
def role_assignment_edit(
    request,
    assignment_id,
):
    """
    Edit a RoleAssignment and its scopes.
    """

    assignment = get_object_or_404(
        RoleAssignment.objects
        .select_related(
            "role",
            "user",
            "position",
        ),
        pk=assignment_id,
    )

    if request.method == "POST":

        form = RoleAssignmentForm(
            request.POST,
            instance=assignment,
        )

        scope_formset = (
            RoleAssignmentScopeFormSet(
                request.POST,
                instance=assignment,
                prefix="scopes",
            )
        )

        if (
            form.is_valid()
            and scope_formset.is_valid()
        ):

            with transaction.atomic():

                assignment = form.save()

                scope_formset.instance = (
                    assignment
                )

                scope_formset.save()

            messages.success(
                request,
                "Role Assignment was updated successfully.",
            )

            return redirect(
                "usermanagement:"
                "role_assignment_list"
            )

    else:

        form = RoleAssignmentForm(
            instance=assignment
        )

        scope_formset = (
            RoleAssignmentScopeFormSet(
                instance=assignment,
                prefix="scopes",
            )
        )

    return render(
        request,
        "usermanagement/"
        "role_assignment_form.html",
        {
            "form": form,

            "scope_formset":
                scope_formset,

            "assignment":
                assignment,

            "page_title":
                "Edit Role Assignment",

            "page_description": (
                "Update role assignment, "
                "validity and authorization scope."
            ),

            "submit_text":
                "Save Changes",

            "is_create":
                False,
        },
    )


# =============================================================================
# DELETE ROLE ASSIGNMENT
# =============================================================================


@staff_required
@require_POST
def role_assignment_delete(
    request,
    assignment_id,
):
    """
    Delete a RoleAssignment.

    Because Scope uses CASCADE, related Scope records are also removed.

    For historical production usage, consider changing this behavior
    later to deactivation rather than physical deletion.
    """

    assignment = get_object_or_404(
        RoleAssignment.objects
        .select_related(
            "role",
            "user",
            "position",
        ),
        pk=assignment_id,
    )

    role_name = assignment.role.name

    assignment.delete()

    messages.success(
        request,
        (
            f"Role Assignment for "
            f"'{role_name}' was deleted."
        ),
    )

    return redirect(
        "usermanagement:"
        "role_assignment_list"
    )


# =============================================================================
# TOGGLE ROLE ASSIGNMENT ACTIVE STATUS
# =============================================================================


@staff_required
@require_POST
def role_assignment_status_toggle(
    request,
    assignment_id,
):
    """
    Activate/deactivate a RoleAssignment without deleting history.

    This should become the preferred method once JKOMS moves into
    operational use.
    """

    assignment = get_object_or_404(
        RoleAssignment,
        pk=assignment_id,
    )

    assignment.is_active = (
        not assignment.is_active
    )

    assignment.save(
        update_fields=[
            "is_active",
        ]
    )

    status_text = (
        "activated"
        if assignment.is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            f"Role Assignment was "
            f"{status_text} successfully."
        ),
    )

    return redirect(
        "usermanagement:"
        "role_assignment_list"
    )