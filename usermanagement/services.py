# usermanagement/services.py

from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .models import (
    EmployeePositionAssignment,
    OrganizationUnit,
    Permission,
    Position,
    PositionReporting,
    Role,
    RoleAssignment,
    RoleAssignmentScope,
)


User = get_user_model()


# =============================================================================
# DATE / VALIDITY HELPERS
# =============================================================================


def get_current_date():
    """
    Return the current application-local date.

    Using Django timezone utilities ensures this follows the
    configured TIME_ZONE when USE_TZ = True.
    """
    return timezone.localdate()


def _date_range_is_active(
    valid_from=None,
    valid_to=None,
    reference_date=None,
):
    """
    Check whether an effective-dated record is valid on a given date.

    Both dates are inclusive.

    None means open-ended.
    """

    reference_date = reference_date or get_current_date()

    if valid_from and reference_date < valid_from:
        return False

    if valid_to and reference_date > valid_to:
        return False

    return True


def _apply_active_date_filter(
    queryset,
    from_field,
    to_field,
    reference_date=None,
):
    """
    Apply a reusable effective-date filter to a QuerySet.

    Example:

        _apply_active_date_filter(
            RoleAssignment.objects.filter(is_active=True),
            "valid_from",
            "valid_to",
        )
    """

    reference_date = reference_date or get_current_date()

    return queryset.filter(
        Q(**{f"{from_field}__isnull": True})
        | Q(**{f"{from_field}__lte": reference_date}),
        Q(**{f"{to_field}__isnull": True})
        | Q(**{f"{to_field}__gte": reference_date}),
    )


# =============================================================================
# EMPLOYEE / POSITION SERVICES
# =============================================================================


def get_active_position_assignments(
    employee,
    reference_date=None,
):
    """
    Return all active/effective Position assignments for an Employee.

    Includes:
    - Permanent
    - Acting
    - Additional Charge
    - Temporary
    """

    if not employee:
        return EmployeePositionAssignment.objects.none()

    reference_date = reference_date or get_current_date()

    queryset = (
        EmployeePositionAssignment.objects
        .filter(
            employee=employee,
            is_active=True,
        )
        .select_related(
            "position",
            "position__organization_unit",
            "position__designation",
        )
        .order_by(
            "-is_primary",
            "-effective_from",
        )
    )

    return _apply_active_date_filter(
        queryset=queryset,
        from_field="effective_from",
        to_field="effective_to",
        reference_date=reference_date,
    )


def get_user_position_assignments(
    user,
    reference_date=None,
):
    """
    Return all current Position assignments associated with a User
    through the linked Employee record.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return EmployeePositionAssignment.objects.none()

    employee = getattr(user, "employee", None)

    if not employee:
        return EmployeePositionAssignment.objects.none()

    return get_active_position_assignments(
        employee=employee,
        reference_date=reference_date,
    )


def get_user_positions(
    user,
    reference_date=None,
):
    """
    Return the active Position objects held by a User.
    """

    assignments = get_user_position_assignments(
        user=user,
        reference_date=reference_date,
    )

    position_ids = assignments.values_list(
        "position_id",
        flat=True,
    )

    return (
        Position.objects
        .filter(
            id__in=position_ids,
            is_active=True,
        )
        .select_related(
            "organization_unit",
            "designation",
        )
        .distinct()
    )


def get_primary_position_assignment(
    user,
    reference_date=None,
):
    """
    Return the User's active primary Position assignment.

    Falls back to the first current assignment if no assignment has
    been marked primary.
    """

    assignments = get_user_position_assignments(
        user=user,
        reference_date=reference_date,
    )

    primary = assignments.filter(
        is_primary=True,
    ).first()

    if primary:
        return primary

    return assignments.first()


def get_primary_position(
    user,
    reference_date=None,
):
    """
    Return the User's current primary Position.
    """

    assignment = get_primary_position_assignment(
        user=user,
        reference_date=reference_date,
    )

    if not assignment:
        return None

    return assignment.position


# =============================================================================
# REPORTING STRUCTURE SERVICES
# =============================================================================


def get_primary_reporting_relationship(
    position,
    reference_date=None,
):
    """
    Return the active primary SOLID_LINE reporting relationship
    for a Position.
    """

    if not position:
        return None

    reference_date = reference_date or get_current_date()

    queryset = (
        PositionReporting.objects
        .filter(
            position=position,
            relationship_type=(
                PositionReporting.RelationshipType.SOLID_LINE
            ),
            is_primary=True,
            is_active=True,
        )
        .select_related(
            "reports_to_position",
            "reports_to_position__organization_unit",
            "reports_to_position__designation",
        )
    )

    queryset = _apply_active_date_filter(
        queryset=queryset,
        from_field="valid_from",
        to_field="valid_to",
        reference_date=reference_date,
    )

    return queryset.first()


def get_reporting_manager_position(
    position,
    reference_date=None,
):
    """
    Return the primary manager Position for a Position.
    """

    relationship = get_primary_reporting_relationship(
        position=position,
        reference_date=reference_date,
    )

    if not relationship:
        return None

    return relationship.reports_to_position


def get_position_occupants(
    position,
    reference_date=None,
):
    """
    Return active EmployeePositionAssignments occupying a Position.

    This is useful because a Position may temporarily have:
    - normal incumbent
    - acting incumbent
    - additional charge
    """

    if not position:
        return EmployeePositionAssignment.objects.none()

    reference_date = reference_date or get_current_date()

    queryset = (
        EmployeePositionAssignment.objects
        .filter(
            position=position,
            is_active=True,
            employee__is_active=True,
        )
        .select_related(
            "employee",
            "position",
        )
        .order_by(
            "-is_primary",
            "-effective_from",
        )
    )

    return _apply_active_date_filter(
        queryset=queryset,
        from_field="effective_from",
        to_field="effective_to",
        reference_date=reference_date,
    )


def get_reporting_manager_users(
    user,
    reference_date=None,
):
    """
    Resolve the current User account(s) occupying the manager Position
    of the User's primary Position.

    Returns a User QuerySet.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return User.objects.none()

    position = get_primary_position(
        user=user,
        reference_date=reference_date,
    )

    if not position:
        return User.objects.none()

    manager_position = get_reporting_manager_position(
        position=position,
        reference_date=reference_date,
    )

    if not manager_position:
        return User.objects.none()

    occupant_employee_ids = get_position_occupants(
        position=manager_position,
        reference_date=reference_date,
    ).values_list(
        "employee_id",
        flat=True,
    )

    return User.objects.filter(
        employee_id__in=occupant_employee_ids,
        is_active=True,
    ).distinct()


