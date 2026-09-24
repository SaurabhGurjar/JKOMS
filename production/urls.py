from django.urls import path

from . import views


app_name = "production"


urlpatterns = [
    # Production Dashboard
    path(
        "",
        views.production_dashboard,
        name="dashboard",
    ),

    # Card-based Department Selection
    path(
        "entry/<str:entry_type>/",
        views.department_selection,
        name="department_selection",
    ),

    # Department-Specific Entry Form
    path(
        "entry/<str:entry_type>/<str:department>/",
        views.production_entry_form,
        name="entry_form",
    ),
]