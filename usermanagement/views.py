from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import Group
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .decorators import staff_required, can_manage_user

from .forms import (
    CreateUserForm,
    EditUserForm,
    ResetUserPasswordForm,
)

User = get_user_model()


def admin_required(user):
    """
    Only active staff users can access User Management.
    """

    return user.is_authenticated and user.is_active and user.is_staff


@staff_required
def user_list(request):
    search_query = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "").strip()
    role_filter = request.GET.get("role", "").strip()

    users = User.objects.prefetch_related("groups").order_by(
        "-date_joined"
    )

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    if status_filter == "active":
        users = users.filter(is_active=True)

    elif status_filter == "inactive":
        users = users.filter(is_active=False)

    if role_filter:
        users = users.filter(groups__id=role_filter)

    users = users.distinct()

    context = {
        "users": users,
        "groups": Group.objects.all().order_by("name"),
        "search_query": search_query,
        "status_filter": status_filter,
        "role_filter": role_filter,
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "inactive_users": User.objects.filter(is_active=False).count(),
        "staff_users": User.objects.filter(is_staff=True).count(),
    }

    return render(
        request,
        "usermanagement/user_list.html",
        context,
    )


@staff_required
def user_create(request):
    if request.method == "POST":
        form = CreateUserForm(request.POST)

        if form.is_valid():
            user = form.save()

            messages.success(
                request,
                f"User '{user.username}' was created successfully.",
            )

            return redirect("usermanagement:user_list")

    else:
        form = CreateUserForm(
            initial={
                "is_active": True,
            }
        )

    return render(
        request,
        "usermanagement/user_form.html",
        {
            "form": form,
            "page_title": "Add User",
            "page_description": (
                "Create a new JKOMS user account and assign roles."
            ),
            "submit_text": "Create User",
        },
    )


@staff_required
@can_manage_user
def user_edit(request, user_id):
    selected_user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = EditUserForm(
            request.POST,
            instance=selected_user,
        )

        if form.is_valid():
            updated_user = form.save()

            messages.success(
                request,
                f"User '{updated_user.username}' was updated.",
            )

            return redirect("usermanagement:user_list")

    else:
        form = EditUserForm(instance=selected_user)

    return render(
        request,
        "usermanagement/user_form.html",
        {
            "form": form,
            "selected_user": selected_user,
            "page_title": "Edit User",
            "page_description": (
                "Update user information, role, and access status."
            ),
            "submit_text": "Save Changes",
        },
    )


@staff_required
@can_manage_user
def user_password_reset(request, user_id):
    selected_user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = ResetUserPasswordForm(
            selected_user,
            request.POST,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                (
                    f"Password for '{selected_user.username}' "
                    "was changed successfully."
                ),
            )

            return redirect("usermanagement:user_list")

    else:
        form = ResetUserPasswordForm(selected_user)

    return render(
        request,
        "usermanagement/password_reset.html",
        {
            "form": form,
            "selected_user": selected_user,
        },
    )


@staff_required
@can_manage_user
def user_status_toggle(request, user_id):
    if request.method != "POST":
        return redirect("usermanagement:user_list")

    selected_user = get_object_or_404(User, id=user_id)

    if selected_user == request.user:
        messages.error(
            request,
            "You cannot deactivate your own account.",
        )

        return redirect("usermanagement:user_list")

    selected_user.is_active = not selected_user.is_active
    selected_user.save(update_fields=["is_active"])

    status_text = (
        "activated"
        if selected_user.is_active
        else "deactivated"
    )

    messages.success(
        request,
        f"User '{selected_user.username}' was {status_text}.",
    )

    return redirect("usermanagement:user_list")