# =============================================================================
# ORGANIZATION TREE SERVICES
# =============================================================================


def get_organization_ancestors(
    organization_unit,
    include_self=False,
):
    """
    Return a Python list containing the Organization Unit and/or
    its parents from the current node upward.

    Example:

        Tube Plant
        -> Sub-Plant 2
        -> Quality
        -> LTP
    """

    if not organization_unit:
        return []

    units = []

    current = (
        organization_unit
        if include_self
        else organization_unit.parent
    )

    visited = set()

    while current:

        if current.pk in visited:
            # Defensive protection if invalid/circular data somehow
            # exists despite model validation.
            break

        visited.add(current.pk)
        units.append(current)

        current = current.parent

    return units


def get_organization_descendant_ids(
    organization_unit,
    include_self=True,
):
    """
    Return IDs for an OrganizationUnit and all descendants.

    The current schema uses an adjacency-list parent FK, therefore
    traversal is done iteratively.

    This is sufficient for JKOMS master data scale. If the organization
    grows into a very large hierarchy, this implementation can later be
    replaced by PostgreSQL recursive CTE logic without changing callers.
    """

    if not organization_unit:
        return []

    result = []

    if include_self:
        result.append(organization_unit.pk)

    pending = [organization_unit.pk]

    while pending:

        children = list(
            OrganizationUnit.objects
            .filter(
                parent_id__in=pending,
                is_active=True,
            )
            .values_list(
                "id",
                flat=True,
            )
        )

        if not children:
            break

        new_children = [
            child_id
            for child_id in children
            if child_id not in result
        ]

        if not new_children:
            break

        result.extend(new_children)
        pending = new_children

    return result


def organization_unit_is_within_scope(
    organization_unit,
    scope,
):
    """
    Determine whether an OrganizationUnit falls inside a
    RoleAssignmentScope.

    Rules:

    1. Blank organization scope means no organization restriction.
    2. Exact unit matches.
    3. If include_descendants=True, child units also match.
    """

    if scope.organization_unit_id is None:
        return True

    if organization_unit is None:
        return False

    if organization_unit.pk == scope.organization_unit_id:
        return True

    if not scope.include_descendants:
        return False

    current = organization_unit.parent

    visited = set()

    while current:

        if current.pk in visited:
            break

        visited.add(current.pk)

        if current.pk == scope.organization_unit_id:
            return True

        current = current.parent

    return False


# =============================================================================
# ROLE ASSIGNMENT SERVICES
# =============================================================================


