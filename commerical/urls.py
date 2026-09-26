from django.urls import path
from . import views

app_name = "commerical"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]