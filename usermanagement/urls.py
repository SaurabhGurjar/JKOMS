# usermanagement/urls.py

from django.urls import path

from . import views


app_name = "usermanagement"


urlpatterns = [

    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================

    # User list
    path(
        "",
        views.user_list,
        name="user_list",
    ),

    # Optional explicit users URL
    path(
        "users/",
        views.user_list,
        name="users",
    ),

    # Create User
    path(
        "users/add/",
        views.user_create,
        name="user_create",
    ),

    # User Detail
    path(
        "users/<int:user_id>/",
        views.user_detail,
        name="user_detail",
    ),

    # Edit User
    path(
        "users/<int:user_id>/edit/",
        views.user_edit,
        name="user_edit",
    ),

    # Reset User Password
    path(
        "users/<int:user_id>/password/",
        views.user_password_reset,
        name="user_password_reset",
    ),

    # Activate / Deactivate User
    path(
        "users/<int:user_id>/status/",
        views.user_status_toggle,
        name="user_status_toggle",
    ),


    # =========================================================================
    # ROLE ASSIGNMENTS
    # =========================================================================

    # Role Assignment List
    path(
        "role-assignments/",
        views.role_assignment_list,
        name="role_assignment_list",
    ),

    # Create Role Assignment
    path(
        "role-assignments/add/",
        views.role_assignment_create,
        name="role_assignment_create",
    ),

    # Edit Role Assignment
    path(
        "role-assignments/<int:assignment_id>/edit/",
        views.role_assignment_edit,
        name="role_assignment_edit",
    ),

    # Activate / Deactivate Role Assignment
    path(
        "role-assignments/<int:assignment_id>/status/",
        views.role_assignment_status_toggle,
        name="role_assignment_status_toggle",
    ),

    # Delete Role Assignment
    path(
        "role-assignments/<int:assignment_id>/delete/",
        views.role_assignment_delete,
        name="role_assignment_delete",
    ),
    
     # =============================================================================
# ORGANIZATION MANAGEMENT
# =============================================================================

# Organization Dashboard
path(
    "organization/",
    views.organization_dashboard,
    name="organization_dashboard",
),


# =============================================================================
# ORGANIZATION UNIT TYPES
# =============================================================================

path(
    "organization/unit-types/",
    views.organization_unit_type_list,
    name="organization_unit_type_list",
),

path(
    "organization/unit-types/add/",
    views.organization_unit_type_create,
    name="organization_unit_type_create",
),

path(
    "organization/unit-types/<int:type_id>/edit/",
    views.organization_unit_type_edit,
    name="organization_unit_type_edit",
),

path(
    "organization/unit-types/<int:type_id>/status/",
    views.organization_unit_type_status_toggle,
    name="organization_unit_type_status_toggle",
),


# =============================================================================
# ORGANIZATION UNITS
# =============================================================================

path(
    "organization/units/",
    views.organization_unit_list,
    name="organization_unit_list",
),

path(
    "organization/units/add/",
    views.organization_unit_create,
    name="organization_unit_create",
),

path(
    "organization/units/<int:unit_id>/edit/",
    views.organization_unit_edit,
    name="organization_unit_edit",
),

path(
    "organization/units/<int:unit_id>/status/",
    views.organization_unit_status_toggle,
    name="organization_unit_status_toggle",
),


# =============================================================================
# DESIGNATIONS
# =============================================================================

path(
    "organization/designations/",
    views.designation_list,
    name="designation_list",
),

path(
    "organization/designations/add/",
    views.designation_create,
    name="designation_create",
),

path(
    "organization/designations/<int:designation_id>/edit/",
    views.designation_edit,
    name="designation_edit",
),

path(
    "organization/designations/<int:designation_id>/status/",
    views.designation_status_toggle,
    name="designation_status_toggle",
),


# =============================================================================
# POSITIONS
# =============================================================================

path(
    "organization/positions/",
    views.position_list,
    name="position_list",
),

path(
    "organization/positions/add/",
    views.position_create,
    name="position_create",
),

path(
    "organization/positions/<int:position_id>/edit/",
    views.position_edit,
    name="position_edit",
),

path(
    "organization/positions/<int:position_id>/status/",
    views.position_status_toggle,
    name="position_status_toggle",
),


# =============================================================================
# POSITION REPORTING
# =============================================================================

path(
    "organization/reporting/",
    views.position_reporting_list,
    name="position_reporting_list",
),

path(
    "organization/reporting/add/",
    views.position_reporting_create,
    name="position_reporting_create",
),

path(
    "organization/reporting/<int:reporting_id>/edit/",
    views.position_reporting_edit,
    name="position_reporting_edit",
),

path(
    "organization/reporting/<int:reporting_id>/status/",
    views.position_reporting_status_toggle,
    name="position_reporting_status_toggle",
),


# =============================================================================
# EMPLOYEES
# =============================================================================

path(
    "organization/employees/",
    views.employee_list,
    name="employee_list",
),

path(
    "organization/employees/add/",
    views.employee_create,
    name="employee_create",
),

path(
    "organization/employees/<int:employee_id>/",
    views.employee_detail,
    name="employee_detail",
),

path(
    "organization/employees/<int:employee_id>/edit/",
    views.employee_edit,
    name="employee_edit",
),

path(
    "organization/employees/<int:employee_id>/status/",
    views.employee_status_toggle,
    name="employee_status_toggle",
),


# =============================================================================
# EMPLOYEE POSITION ASSIGNMENTS
# =============================================================================

path(
    "organization/position-assignments/",
    views.position_assignment_list,
    name="position_assignment_list",
),

path(
    "organization/position-assignments/add/",
    views.position_assignment_create,
    name="position_assignment_create",
),

path(
    "organization/position-assignments/<int:assignment_id>/edit/",
    views.position_assignment_edit,
    name="position_assignment_edit",
),

path(
    "organization/position-assignments/<int:assignment_id>/status/",
    views.position_assignment_status_toggle,
    name="position_assignment_status_toggle",
),
]
