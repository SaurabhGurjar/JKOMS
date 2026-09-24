from django.urls import path

from . import views

app_name = "usermanagement"

urlpatterns = [
    path("", views.user_list, name="user_list"),
    path("add/", views.user_create, name="user_create"),
    path("<int:user_id>/edit/", views.user_edit, name="user_edit"),
    path(
        "<int:user_id>/password/",
        views.user_password_reset,
        name="user_password_reset",
    ),
    path(
        "<int:user_id>/status/",
        views.user_status_toggle,
        name="user_status_toggle",
    ),
]