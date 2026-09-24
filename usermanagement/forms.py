from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    UserChangeForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group

User = get_user_model()


class StyledFormMixin:
    """
    Adds Bootstrap classes to form fields.
    """

    def apply_bootstrap_classes(self):
        for field in self.fields.values():
            existing_classes = field.widget.attrs.get("class", "")

            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(field.widget, forms.SelectMultiple):
                css_class = "form-select"
            elif isinstance(field.widget, forms.Select):
                css_class = "form-select"
            else:
                css_class = "form-control"

            field.widget.attrs["class"] = (
                f"{existing_classes} {css_class}"
            ).strip()


class CreateUserForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=True)

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "size": "5",
            }
        ),
        help_text="Select one or more roles.",
    )

    class Meta:
        model = User

        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "groups",
            "is_staff",
            "is_active",
            "password1",
            "password2",
        ]

        labels = {
            "is_staff": "Staff access",
            "is_active": "Active user",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()

        self.fields["username"].widget.attrs.update(
            {
                "placeholder": "Enter username",
                "autocomplete": "off",
            }
        )

        self.fields["first_name"].widget.attrs[
            "placeholder"
        ] = "Enter first name"

        self.fields["last_name"].widget.attrs[
            "placeholder"
        ] = "Enter last name"

        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "Enter email address",
                "autocomplete": "off",
            }
        )


class EditUserForm(StyledFormMixin, UserChangeForm):
    password = None

    email = forms.EmailField(required=True)

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "size": "5",
            }
        ),
        help_text="Select one or more roles.",
    )

    class Meta:
        model = User

        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "groups",
            "is_staff",
            "is_active",
        ]

        labels = {
            "is_staff": "Staff access",
            "is_active": "Active user",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()


class ResetUserPasswordForm(
    StyledFormMixin,
    AdminPasswordChangeForm,
):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.apply_bootstrap_classes()