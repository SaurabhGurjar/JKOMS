# quality_capa/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from usermanagement.models import Employee, OrganizationUnit, Position

from .models import (
    CAPA,
    CAPAAction,
    CAPAAttachment,
    CAPACategory,
    CAPADocumentUpdate,
    CAPAFollowUpAudit,
    CAPAManagementSystem,
    CAPARootCause,
    CAPASource,
    CAPAVerification,
)


DATE_INPUT = forms.DateInput(attrs={"type": "date"})
DATETIME_INPUT = forms.DateTimeInput(attrs={"type": "datetime-local"})


class BootstrapModelFormMixin:
    """Apply predictable CSS classes without requiring django-crispy-forms."""

    def _apply_widget_classes(self):
        for field in self.fields.values():
            widget = field.widget
            current = widget.attrs.get("class", "")
            if isinstance(widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            else:
                css_class = "form-control"
            widget.attrs["class"] = f"{current} {css_class}".strip()


class CAPABaseForm(BootstrapModelFormMixin, forms.ModelForm):
    management_systems = forms.ModelMultipleChoiceField(
        queryset=CAPAManagementSystem.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = CAPA
        fields = (
            "title",
            "capa_type",
            "source",
            "category",
            "management_systems",
            "organization_unit",
            "originating_organization_unit",
            "location_text",
            "nonconformity_number",
            "nonconformance_category",
            "is_repeated_nonconformance",
            "owner_position",
            "owner_employee",
            "reported_by_employee",
            "auditor_name",
            "auditor_signature",
            "auditee_name",
            "auditee_signature",
            "audit_date",
            "section_area_audited",
            "clause_reference",
            "document_reference",
            "occurrence_date",
            "detection_date",
            "target_completion_date",
            "problem_description",
            "correction_containment_action",
            "immediate_correction",
            "scope",
            "impact_description",
            "regulatory_impact",
            "customer_impact",
            "safety_impact",
            "production_impact",
            "financial_impact",
            "priority",
            "severity_score",
            "occurrence_score",
            "detection_score",
            "source_reference",
        )
        widgets = {
            "audit_date": DATE_INPUT,
            "occurrence_date": DATE_INPUT,
            "detection_date": DATE_INPUT,
            "target_completion_date": DATE_INPUT,
            "problem_description": forms.Textarea(attrs={"rows": 5}),
            "correction_containment_action": forms.Textarea(attrs={"rows": 4}),
            "immediate_correction": forms.Textarea(attrs={"rows": 4}),
            "scope": forms.Textarea(attrs={"rows": 3}),
            "impact_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = CAPASource.objects.filter(is_active=True)
        self.fields["category"].queryset = CAPACategory.objects.filter(is_active=True)
        self.fields["management_systems"].queryset = CAPAManagementSystem.objects.filter(
            is_active=True
        )
        self.fields["organization_unit"].queryset = OrganizationUnit.objects.filter(
            is_active=True
        ).select_related("unit_type")
        self.fields["originating_organization_unit"].queryset = self.fields[
            "organization_unit"
        ].queryset
        self.fields["owner_position"].queryset = Position.objects.filter(
            is_active=True
        ).select_related("organization_unit", "designation")
        self.fields["owner_employee"].queryset = Employee.objects.filter(is_active=True)
        self.fields["reported_by_employee"].queryset = Employee.objects.filter(is_active=True)
        self._apply_widget_classes()

    def clean(self):
        cleaned = super().clean()
        org = cleaned.get("organization_unit")
        position = cleaned.get("owner_position")
        if org and position and position.organization_unit_id != org.pk:
            self.add_error(
                "owner_position",
                "Owner position must belong to the responsible organization unit.",
            )
        return cleaned


class CAPACreateForm(CAPABaseForm):
    """Fixed-field CAPA creation form. Dynamic form fields are intentionally absent."""


class CAPADraftUpdateForm(CAPABaseForm):
    class Meta(CAPABaseForm.Meta):
        fields = tuple(
            field for field in CAPABaseForm.Meta.fields if field != "organization_unit"
        )


class CAPARootCauseForm(BootstrapModelFormMixin, forms.ModelForm):
    class Meta:
        model = CAPARootCause
        fields = (
            "analysis_method",
            "cause_type",
            "why_1",
            "why_2",
            "why_3",
            "why_4",
            "why_5",
            "cause_statement",
            "analysis_details",
            "evidence",
            "is_confirmed",
        )
        widgets = {
            "why_1": forms.Textarea(attrs={"rows": 2}),
            "why_2": forms.Textarea(attrs={"rows": 2}),
            "why_3": forms.Textarea(attrs={"rows": 2}),
            "why_4": forms.Textarea(attrs={"rows": 2}),
            "why_5": forms.Textarea(attrs={"rows": 2}),
            "cause_statement": forms.Textarea(attrs={"rows": 3}),
            "analysis_details": forms.Textarea(attrs={"rows": 4}),
            "evidence": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_widget_classes()


class CAPAActionAssignForm(BootstrapModelFormMixin, forms.ModelForm):
    class Meta:
        model = CAPAAction
        fields = (
            "root_cause",
            "action_type",
            "title",
            "description",
            "responsible_position",
            "responsible_employee",
            "target_date",
            "is_mandatory",
            "requires_verification",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "target_date": DATE_INPUT,
        }

    def __init__(self, *args, capa=None, **kwargs):
        self.capa = capa
        super().__init__(*args, **kwargs)
        self.fields["root_cause"].queryset = (
            capa.root_causes.order_by("sequence")
            if capa
            else CAPARootCause.objects.none()
        )
        positions = Position.objects.filter(is_active=True)
        if capa:
            positions = positions.filter(organization_unit=capa.organization_unit)
        self.fields["responsible_position"].queryset = positions.select_related(
            "organization_unit", "designation"
        )
        self.fields["responsible_employee"].queryset = Employee.objects.filter(
            is_active=True
        )
        self._apply_widget_classes()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("responsible_position") and not cleaned.get(
            "responsible_employee"
        ):
            raise ValidationError(
                "Select a responsible employee or responsible position."
            )
        return cleaned


class CAPAActionProgressForm(BootstrapModelFormMixin, forms.ModelForm):
    class Meta:
        model = CAPAAction
        fields = (
            "status",
            "completion_percentage",
            "revised_target_date",
            "revision_reason",
            "completion_details",
        )
        widgets = {
            "revised_target_date": DATE_INPUT,
            "revision_reason": forms.Textarea(attrs={"rows": 3}),
            "completion_details": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = {
            CAPAAction.Status.ASSIGNED,
            CAPAAction.Status.IN_PROGRESS,
            CAPAAction.Status.ON_HOLD,
        }
        self.fields["status"].choices = [
            choice for choice in CAPAAction.Status.choices if choice[0] in allowed
        ]
        self._apply_widget_classes()


class CAPAActionCompleteForm(BootstrapModelFormMixin, forms.Form):
    completion_details = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}))
    actual_date = forms.DateField(required=False, widget=DATE_INPUT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_widget_classes()


class CAPAActionVerifyForm(BootstrapModelFormMixin, forms.Form):
    comments = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_widget_classes()


class CAPAVerificationForm(BootstrapModelFormMixin, forms.ModelForm):
    class Meta:
        model = CAPAVerification
        fields = (
            "action",
            "review_type",
            "review_date",
            "reviewed_as_position",
            "verification_method",
            "observations",
            "result",
            "effectiveness_score",
            "follow_up_required",
            "follow_up_date",
            "follow_up_comments",
            "recommendation",
            "is_final",
        )
        widgets = {
            "review_date": DATE_INPUT,
            "follow_up_date": DATE_INPUT,
            "verification_method": forms.Textarea(attrs={"rows": 3}),
            "observations": forms.Textarea(attrs={"rows": 4}),
            "follow_up_comments": forms.Textarea(attrs={"rows": 3}),
            "recommendation": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, capa=None, user=None, **kwargs):
        self.capa = capa
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["action"].queryset = (
            capa.actions.order_by("sequence") if capa else CAPAAction.objects.none()
        )
        self.fields["reviewed_as_position"].queryset = (
            get_user_positions(user) if user else Position.objects.none()
        )
        self.fields["review_date"].initial = timezone.localdate()
        self._apply_widget_classes()


class CAPAAttachmentForm(BootstrapModelFormMixin, forms.ModelForm):
    class Meta:
        model = CAPAAttachment
        fields = (
            "action",
            "root_cause",
            "attachment_type",
            "title",
            "description",
            "file",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, capa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["action"].queryset = (
            capa.actions.order_by("sequence") if capa else CAPAAction.objects.none()
        )
        self.fields["root_cause"].queryset = (
            capa.root_causes.order_by("sequence")
            if capa
            else CAPARootCause.objects.none()
        )
        self._apply_widget_classes()


class CAPAFollowUpAuditForm(BootstrapModelFormMixin, forms.ModelForm):
    class Meta:
        model = CAPAFollowUpAudit
        fields = (
            "due_date",
            "verified_on",
            "verified_as_position",
            "result",
            "observations",
        )
        widgets = {
            "due_date": DATE_INPUT,
            "verified_on": DATE_INPUT,
            "observations": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["verified_as_position"].queryset = (
            get_user_positions(user) if user else Position.objects.none()
        )
        self._apply_widget_classes()


class CAPADocumentUpdateForm(BootstrapModelFormMixin, forms.ModelForm):
    class Meta:
        model = CAPADocumentUpdate
        fields = (
            "document_type",
            "update_required",
            "document_reference",
            "description",
            "updated_on",
            "attachment",
        )
        widgets = {
            "updated_on": DATE_INPUT,
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_widget_classes()


class CAPATransitionForm(BootstrapModelFormMixin, forms.Form):
    comments = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, require_comments=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comments"].required = require_comments
        self._apply_widget_classes()


# Local import avoids a circular dependency during app loading.
from usermanagement.services import get_user_positions  # noqa: E402
