# usermanagement/forms.py

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import inlineformset_factory

from .models import (
    Employee,
    Module,
    OrganizationUnit,
    Position,
    Role,
    RoleAssignment,
    RoleAssignmentScope,
)


User = get_user_model()


# =============================================================================
# COMMON FORM STYLING
# =============================================================================


class BootstrapFormMixin:
    """
    Applies Bootstrap 5 styling consistently to JKOMS forms.
    """

    def apply_bootstrap_classes(self):
        for field_name, field in self.fields.items():
            widget = field.widget

            # Checkbox
            if isinstance(widget, forms.CheckboxInput):
                existing_class = widget.attrs.get("class", "")
                widget.attrs["class"] = (
                    f"{existing_class} form-check-input"
                ).strip()
                continue

            # Radio
            if isinstance(widget, forms.RadioSelect):
                continue

            # Select / SelectMultiple
            if isinstance(
                widget,
                (forms.Select, forms.SelectMultiple),
            ):
                existing_class = widget.attrs.get("class", "")
                widget.attrs["class"] = (
                    f"{existing_class} form-select"
                ).strip()

            else:
                existing_class = widget.attrs.get("class", "")
                widget.attrs["class"] = (
                    f"{existing_class} form-control"
                ).strip()

            # Placeholder only for suitable widgets
            if not isinstance(
                widget,
                (
                    forms.Select,
                    forms.SelectMultiple,
                    forms.DateInput,
                    forms.DateTimeInput,
                ),
            ):
                widget.attrs.setdefault(
                    "placeholder",
                    field.label,
                )


# =============================================================================
# CREATE USER FORM
# =============================================================================


