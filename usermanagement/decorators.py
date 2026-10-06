# usermanagement/decorators.py

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .services import user_has_jkoms_permission


# =============================================================================
# ACTIVE STAFF ACCESS
# =============================================================================


def staff_required(view_func):
    """
    Transitional administrative access decorator.

    Allows access only when the User is:

    - authenticated
    - active
    - staff

    This is retained for the existing JKOMS User Management screens.

    Important:
    is_staff should NOT be used as business authorization for
    CAPA, NCMR, deviation, Production, or other JKOMS workflows.
    """

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        user = request.user

        if (
            user.is_authenticated
            and user.is_active
            and user.is_staff
        ):
            return view_func(
                request,
                *args,
                **kwargs,
            )

        messages.error(
            request,
            "You do not have permission to access this page.",
        )

        return redirect("home")

    return wrapper


# =============================================================================
# MANAGE USER PROTECTION
# =============================================================================


def can_manage_user(view_func):
    """
    Additional safety layer for operations against another User.

    Intended for views such as:

        user_edit
        user_password_reset
        user_status_toggle

    The decorator expects the view URL to provide:

        user_id

    The main permission/access check remains staff_required or
    jkoms_permission_required.

    Object-specific restrictions are enforced in the actual views.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        user_id = kwargs.get("user_id")

        if not user_id:

            messages.error(
                request,
                "Invalid user request.",
            )

            return redirect(
                "usermanagement:user_list"
            )

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper


# =============================================================================
# JKOMS PERMISSION REQUIRED
# =============================================================================


def jkoms_permission_required(
    permission_code,
    organization_unit_getter=None,
):
    """
    JKOMS business permission decorator.

    Authorization is resolved using:

        User
          ↓
        Direct RoleAssignment
          OR
        Employee
          ↓
        Current Position
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


    Example
    -------

        @jkoms_permission_required(
            "usermanagement.user.view"
        )
        def user_list(request):
            ...


    Organization-scoped example
    ---------------------------

        def get_capa_org_unit(request, capa_id, *args, **kwargs):

            capa = get_object_or_404(
                CAPA,
                pk=capa_id,
            )

            return capa.organization_unit


        @jkoms_permission_required(
            "quality.capa.approve",
            organization_unit_getter=get_capa_org_unit,
        )
        def approve_capa(request, capa_id):
            ...


    organization_unit_getter
    ------------------------

    Optional callable.

    Expected signature:

        organization_unit_getter(
            request,
            *args,
            **kwargs
        )

    It must return an OrganizationUnit instance or None.
    """

    def decorator(view_func):

        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):

            user = request.user

            # -------------------------------------------------------------
            # USER STATUS
            # -------------------------------------------------------------

            if not user.is_active:

                messages.error(
                    request,
                    "Your JKOMS account is inactive.",
                )

                return redirect("login")

            # -------------------------------------------------------------
            # ORGANIZATION CONTEXT
            # -------------------------------------------------------------

            organization_unit = None

            if organization_unit_getter:

                organization_unit = (
                    organization_unit_getter(
                        request,
                        *args,
                        **kwargs,
                    )
                )

            # -------------------------------------------------------------
            # JKOMS PERMISSION CHECK
            # -------------------------------------------------------------

            has_permission = (
                user_has_jkoms_permission(
                    user=user,
                    permission_code=permission_code,
                    organization_unit=organization_unit,
                )
            )

            if has_permission:

                return view_func(
                    request,
                    *args,
                    **kwargs,
                )

            # -------------------------------------------------------------
            # ACCESS DENIED
            # -------------------------------------------------------------

            messages.error(
                request,
                (
                    "You do not have the required "
                    "JKOMS permission to perform this action."
                ),
            )

            return redirect("home")

        return wrapper

    return decorator


# =============================================================================
# JKOMS PERMISSION OR STAFF
# =============================================================================


def jkoms_permission_or_staff_required(
    permission_code,
    organization_unit_getter=None,
):
    """
    Transitional JKOMS decorator.

    Allows access if the User is:

        1. Django staff

    OR

        2. Holds the required JKOMS permission.


    This is useful while migrating the existing User Management
    screens from is_staff-based authorization to JKOMS RBAC.

    Long term, prefer:

        @jkoms_permission_required(...)
    """

    def decorator(view_func):

        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):

            user = request.user

            if not user.is_active:

                messages.error(
                    request,
                    "Your JKOMS account is inactive.",
                )

                return redirect("login")

            # -------------------------------------------------------------
            # DJANGO STAFF TRANSITION BYPASS
            # -------------------------------------------------------------

            if user.is_staff:

                return view_func(
                    request,
                    *args,
                    **kwargs,
                )

            # -------------------------------------------------------------
            # ORGANIZATION CONTEXT
            # -------------------------------------------------------------

            organization_unit = None

            if organization_unit_getter:

                organization_unit = (
                    organization_unit_getter(
                        request,
                        *args,
                        **kwargs,
                    )
                )

            # -------------------------------------------------------------
            # JKOMS RBAC
            # -------------------------------------------------------------

            if user_has_jkoms_permission(
                user=user,
                permission_code=permission_code,
                organization_unit=organization_unit,
            ):

                return view_func(
                    request,
                    *args,
                    **kwargs,
                )

            messages.error(
                request,
                (
                    "You do not have permission "
                    "to access this function."
                ),
            )

            return redirect("home")

        return wrapper

    return decorator