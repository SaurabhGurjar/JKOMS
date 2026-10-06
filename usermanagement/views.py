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

# =============================================================================
# ADD TO EXISTING IMPORTS
# =============================================================================

from django.utils import timezone

from .forms import (
    CreateUserForm,
    EditUserForm,
    ResetUserPasswordForm,
    RoleAssignmentForm,
    RoleAssignmentScopeFormSet,
    UserFilterForm,

    # Organization Management
    OrganizationUnitTypeForm,
    OrganizationUnitForm,
    DesignationForm,
    PositionForm,
    PositionReportingForm,
    EmployeeForm,
    EmployeePositionAssignmentForm,
)

from .models import (
    EmployeePositionAssignment,
    Role,
    RoleAssignment,

    # Organization Management
    OrganizationUnitType,
    OrganizationUnit,
    Designation,
    Position,
    PositionReporting,
    Employee,
)

User = get_user_model()


# =============================================================================
# USER LIST
# =============================================================================


@staff_required
def user_list(request):
    """
    Display LTPOMS users.

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
    Detailed LTPOMS User view.

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
    Create a LTPOMS User.

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
                "Create a LTPOMS user account "
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
    Edit LTPOMS User account information.

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
    Reset another LTPOMS User password.

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
    Activate or deactivate a LTPOMS User.

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
                "from LTPOMS User Management."
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
    Display LTPOMS Role Assignments.

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
                "Assign a LTPOMS role to a User "
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

    This should become the preferred method once LTPOMS moves into
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
    
# =============================================================================
# ORGANIZATION MANAGEMENT DASHBOARD
# =============================================================================


@staff_required
def organization_dashboard(request):
    """
    Central Organization Management dashboard.

    Provides summary statistics for:
    - Organization Units
    - Designations
    - Positions
    - Employees
    - Position Reporting
    - Employee Position Assignments
    """

    context = {
        "organization_units": (
            OrganizationUnit.objects.count()
        ),

        "active_organization_units": (
            OrganizationUnit.objects
            .filter(is_active=True)
            .count()
        ),

        "designations": (
            Designation.objects.count()
        ),

        "positions": (
            Position.objects.count()
        ),

        "active_positions": (
            Position.objects
            .filter(is_active=True)
            .count()
        ),

        "employees": (
            Employee.objects.count()
        ),

        "active_employees": (
            Employee.objects
            .filter(is_active=True)
            .count()
        ),

        "reporting_relationships": (
            PositionReporting.objects
            .filter(is_active=True)
            .count()
        ),

        "position_assignments": (
            EmployeePositionAssignment.objects
            .filter(is_active=True)
            .count()
        ),
    }

    return render(
        request,
        "usermanagement/organization_dashboard.html",
        context,
    )


# =============================================================================
# ORGANIZATION UNIT TYPE LIST
# =============================================================================


@staff_required
def organization_unit_type_list(request):
    """
    List Organization Unit Types.
    """

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    status_filter = (
        request.GET.get(
            "status",
            "",
        ).strip()
    )

    unit_types = (
        OrganizationUnitType.objects
        .all()
        .order_by("name")
    )

    if search_query:
        unit_types = unit_types.filter(
            Q(code__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    if status_filter == "active":
        unit_types = unit_types.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        unit_types = unit_types.filter(
            is_active=False
        )

    context = {
        "unit_types": unit_types,
        "search_query": search_query,
        "status_filter": status_filter,
    }

    return render(
        request,
        "usermanagement/"
        "organization_unit_type_list.html",
        context,
    )


# =============================================================================
# ORGANIZATION UNIT TYPE CREATE
# =============================================================================


@staff_required
def organization_unit_type_create(request):

    if request.method == "POST":

        form = OrganizationUnitTypeForm(
            request.POST
        )

        if form.is_valid():

            unit_type = form.save()

            messages.success(
                request,
                (
                    f"Organization Unit Type "
                    f"'{unit_type.name}' was created."
                ),
            )

            return redirect(
                "usermanagement:"
                "organization_unit_type_list"
            )

    else:

        form = OrganizationUnitTypeForm(
            initial={
                "is_active": True,
            }
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,
            "page_title": (
                "Add Organization Unit Type"
            ),
            "page_description": (
                "Create a configurable type such as "
                "Plant, Sub-Plant, Function, "
                "Department or Section."
            ),
            "submit_text": "Create Type",
            "back_url_name": (
                "usermanagement:"
                "organization_unit_type_list"
            ),
        },
    )


# =============================================================================
# ORGANIZATION UNIT TYPE EDIT
# =============================================================================


@staff_required
def organization_unit_type_edit(
    request,
    type_id,
):

    unit_type = get_object_or_404(
        OrganizationUnitType,
        pk=type_id,
    )

    if request.method == "POST":

        form = OrganizationUnitTypeForm(
            request.POST,
            instance=unit_type,
        )

        if form.is_valid():

            unit_type = form.save()

            messages.success(
                request,
                (
                    f"Organization Unit Type "
                    f"'{unit_type.name}' was updated."
                ),
            )

            return redirect(
                "usermanagement:"
                "organization_unit_type_list"
            )

    else:

        form = OrganizationUnitTypeForm(
            instance=unit_type
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,
            "page_title": (
                "Edit Organization Unit Type"
            ),
            "page_description": (
                "Update organization type information."
            ),
            "submit_text": "Save Changes",
            "back_url_name": (
                "usermanagement:"
                "organization_unit_type_list"
            ),
        },
    )


# =============================================================================
# ORGANIZATION UNIT TYPE STATUS
# =============================================================================


@staff_required
@require_POST
def organization_unit_type_status_toggle(
    request,
    type_id,
):

    unit_type = get_object_or_404(
        OrganizationUnitType,
        pk=type_id,
    )

    unit_type.is_active = (
        not unit_type.is_active
    )

    unit_type.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    status = (
        "activated"
        if unit_type.is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            f"Organization Unit Type "
            f"'{unit_type.name}' was {status}."
        ),
    )

    return redirect(
        "usermanagement:"
        "organization_unit_type_list"
    )


# =============================================================================
# ORGANIZATION UNIT LIST
# =============================================================================


@staff_required
def organization_unit_list(request):
    """
    List configurable Organization Units.

    Organization structure comes from:
        OrganizationUnit.parent
    """

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    type_filter = (
        request.GET.get(
            "type",
            "",
        ).strip()
    )

    status_filter = (
        request.GET.get(
            "status",
            "",
        ).strip()
    )

    units = (
        OrganizationUnit.objects
        .select_related(
            "unit_type",
            "parent",
        )
        .order_by(
            "display_order",
            "name",
        )
    )

    if search_query:
        units = units.filter(
            Q(code__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(parent__name__icontains=search_query)
        )

    if type_filter:
        units = units.filter(
            unit_type_id=type_filter
        )

    if status_filter == "active":
        units = units.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        units = units.filter(
            is_active=False
        )

    context = {
        "units": units,

        "unit_types": (
            OrganizationUnitType.objects
            .filter(is_active=True)
            .order_by("name")
        ),

        "search_query": search_query,
        "type_filter": type_filter,
        "status_filter": status_filter,
    }

    return render(
        request,
        "usermanagement/"
        "organization_unit_list.html",
        context,
    )


# =============================================================================
# ORGANIZATION UNIT CREATE
# =============================================================================


@staff_required
def organization_unit_create(request):

    if request.method == "POST":

        form = OrganizationUnitForm(
            request.POST
        )

        if form.is_valid():

            unit = form.save()

            messages.success(
                request,
                (
                    f"Organization Unit "
                    f"'{unit.name}' was created."
                ),
            )

            return redirect(
                "usermanagement:"
                "organization_unit_list"
            )

    else:

        form = OrganizationUnitForm(
            initial={
                "is_active": True,
            }
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Add Organization Unit",

            "page_description": (
                "Add a node to the configurable "
                "LTPOMS organization hierarchy."
            ),

            "submit_text":
                "Create Organization Unit",

            "back_url_name": (
                "usermanagement:"
                "organization_unit_list"
            ),
        },
    )


# =============================================================================
# ORGANIZATION UNIT EDIT
# =============================================================================


@staff_required
def organization_unit_edit(
    request,
    unit_id,
):

    unit = get_object_or_404(
        OrganizationUnit.objects
        .select_related(
            "unit_type",
            "parent",
        ),
        pk=unit_id,
    )

    if request.method == "POST":

        form = OrganizationUnitForm(
            request.POST,
            instance=unit,
        )

        if form.is_valid():

            unit = form.save()

            messages.success(
                request,
                (
                    f"Organization Unit "
                    f"'{unit.name}' was updated."
                ),
            )

            return redirect(
                "usermanagement:"
                "organization_unit_list"
            )

    else:

        form = OrganizationUnitForm(
            instance=unit
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Edit Organization Unit",

            "page_description": (
                "Update the organization node, "
                "parent or validity."
            ),

            "submit_text":
                "Save Changes",

            "back_url_name": (
                "usermanagement:"
                "organization_unit_list"
            ),
        },
    )


# =============================================================================
# ORGANIZATION UNIT STATUS
# =============================================================================


@staff_required
@require_POST
def organization_unit_status_toggle(
    request,
    unit_id,
):

    unit = get_object_or_404(
        OrganizationUnit,
        pk=unit_id,
    )

    unit.is_active = (
        not unit.is_active
    )

    unit.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    status = (
        "activated"
        if unit.is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            f"Organization Unit "
            f"'{unit.name}' was {status}."
        ),
    )

    return redirect(
        "usermanagement:"
        "organization_unit_list"
    )


# =============================================================================
# DESIGNATION LIST
# =============================================================================


@staff_required
def designation_list(request):

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    status_filter = (
        request.GET.get(
            "status",
            "",
        ).strip()
    )

    designations = (
        Designation.objects
        .all()
        .order_by(
            "rank_order",
            "name",
        )
    )

    if search_query:
        designations = designations.filter(
            Q(code__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(grade__icontains=search_query)
        )

    if status_filter == "active":
        designations = designations.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        designations = designations.filter(
            is_active=False
        )

    context = {
        "designations": designations,
        "search_query": search_query,
        "status_filter": status_filter,
    }

    return render(
        request,
        "usermanagement/"
        "designation_list.html",
        context,
    )


# =============================================================================
# DESIGNATION CREATE
# =============================================================================


@staff_required
def designation_create(request):

    if request.method == "POST":

        form = DesignationForm(
            request.POST
        )

        if form.is_valid():

            designation = form.save()

            messages.success(
                request,
                (
                    f"Designation "
                    f"'{designation.name}' was created."
                ),
            )

            return redirect(
                "usermanagement:"
                "designation_list"
            )

    else:

        form = DesignationForm(
            initial={
                "is_active": True,
            }
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Add Designation",

            "page_description": (
                "Create an HR designation. "
                "Designation does not determine "
                "LTPOMS authority."
            ),

            "submit_text":
                "Create Designation",

            "back_url_name":
                "usermanagement:designation_list",
        },
    )


# =============================================================================
# DESIGNATION EDIT
# =============================================================================


@staff_required
def designation_edit(
    request,
    designation_id,
):

    designation = get_object_or_404(
        Designation,
        pk=designation_id,
    )

    if request.method == "POST":

        form = DesignationForm(
            request.POST,
            instance=designation,
        )

        if form.is_valid():

            designation = form.save()

            messages.success(
                request,
                (
                    f"Designation "
                    f"'{designation.name}' was updated."
                ),
            )

            return redirect(
                "usermanagement:"
                "designation_list"
            )

    else:

        form = DesignationForm(
            instance=designation
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Edit Designation",

            "page_description":
                "Update HR designation information.",

            "submit_text":
                "Save Changes",

            "back_url_name":
                "usermanagement:designation_list",
        },
    )


# =============================================================================
# DESIGNATION STATUS
# =============================================================================


@staff_required
@require_POST
def designation_status_toggle(
    request,
    designation_id,
):

    designation = get_object_or_404(
        Designation,
        pk=designation_id,
    )

    designation.is_active = (
        not designation.is_active
    )

    designation.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    status = (
        "activated"
        if designation.is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            f"Designation "
            f"'{designation.name}' was {status}."
        ),
    )

    return redirect(
        "usermanagement:"
        "designation_list"
    )


# =============================================================================
# POSITION LIST
# =============================================================================


@staff_required
def position_list(request):

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    organization_filter = (
        request.GET.get(
            "organization",
            "",
        ).strip()
    )

    status_filter = (
        request.GET.get(
            "status",
            "",
        ).strip()
    )

    positions = (
        Position.objects
        .select_related(
            "organization_unit",
            "organization_unit__unit_type",
            "designation",
        )
        .order_by(
            "organization_unit__name",
            "display_order",
            "name",
        )
    )

    if search_query:
        positions = positions.filter(
            Q(code__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(
                organization_unit__name__icontains=
                search_query
            )
            | Q(
                designation__name__icontains=
                search_query
            )
        )

    if organization_filter:
        positions = positions.filter(
            organization_unit_id=
            organization_filter
        )

    if status_filter == "active":
        positions = positions.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        positions = positions.filter(
            is_active=False
        )

    context = {
        "positions": positions,

        "organization_units": (
            OrganizationUnit.objects
            .filter(is_active=True)
            .order_by("name")
        ),

        "search_query": search_query,

        "organization_filter":
            organization_filter,

        "status_filter":
            status_filter,
    }

    return render(
        request,
        "usermanagement/"
        "position_list.html",
        context,
    )


# =============================================================================
# POSITION CREATE
# =============================================================================


@staff_required
def position_create(request):

    if request.method == "POST":

        form = PositionForm(
            request.POST
        )

        if form.is_valid():

            position = form.save()

            messages.success(
                request,
                (
                    f"Position "
                    f"'{position.name}' was created."
                ),
            )

            return redirect(
                "usermanagement:"
                "position_list"
            )

    else:

        form = PositionForm(
            initial={
                "is_active": True,
                "sanctioned_strength": 1,
            }
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Add Position",

            "page_description": (
                "Create an organizational Position "
                "and associate it with an "
                "Organization Unit."
            ),

            "submit_text":
                "Create Position",

            "back_url_name":
                "usermanagement:position_list",
        },
    )


# =============================================================================
# POSITION EDIT
# =============================================================================


@staff_required
def position_edit(
    request,
    position_id,
):

    position = get_object_or_404(
        Position.objects
        .select_related(
            "organization_unit",
            "designation",
        ),
        pk=position_id,
    )

    if request.method == "POST":

        form = PositionForm(
            request.POST,
            instance=position,
        )

        if form.is_valid():

            position = form.save()

            messages.success(
                request,
                (
                    f"Position "
                    f"'{position.name}' was updated."
                ),
            )

            return redirect(
                "usermanagement:"
                "position_list"
            )

    else:

        form = PositionForm(
            instance=position
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Edit Position",

            "page_description": (
                "Update Position classification, "
                "designation and validity."
            ),

            "submit_text":
                "Save Changes",

            "back_url_name":
                "usermanagement:position_list",
        },
    )


# =============================================================================
# POSITION STATUS
# =============================================================================


@staff_required
@require_POST
def position_status_toggle(
    request,
    position_id,
):

    position = get_object_or_404(
        Position,
        pk=position_id,
    )

    position.is_active = (
        not position.is_active
    )

    position.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    status = (
        "activated"
        if position.is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            f"Position "
            f"'{position.name}' was {status}."
        ),
    )

    return redirect(
        "usermanagement:"
        "position_list"
    )


# =============================================================================
# POSITION REPORTING LIST
# =============================================================================


@staff_required
def position_reporting_list(request):

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    relationship_filter = (
        request.GET.get(
            "relationship",
            "",
        ).strip()
    )

    reporting = (
        PositionReporting.objects
        .select_related(
            "position",
            "position__organization_unit",
            "reports_to_position",
            "reports_to_position__organization_unit",
        )
        .order_by(
            "position__name",
        )
    )

    if search_query:
        reporting = reporting.filter(
            Q(
                position__name__icontains=
                search_query
            )
            | Q(
                position__code__icontains=
                search_query
            )
            | Q(
                reports_to_position__name__icontains=
                search_query
            )
            | Q(
                reports_to_position__code__icontains=
                search_query
            )
        )

    if relationship_filter:
        reporting = reporting.filter(
            relationship_type=
            relationship_filter
        )

    context = {
        "reporting_relationships":
            reporting,

        "relationship_types":
            PositionReporting
            .RelationshipType
            .choices,

        "search_query":
            search_query,

        "relationship_filter":
            relationship_filter,
    }

    return render(
        request,
        "usermanagement/"
        "position_reporting_list.html",
        context,
    )


# =============================================================================
# POSITION REPORTING CREATE
# =============================================================================


@staff_required
def position_reporting_create(request):

    if request.method == "POST":

        form = PositionReportingForm(
            request.POST
        )

        if form.is_valid():

            reporting = form.save()

            messages.success(
                request,
                (
                    f"Reporting relationship "
                    f"'{reporting}' was created."
                ),
            )

            return redirect(
                "usermanagement:"
                "position_reporting_list"
            )

    else:

        form = PositionReportingForm(
            initial={
                "relationship_type":
                    PositionReporting
                    .RelationshipType
                    .SOLID_LINE,

                "is_primary": True,
                "is_active": True,
            }
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Add Reporting Relationship",

            "page_description": (
                "Define which Position reports "
                "to another Position."
            ),

            "submit_text":
                "Create Relationship",

            "back_url_name": (
                "usermanagement:"
                "position_reporting_list"
            ),
        },
    )


# =============================================================================
# POSITION REPORTING EDIT
# =============================================================================


@staff_required
def position_reporting_edit(
    request,
    reporting_id,
):

    reporting = get_object_or_404(
        PositionReporting.objects
        .select_related(
            "position",
            "reports_to_position",
        ),
        pk=reporting_id,
    )

    if request.method == "POST":

        form = PositionReportingForm(
            request.POST,
            instance=reporting,
        )

        if form.is_valid():

            reporting = form.save()

            messages.success(
                request,
                (
                    "Position reporting relationship "
                    "was updated successfully."
                ),
            )

            return redirect(
                "usermanagement:"
                "position_reporting_list"
            )

    else:

        form = PositionReportingForm(
            instance=reporting
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Edit Reporting Relationship",

            "page_description": (
                "Update Position reporting, "
                "relationship type or validity."
            ),

            "submit_text":
                "Save Changes",

            "back_url_name": (
                "usermanagement:"
                "position_reporting_list"
            ),
        },
    )


# =============================================================================
# POSITION REPORTING STATUS
# =============================================================================


@staff_required
@require_POST
def position_reporting_status_toggle(
    request,
    reporting_id,
):

    reporting = get_object_or_404(
        PositionReporting,
        pk=reporting_id,
    )

    reporting.is_active = (
        not reporting.is_active
    )

    reporting.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    status = (
        "activated"
        if reporting.is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            "Position reporting relationship "
            f"was {status}."
        ),
    )

    return redirect(
        "usermanagement:"
        "position_reporting_list"
    )


# =============================================================================
# EMPLOYEE LIST
# =============================================================================


@staff_required
def employee_list(request):

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    status_filter = (
        request.GET.get(
            "status",
            "",
        ).strip()
    )

    employees = (
        Employee.objects
        .all()
        .order_by(
            "employee_code",
        )
    )

    if search_query:
        employees = employees.filter(
            Q(employee_code__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(middle_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    if status_filter:
        employees = employees.filter(
            employment_status=
            status_filter
        )

    context = {
        "employees": employees,

        "employment_statuses":
            Employee
            .EmploymentStatus
            .choices,

        "search_query":
            search_query,

        "status_filter":
            status_filter,

        "total_employees":
            Employee.objects.count(),

        "active_employees": (
            Employee.objects
            .filter(
                employment_status=
                Employee
                .EmploymentStatus
                .ACTIVE
            )
            .count()
        ),
    }

    return render(
        request,
        "usermanagement/"
        "employee_list.html",
        context,
    )


# =============================================================================
# EMPLOYEE CREATE
# =============================================================================


@staff_required
def employee_create(request):

    if request.method == "POST":

        form = EmployeeForm(
            request.POST
        )

        if form.is_valid():

            employee = form.save()

            messages.success(
                request,
                (
                    f"Employee "
                    f"'{employee.employee_code}' "
                    "was created."
                ),
            )

            return redirect(
                "usermanagement:"
                "employee_detail",
                employee_id=employee.pk,
            )

    else:

        form = EmployeeForm(
            initial={
                "employment_status":
                    Employee
                    .EmploymentStatus
                    .ACTIVE,

                "is_active": True,
            }
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Add Employee",

            "page_description": (
                "Create an Employee master record. "
                "Position assignment is managed "
                "separately."
            ),

            "submit_text":
                "Create Employee",

            "back_url_name":
                "usermanagement:employee_list",
        },
    )


# =============================================================================
# EMPLOYEE DETAIL
# =============================================================================


@staff_required
def employee_detail(
    request,
    employee_id,
):

    employee = get_object_or_404(
        Employee,
        pk=employee_id,
    )

    position_assignments = (
        EmployeePositionAssignment.objects
        .filter(
            employee=employee
        )
        .select_related(
            "position",
            "position__organization_unit",
            "position__designation",
        )
        .order_by(
            "-is_active",
            "-is_primary",
            "-effective_from",
        )
    )

    current_assignments = (
        position_assignments
        .filter(
            is_active=True
        )
    )

    user_account = getattr(
        employee,
        "user_account",
        None,
    )

    context = {
        "employee": employee,
        "position_assignments":
            position_assignments,
        "current_assignments":
            current_assignments,
        "user_account":
            user_account,
    }

    return render(
        request,
        "usermanagement/"
        "employee_detail.html",
        context,
    )


# =============================================================================
# EMPLOYEE EDIT
# =============================================================================


@staff_required
def employee_edit(
    request,
    employee_id,
):

    employee = get_object_or_404(
        Employee,
        pk=employee_id,
    )

    if request.method == "POST":

        form = EmployeeForm(
            request.POST,
            instance=employee,
        )

        if form.is_valid():

            employee = form.save()

            messages.success(
                request,
                (
                    f"Employee "
                    f"'{employee.employee_code}' "
                    "was updated."
                ),
            )

            return redirect(
                "usermanagement:"
                "employee_detail",
                employee_id=employee.pk,
            )

    else:

        form = EmployeeForm(
            instance=employee
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Edit Employee",

            "page_description":
                "Update Employee master information.",

            "submit_text":
                "Save Changes",

            "back_url_name":
                "usermanagement:employee_list",
        },
    )


# =============================================================================
# EMPLOYEE STATUS
# =============================================================================


@staff_required
@require_POST
def employee_status_toggle(
    request,
    employee_id,
):

    employee = get_object_or_404(
        Employee,
        pk=employee_id,
    )

    employee.is_active = (
        not employee.is_active
    )

    if employee.is_active:
        if (
            employee.employment_status
            == Employee.EmploymentStatus.INACTIVE
        ):
            employee.employment_status = (
                Employee.EmploymentStatus.ACTIVE
            )

    else:
        if (
            employee.employment_status
            == Employee.EmploymentStatus.ACTIVE
        ):
            employee.employment_status = (
                Employee.EmploymentStatus.INACTIVE
            )

    employee.save(
        update_fields=[
            "is_active",
            "employment_status",
            "updated_at",
        ]
    )

    status = (
        "activated"
        if employee.is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            f"Employee "
            f"'{employee.employee_code}' "
            f"was {status}."
        ),
    )

    return redirect(
        "usermanagement:"
        "employee_detail",
        employee_id=employee.pk,
    )


# =============================================================================
# EMPLOYEE POSITION ASSIGNMENT LIST
# =============================================================================


@staff_required
def position_assignment_list(request):

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    assignment_type_filter = (
        request.GET.get(
            "assignment_type",
            "",
        ).strip()
    )

    status_filter = (
        request.GET.get(
            "status",
            "",
        ).strip()
    )

    assignments = (
        EmployeePositionAssignment.objects
        .select_related(
            "employee",
            "position",
            "position__organization_unit",
            "position__designation",
        )
        .order_by(
            "-is_active",
            "-effective_from",
        )
    )

    if search_query:
        assignments = assignments.filter(
            Q(
                employee__employee_code__icontains=
                search_query
            )
            | Q(
                employee__first_name__icontains=
                search_query
            )
            | Q(
                employee__last_name__icontains=
                search_query
            )
            | Q(
                position__name__icontains=
                search_query
            )
            | Q(
                position__code__icontains=
                search_query
            )
        )

    if assignment_type_filter:
        assignments = assignments.filter(
            assignment_type=
            assignment_type_filter
        )

    if status_filter == "active":
        assignments = assignments.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        assignments = assignments.filter(
            is_active=False
        )

    context = {
        "assignments":
            assignments,

        "assignment_types":
            EmployeePositionAssignment
            .AssignmentType
            .choices,

        "search_query":
            search_query,

        "assignment_type_filter":
            assignment_type_filter,

        "status_filter":
            status_filter,
    }

    return render(
        request,
        "usermanagement/"
        "position_assignment_list.html",
        context,
    )


# =============================================================================
# EMPLOYEE POSITION ASSIGNMENT CREATE
# =============================================================================


@staff_required
def position_assignment_create(
    request,
):

    initial = {
        "is_active": True,
        "is_primary": True,
        "effective_from":
            timezone.localdate(),
    }

    # Optional convenience:
    # /position-assignments/add/?employee=5
    employee_id = request.GET.get(
        "employee"
    )

    if employee_id:
        initial["employee"] = employee_id

    if request.method == "POST":

        form = (
            EmployeePositionAssignmentForm(
                request.POST
            )
        )

        if form.is_valid():

            assignment = form.save()

            messages.success(
                request,
                (
                    f"Position "
                    f"'{assignment.position.name}' "
                    "was assigned to "
                    f"'{assignment.employee.full_name}'."
                ),
            )

            return redirect(
                "usermanagement:"
                "employee_detail",
                employee_id=
                    assignment.employee_id,
            )

    else:

        form = (
            EmployeePositionAssignmentForm(
                initial=initial
            )
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Assign Employee Position",

            "page_description": (
                "Assign an Employee to a Position "
                "with assignment type, primary "
                "indicator and effective dates."
            ),

            "submit_text":
                "Create Assignment",

            "back_url_name": (
                "usermanagement:"
                "position_assignment_list"
            ),
        },
    )


# =============================================================================
# EMPLOYEE POSITION ASSIGNMENT EDIT
# =============================================================================


@staff_required
def position_assignment_edit(
    request,
    assignment_id,
):

    assignment = get_object_or_404(
        EmployeePositionAssignment.objects
        .select_related(
            "employee",
            "position",
        ),
        pk=assignment_id,
    )

    if request.method == "POST":

        form = (
            EmployeePositionAssignmentForm(
                request.POST,
                instance=assignment,
            )
        )

        if form.is_valid():

            assignment = form.save()

            messages.success(
                request,
                (
                    "Employee Position Assignment "
                    "was updated successfully."
                ),
            )

            return redirect(
                "usermanagement:"
                "employee_detail",
                employee_id=
                    assignment.employee_id,
            )

    else:

        form = (
            EmployeePositionAssignmentForm(
                instance=assignment
            )
        )

    return render(
        request,
        "usermanagement/"
        "organization_master_form.html",
        {
            "form": form,

            "page_title":
                "Edit Position Assignment",

            "page_description": (
                "Update Employee Position, "
                "assignment type or effective dates."
            ),

            "submit_text":
                "Save Changes",

            "back_url_name": (
                "usermanagement:"
                "position_assignment_list"
            ),
        },
    )


# =============================================================================
# EMPLOYEE POSITION ASSIGNMENT STATUS
# =============================================================================


@staff_required
@require_POST
def position_assignment_status_toggle(
    request,
    assignment_id,
):

    assignment = get_object_or_404(
        EmployeePositionAssignment,
        pk=assignment_id,
    )

    assignment.is_active = (
        not assignment.is_active
    )

    # When closing an assignment, preserve
    # its effective history automatically.
    if (
        not assignment.is_active
        and assignment.effective_to is None
    ):
        assignment.effective_to = (
            timezone.localdate()
        )

    assignment.save(
        update_fields=[
            "is_active",
            "effective_to",
            "updated_at",
        ]
    )

    status = (
        "activated"
        if assignment.is_active
        else "closed"
    )

    messages.success(
        request,
        (
            "Employee Position Assignment "
            f"was {status}."
        ),
    )

    return redirect(
        "usermanagement:"
        "employee_detail",
        employee_id=
            assignment.employee_id,
    )