class CreateUserForm(
    BootstrapFormMixin,
    UserCreationForm,
):
    """
    Creates a JKOMS authentication account.

    Role assignment is not handled in this form.

    User responsibilities:
        - Account information
        - Employee linkage

    Authorization responsibilities:
        - RoleAssignment
        - RoleAssignmentScope
    """

    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        required=False,
        empty_label="Select employee",
        help_text=(
            "Link this login to an existing employee. "
            "Leave blank only for authorized service or "
            "non-employee accounts."
        ),
    )

    first_name = forms.CharField(
        max_length=150,
        required=False,
    )

    last_name = forms.CharField(
        max_length=150,
        required=False,
    )

    email = forms.EmailField(
        required=False,
    )

    is_active = forms.BooleanField(
        required=False,
        initial=True,
        help_text=(
            "Inactive users cannot authenticate to JKOMS."
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User

        fields = (
            "username",
            "employee",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only employees not already connected to another User
        # should normally be available for selection.
        assigned_employee_ids = (
            User.objects
            .filter(employee__isnull=False)
            .values_list("employee_id", flat=True)
        )

        self.fields["employee"].queryset = (
            Employee.objects
            .filter(is_active=True)
            .exclude(id__in=assigned_employee_ids)
            .order_by("employee_code")
        )

        self.fields["username"].help_text = (
            "Enter the JKOMS login username."
        )

        self.fields["password1"].help_text = (
            "Enter a secure password that satisfies "
            "the configured JKOMS password policy."
        )

        self.fields["password2"].help_text = (
            "Enter the same password again for verification."
        )

        self.apply_bootstrap_classes()

    def clean_employee(self):
        """
        Prevent an Employee from being linked to more than
        one JKOMS User account.
        """

        employee = self.cleaned_data.get("employee")

        if not employee:
            return employee

        if User.objects.filter(employee=employee).exists():
            raise ValidationError(
                "This employee is already linked "
                "to a JKOMS user account."
            )

        return employee

    def clean_email(self):
        """
        Normalize email address.
        """

        email = self.cleaned_data.get("email", "")

        return email.strip().lower()

    def save(self, commit=True):
        user = super().save(commit=False)

        user.employee = self.cleaned_data.get("employee")

        user.first_name = self.cleaned_data.get(
            "first_name",
            "",
        )

        user.last_name = self.cleaned_data.get(
            "last_name",
            "",
        )

        user.email = self.cleaned_data.get(
            "email",
            "",
        )

        user.is_active = self.cleaned_data.get(
            "is_active",
            True,
        )

        if commit:
            user.save()

        return user


# =============================================================================
# EDIT USER FORM
# =============================================================================


class EditUserForm(
    BootstrapFormMixin,
    forms.ModelForm,
):
    """
    Edits the JKOMS User account.

    Passwords and authorization are managed separately.
    """

    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        required=False,
        empty_label="Select employee",
        help_text=(
            "Employee linked to this JKOMS account."
        ),
    )

    class Meta:
        model = User

        fields = (
            "username",
            "employee",
            "first_name",
            "last_name",
            "email",
            "is_active",
        )

        widgets = {
            "username": forms.TextInput(),
            "first_name": forms.TextInput(),
            "last_name": forms.TextInput(),
            "email": forms.EmailInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Find employees already linked to OTHER user accounts.
        used_employee_ids = (
            User.objects
            .filter(employee__isnull=False)
        )

        if self.instance and self.instance.pk:
            used_employee_ids = used_employee_ids.exclude(
                pk=self.instance.pk,
            )

        used_employee_ids = used_employee_ids.values_list(
            "employee_id",
            flat=True,
        )

        employee_queryset = (
            Employee.objects
            .exclude(id__in=used_employee_ids)
            .filter(is_active=True)
        )

        # Keep the currently linked Employee selectable even
        # if that Employee has subsequently become inactive.
        if (
            self.instance
            and self.instance.pk
            and self.instance.employee_id
        ):
            employee_queryset = (
                Employee.objects
                .exclude(id__in=used_employee_ids)
                .filter(
                    Q(is_active=True)
                    | Q(pk=self.instance.employee_id)
                )
            )

        self.fields["employee"].queryset = (
            employee_queryset
            .distinct()
            .order_by("employee_code")
        )

        self.apply_bootstrap_classes()

    def clean_employee(self):
        """
        Ensure an Employee cannot be linked to multiple Users.
        """

        employee = self.cleaned_data.get("employee")

        if not employee:
            return employee

        existing = User.objects.filter(
            employee=employee,
        )

        if self.instance and self.instance.pk:
            existing = existing.exclude(
                pk=self.instance.pk,
            )

        if existing.exists():
            raise ValidationError(
                "This employee is already linked "
                "to another JKOMS user account."
            )

        return employee

    def clean_email(self):
        email = self.cleaned_data.get(
            "email",
            "",
        )

        return email.strip().lower()


# =============================================================================
# RESET USER PASSWORD FORM
# =============================================================================


class ResetUserPasswordForm(
    BootstrapFormMixin,
    SetPasswordForm,
):
    """
    Administrator password reset form.

    Django's configured password validators are automatically used.
    """

    def __init__(self, user, *args, **kwargs):
        super().__init__(
            user,
            *args,
            **kwargs,
        )

        self.fields["new_password1"].label = (
            "New Password"
        )

        self.fields["new_password2"].label = (
            "Confirm New Password"
        )

        self.apply_bootstrap_classes()


# =============================================================================
# ROLE ASSIGNMENT FORM
# =============================================================================


class RoleAssignmentForm(
    BootstrapFormMixin,
    forms.ModelForm,
):
    """
    Assign a JKOMS Role to exactly one target:

        User
        OR
        Position

    Position assignment is preferred for organizational authority.

    Direct User assignment should be reserved for user-specific
    or technical access.
    """

    role = forms.ModelChoiceField(
        queryset=Role.objects.none(),
        empty_label="Select role",
    )

    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="Select user",
        help_text=(
            "Use for user-specific authority only. "
            "Leave blank for position-based assignment."
        ),
    )

    position = forms.ModelChoiceField(
        queryset=Position.objects.none(),
        required=False,
        empty_label="Select position",
        help_text=(
            "Preferred for organizational authority. "
            "Leave blank for direct user assignment."
        ),
    )

    valid_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )

    valid_to = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )

    class Meta:
        model = RoleAssignment

        fields = (
            "role",
            "user",
            "position",
            "valid_from",
            "valid_to",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["role"].queryset = (
            Role.objects
            .filter(is_active=True)
            .select_related(
                "role_type",
                "module",
            )
            .order_by("name")
        )

        self.fields["user"].queryset = (
            User.objects
            .filter(is_active=True)
            .select_related("employee")
            .order_by("username")
        )

        self.fields["position"].queryset = (
            Position.objects
            .filter(is_active=True)
            .select_related(
                "organization_unit",
                "designation",
            )
            .order_by(
                "organization_unit__name",
                "name",
            )
        )

        self.apply_bootstrap_classes()

    def clean(self):
        cleaned_data = super().clean()

        user = cleaned_data.get("user")
        position = cleaned_data.get("position")

        valid_from = cleaned_data.get(
            "valid_from"
        )

        valid_to = cleaned_data.get(
            "valid_to"
        )

        # ---------------------------------------------------------------------
        # Exactly ONE target must be selected
        # ---------------------------------------------------------------------

        if not user and not position:
            raise ValidationError(
                "Select either a User or a Position "
                "for this Role Assignment."
            )

        if user and position:
            raise ValidationError(
                "A Role Assignment cannot target both "
                "a User and a Position."
            )

        # ---------------------------------------------------------------------
        # Effective date validation
        # ---------------------------------------------------------------------

        if (
            valid_from
            and valid_to
            and valid_to < valid_from
        ):
            self.add_error(
                "valid_to",
                "Valid-to date cannot be before "
                "valid-from date.",
            )

        return cleaned_data


# =============================================================================
# ROLE ASSIGNMENT SCOPE FORM
# =============================================================================


class RoleAssignmentScopeForm(
    BootstrapFormMixin,
    forms.ModelForm,
):
    """
    Restricts a RoleAssignment by:

        Organization Unit
        Module

    Organization Unit blank:
        No organization restriction.

    Module blank:
        No module restriction.

    Include Descendants:
        Authority also applies to child Organization Units.
    """

    organization_unit = forms.ModelChoiceField(
        queryset=OrganizationUnit.objects.none(),
        required=False,
        empty_label="All organization units",
    )

    module = forms.ModelChoiceField(
        queryset=Module.objects.none(),
        required=False,
        empty_label="All modules",
    )

    class Meta:
        model = RoleAssignmentScope

        fields = (
            "organization_unit",
            "module",
            "include_descendants",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields[
            "organization_unit"
        ].queryset = (
            OrganizationUnit.objects
            .filter(is_active=True)
            .select_related(
                "unit_type",
                "parent",
            )
            .order_by("name")
        )

        self.fields["module"].queryset = (
            Module.objects
            .filter(is_enabled=True)
            .order_by(
                "display_order",
                "name",
            )
        )

        self.fields[
            "include_descendants"
        ].help_text = (
            "If enabled, the scope also applies "
            "to child organization units."
        )

        self.apply_bootstrap_classes()

    def clean(self):
        cleaned_data = super().clean()

        organization_unit = cleaned_data.get(
            "organization_unit"
        )

        include_descendants = cleaned_data.get(
            "include_descendants"
        )

        # Descendant inheritance has no meaning when the scope
        # isn't restricted to an Organization Unit.
        if (
            organization_unit is None
            and include_descendants
        ):
            cleaned_data[
                "include_descendants"
            ] = False

        return cleaned_data


# =============================================================================
# ROLE ASSIGNMENT SCOPE FORMSET
# =============================================================================


RoleAssignmentScopeFormSet = inlineformset_factory(
    parent_model=RoleAssignment,
    model=RoleAssignmentScope,
    form=RoleAssignmentScopeForm,
    fields=(
        "organization_unit",
        "module",
        "include_descendants",
    ),
    extra=1,
    can_delete=True,
)


# =============================================================================
# USER FILTER FORM
# =============================================================================


class UserFilterForm(
    BootstrapFormMixin,
    forms.Form,
):
    """
    Filter form for the JKOMS User List screen.
    """

    search = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "placeholder": (
                    "Username, employee code, name or email"
                ),
            }
        ),
    )

    status = forms.ChoiceField(
        required=False,
        choices=(
            ("", "All Status"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ),
    )

    role = forms.ModelChoiceField(
        queryset=Role.objects.none(),
        required=False,
        empty_label="All Roles",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["role"].queryset = (
            Role.objects
            .filter(is_active=True)
            .select_related(
                "role_type",
                "module",
            )
            .order_by("name")
        )

        self.apply_bootstrap_classes()