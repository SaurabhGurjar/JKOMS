# from functools import wraps

# from django.shortcuts import redirect, render


# def staff_required(view_function):
#     @wraps(view_function)
#     def wrapper(request, *args, **kwargs):

#         if not request.user.is_authenticated:
#             return redirect("login")

#         if not request.user.is_active or not request.user.is_staff:
#             return render(
#                 request,
#                 "403.html",
#                 status=403,
#             )

#         return view_function(request, *args, **kwargs)

#     return wrapper

from functools import wraps

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from django.contrib.auth import get_user_model


User = get_user_model()


def can_manage_user(view_func):
    """
    Controls which users a staff member can manage.

    Rules:
    - Superusers can manage all users.
    - Normal staff users can manage normal users only.
    - Normal staff users cannot manage:
        - other staff users
        - superusers
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        user_id = kwargs.get("user_id")

        if user_id is None:
            messages.error(
                request,
                "Invalid user reference.",
            )

            return redirect(
                "usermanagement:user_list"
            )

        target_user = get_object_or_404(
            User,
            id=user_id,
        )

        # Superusers can manage all users
        if request.user.is_superuser:
            return view_func(
                request,
                *args,
                **kwargs,
            )

        # Normal staff cannot manage staff or superusers
        if target_user.is_staff:
            messages.error(
                request,
                "You are not authorized to manage this user account.",
            )

            return redirect(
                "usermanagement:user_list"
            )

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper


def staff_required(view_func):
    """
    Only active staff users can access the view.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not (
            request.user.is_authenticated
            and request.user.is_active
            and request.user.is_staff
        ):
            messages.error(
                request,
                "You are not authorized to access this page. Please contact the system administrator if you believe you should have access to this module.",
            )

            return redirect("login")

        return view_func(request, *args, **kwargs)

    return wrapper


# def can_manage_user(view_func):
#     @wraps(view_func)
#     def wrapper(request, *args, **kwargs):
#         user_id = kwargs.get("user_id")

#         if user_id is None:
#             messages.error(
#                 request,
#                 "Invalid user reference.",
#             )

#             return redirect(
#                 "usermanagement:user_list"
#             )

#         target_user = get_object_or_404(
#             User,
#             id=user_id,
#         )

#         if (
#             target_user.is_superuser
#             and not request.user.is_superuser
#         ):
#             messages.error(
#                 request,
#                 "You are not authorized to modify a superuser account.",
#             )

#             return redirect(
#                 "usermanagement:user_list"
#             )

#         return view_func(
#             request,
#             *args,
#             **kwargs
#         )

#     return wrapper

