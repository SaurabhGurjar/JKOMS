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
]