from django.urls import path

from . import views


app_name = "safety_bbs"


urlpatterns = [

    # ==============================================================
    # PUBLIC
    # ==============================================================

    path(
        "",
        views.bbs_observation_create,
        name="bbs_create",
    ),

    path(
        "submitted/",
        views.bbs_success,
        name="bbs_success",
    ),

    # ==============================================================
    # PROTECTED
    # ==============================================================

    path(
        "dashboard/",
        views.bbs_dashboard,
        name="bbs_dashboard",
    ),

    path(
        "dashboard/export/",
        views.bbs_monthly_export,
        name="bbs_monthly_export",
    ),

    path(
        "responses/",
        views.bbs_response_list,
        name="bbs_response_list",
    ),

    path(
        "responses/<int:response_id>/",
        views.bbs_response_detail,
        name="bbs_response_detail",
    ),
    
    path(
       "responses/export/",
        views.bbs_response_export,
        name="bbs_response_export",
    ),

]