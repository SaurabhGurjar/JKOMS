from django.urls import path
from . import views

app_name = "quality"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("qms/",views.qms_home, name="qms")
 
]