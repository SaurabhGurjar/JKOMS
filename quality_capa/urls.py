# quality_capa/urls.py
from django.urls import path

from . import views

app_name = "quality_capa"

urlpatterns = [
    path("", views.capa_list, name="list"),
    path("create/", views.capa_create, name="create"),
    path("<int:pk>/", views.capa_detail, name="detail"),
    path("<int:pk>/edit/", views.capa_edit, name="edit"),
    path("<int:pk>/transition/<slug:operation>/", views.capa_transition, name="transition"),
    path("<int:pk>/root-causes/add/", views.root_cause_create, name="root_cause_add"),
    path("<int:pk>/actions/assign/", views.action_assign, name="action_assign"),
    path("actions/<int:action_id>/progress/", views.action_progress, name="action_progress"),
    path("actions/<int:action_id>/complete/", views.action_complete, name="action_complete"),
    path("actions/<int:action_id>/verify/", views.action_verify, name="action_verify"),
    path("<int:pk>/verifications/add/", views.verification_create, name="verification_add"),
    path("<int:pk>/attachments/add/", views.attachment_create, name="attachment_add"),
    path("attachments/<int:attachment_id>/download/", views.attachment_download, name="attachment_download"),
]