def get_direct_role_assignments(
    user,
    reference_date=None,
):
    """
    Return active RoleAssignments made directly to a User.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return RoleAssignment.objects.none()

    reference_date = reference_date or get_current_date()

    queryset = (
        RoleAssignment.objects
        .filter(
            user=user,
            is_active=True,
            role__is_active=True,
        )
        .select_related(
            "role",
            "role__role_type",
            "role__module",
            "user",
        )
        .prefetch_related(
            "scopes",
            "scopes__organization_unit",
            "scopes__module",
        )
    )

    return _apply_active_date_filter(
        queryset=queryset,
        from_field="valid_from",
        to_field="valid_to",
        reference_date=reference_date,
    )


def get_position_role_assignments(
    user,
    reference_date=None,
):
    """
    Return active RoleAssignments inherited through any current
    Employee Position Assignment.

    This is what makes organizational authority follow the Position
    rather than the employee.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return RoleAssignment.objects.none()

    position_ids = get_user_position_assignments(
        user=user,
        reference_date=reference_date,
    ).values_list(
        "position_id",
        flat=True,
    )

    if not position_ids:
        return RoleAssignment.objects.none()

    queryset = (
        RoleAssignment.objects
        .filter(
            position_id__in=position_ids,
            is_active=True,
            role__is_active=True,
        )
        .select_related(
            "role",
            "role__role_type",
            "role__module",
            "position",
            "position__organization_unit",
        )
        .prefetch_related(
            "scopes",
            "scopes__organization_unit",
            "scopes__module",
        )
    )

    return _apply_active_date_filter(
        queryset=queryset,
        from_field="valid_from",
        to_field="valid_to",
        reference_date=reference_date,
    )


