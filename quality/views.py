from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    context = {
        "active_page": "dashboard",
    }

    return render(
        request,
        "quality/dashboard.html",
        context,
    )