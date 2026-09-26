from django.shortcuts import render

def dashboard(request):
    return render(request, "quality/dashboard.html")
    