def get_effective_role_assignments(
    user,
    reference_date=None,
):
    """
    Return all effective RoleAssignments for a User.

    Includes:
    - Direct user RoleAssignment
    - RoleAssignments inherited through current Positions

    Returned as a list because the records originate from two
    independent assignment paths.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return []

    direct_assignments = list(
        get_direct_role_assignments(
            user=user,
            reference_date=reference_date,
        )
    )

    position_assignments = list(
        get_position_role_assignments(
            user=user,
            reference_date=reference_date,
        )
    )

    assignments = []
    seen = set()

    for assignment in direct_assignments + position_assignments:

        if assignment.pk in seen:
            continue

        seen.add(assignment.pk)
        assignments.append(assignment)

    return assignments


def get_effective_roles(
    user,
    reference_date=None,
):
    """
    Return Role objects effectively held by a User.

    Includes both User-based and Position-based assignments.
    """

    assignments = get_effective_role_assignments(
        user=user,
        reference_date=reference_date,
    )

    role_ids = {
        assignment.role_id
        for assignment in assignments
    }

    if not role_ids:
        return Role.objects.none()

    return (
        Role.objects
        .filter(
            id__in=role_ids,
            is_active=True,
        )
        .select_related(
            "role_type",
            "module",
        )
        .order_by(
            "name",
        )
    )


def user_has_role(
    user,
    role_code,
    reference_date=None,
):
    """
    Check whether a User effectively holds a Role.

    Example:

        user_has_role(
            request.user,
            "QUALITY_APPROVER",
        )
    """

    if not user or not getattr(user, "is_authenticated", False):
        return False

    if user.is_superuser:
        return True

    return get_effective_roles(
        user=user,
        reference_date=reference_date,
    ).filter(
        code=role_code,
        is_active=True,
    ).exists()


# =============================================================================
# ROLE SCOPE SERVICES
# =============================================================================


def get_assignment_scopes(
    role_assignment,
):
    """
    Return all scopes belonging to a RoleAssignment.
    """

    if not role_assignment:
        return RoleAssignmentScope.objects.none()

    return (
        RoleAssignmentScope.objects
        .filter(
            role_assignment=role_assignment,
        )
        .select_related(
            "organization_unit",
            "module",
        )
    )


def assignment_applies_to_scope(
    role_assignment,
    organization_unit=None,
    module=None,
):
    """
    Determine whether a RoleAssignment applies to the requested
    organization/module context.

    Scope semantics:

    No RoleAssignmentScope rows
        -> Assignment is unrestricted.

    Scope row organization_unit=None
        -> No organization restriction for that row.

    Scope row module=None
        -> No module restriction for that row.

    Multiple scope rows
        -> Any matching row is sufficient.
    """

    scopes = list(
        get_assignment_scopes(
            role_assignment=role_assignment,
        )
    )

    # No scopes means globally applicable assignment.
    if not scopes:
        return True

    for scope in scopes:

        # -------------------------------------------------------------
        # MODULE CHECK
        # -------------------------------------------------------------

        module_matches = True

        if scope.module_id:

            if module is None:
                module_matches = False

            elif isinstance(module, str):
                module_matches = (
                    scope.module.code == module
                )

            else:
                module_matches = (
                    scope.module_id == module.pk
                )

        if not module_matches:
            continue

        # -------------------------------------------------------------
        # ORGANIZATION CHECK
        # -------------------------------------------------------------

        if organization_unit_is_within_scope(
            organization_unit=organization_unit,
            scope=scope,
        ):
            return True

    return False


# =============================================================================
# PERMISSION SERVICES
# =============================================================================


def get_permission(
    permission_code,
):
    """
    Get an active JKOMS Permission by code.

    Returns None instead of raising if the permission does not exist.
    """

    return (
        Permission.objects
        .filter(
            code=permission_code,
            is_active=True,
        )
        .select_related(
            "module",
        )
        .first()
    )


def role_has_permission(
    role,
    permission,
):
    """
    Resolve whether a Role grants a specific Permission.

    DENY takes precedence if duplicate/conflicting configuration
    somehow exists.
    """

    permission_code = (
        permission.code
        if isinstance(permission, Permission)
        else permission
    )

    permissions = role.role_permissions.filter(
        permission__code=permission_code,
        permission__is_active=True,
    )

    if permissions.filter(
        effect="DENY",
    ).exists():
        return False

    return permissions.filter(
        effect="ALLOW",
    ).exists()


def get_applicable_role_assignments(
    user,
    organization_unit=None,
    module=None,
    reference_date=None,
):
    """
    Return effective RoleAssignments that are valid for the requested
    Organization Unit and Module context.
    """

    assignments = get_effective_role_assignments(
        user=user,
        reference_date=reference_date,
    )

    return [
        assignment
        for assignment in assignments
        if assignment_applies_to_scope(
            role_assignment=assignment,
            organization_unit=organization_unit,
            module=module,
        )
    ]


def user_has_jkoms_permission(
    user,
    permission_code,
    organization_unit=None,
    reference_date=None,
):
    """
    Main JKOMS business authorization function.

    This should become the standard permission check used across
    Quality, Production, Technology, Engineering, Commercial, HR,
    Safety and future modules.

    Example:

        allowed = user_has_jkoms_permission(
            request.user,
            "quality.capa.approve",
            organization_unit=capa.organization_unit,
        )

    Resolution:

        User
          ↓
        Direct RoleAssignment
            OR
        Current Position(s)
          ↓
        Position RoleAssignment
          ↓
        Role
          ↓
        RolePermission
          ↓
        Permission
          +
        RoleAssignmentScope
    """

    # -----------------------------------------------------------------
    # AUTHENTICATION
    # -----------------------------------------------------------------

    if not user:
        return False

    if not getattr(user, "is_authenticated", False):
        return False

    if not user.is_active:
        return False

    # -----------------------------------------------------------------
    # DJANGO SUPERUSER
    # -----------------------------------------------------------------

    # Technical superuser bypass.
    # Do not use is_staff as business authority.
    if user.is_superuser:
        return True

    # -----------------------------------------------------------------
    # PERMISSION
    # -----------------------------------------------------------------

    permission = get_permission(
        permission_code=permission_code,
    )

    if not permission:
        return False

    # Permission's module becomes the scope module.
    permission_module = permission.module

    # -----------------------------------------------------------------
    # EFFECTIVE ASSIGNMENTS
    # -----------------------------------------------------------------

    assignments = get_applicable_role_assignments(
        user=user,
        organization_unit=organization_unit,
        module=permission_module,
        reference_date=reference_date,
    )

    # -----------------------------------------------------------------
    # DENY PRECEDENCE
    # -----------------------------------------------------------------

    for assignment in assignments:

        denied = assignment.role.role_permissions.filter(
            permission=permission,
            effect="DENY",
        ).exists()

        if denied:
            return False

    # -----------------------------------------------------------------
    # ALLOW
    # -----------------------------------------------------------------

    for assignment in assignments:

        allowed = assignment.role.role_permissions.filter(
            permission=permission,
            effect="ALLOW",
        ).exists()

        if allowed:
            return True

    return False


# =============================================================================
# USER AUTHORIZATION SUMMARY
# =============================================================================


def get_user_authorization_summary(
    user,
    reference_date=None,
):
    """
    Return a convenient authorization summary for screens such as
    user_detail.html.

    This function does not make authorization decisions. It provides
    display information.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return {
            "positions": [],
            "direct_role_assignments": [],
            "position_role_assignments": [],
            "roles": [],
        }

    positions = list(
        get_user_position_assignments(
            user=user,
            reference_date=reference_date,
        )
    )

    direct_role_assignments = list(
        get_direct_role_assignments(
            user=user,
            reference_date=reference_date,
        )
    )

    position_role_assignments = list(
        get_position_role_assignments(
            user=user,
            reference_date=reference_date,
        )
    )

    roles = list(
        get_effective_roles(
            user=user,
            reference_date=reference_date,
        )
    )

    return {
        "positions": positions,
        "direct_role_assignments": direct_role_assignments,
        "position_role_assignments": position_role_assignments,
        "roles": roles,
    }