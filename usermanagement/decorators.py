from functools import wraps

from django.shortcuts import redirect, render


def staff_required(view_function):
    @wraps(view_function)
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect("login")

        if not request.user.is_active or not request.user.is_staff:
            return render(
                request,
                "403.html",
                status=403,
            )

        return view_function(request, *args, **kwargs)

    return wrapper