from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import BBSObservation


# =============================================================================
# BBS OBSERVATION FORM
# =============================================================================


class BBSObservationForm(forms.ModelForm):
    """
    Public BBS Observation Form.

    Designed as a Microsoft Forms-style submission form.

    No authentication is required.

    Employee identification is currently based on:
        - Employee Name
        - Card No.
    """

    # =========================================================================
    # MULTI-SELECT CHOICES
    # =========================================================================

    BEHAVIOUR_CATEGORY_CHOICES = (
        ("PPE", "PPE"),
        ("GUARDING_LOTO", "Guarding / LOTO"),
        ("ERGONOMICS", "Position / Ergonomics"),
        ("TOOLS_EQUIPMENT", "Tools / Equipment"),
        ("HOUSEKEEPING", "Housekeeping"),
        ("PERMIT", "Permit"),
    )

    CONSEQUENCE_CHOICES = (
        (
            "POSITIVE_REINFORCEMENT",
            "Positive Reinforcement / Praised",
        ),
        (
            "ON_SPOT_COACHING",
            "On-Spot Coaching Given",
        ),
        (
            "CORRECTIVE_ACTION",
            "Corrective Action Required",
        ),
        (
            "NEAR_MISS_HAZARD",
            "Near-Miss / Hazard Reported",
        ),
    )

    ROOT_CAUSE_CHOICES = (
        ("TIME_PRESSURE", "Time Pressure"),
        ("TRAINING_GAP", "Training Gap"),
        (
            "TOOL_EQUIPMENT_ISSUE",
            "Tool / Equipment Issue",
        ),
        (
            "PROCEDURE_UNCLEAR",
            "Procedure Unclear",
        ),
        ("COMPLACENCY", "Complacency"),
        ("OTHER", "Other"),
    )

    # =========================================================================
    # EMPLOYEE DETAILS
    # =========================================================================

    employee_name = forms.CharField(
        label="Employee Name",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Enter your name",
                "autocomplete": "name",
            }
        ),
    )

    card_no = forms.CharField(
        label="Card No.",
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Enter your card number",
                "autocomplete": "off",
            }
        ),
    )

    # =========================================================================
    # OBSERVATION DETAILS
    # =========================================================================

    observation_date = forms.DateField(
        label="Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    observation_time = forms.TimeField(
        label="Time",
        widget=forms.TimeInput(
            attrs={
                "class": "form-control",
                "type": "time",
            }
        ),
    )

    shift = forms.ChoiceField(
        label="Shift",
        choices=BBSObservation.Shift.choices,
        widget=forms.RadioSelect(),
    )

    area = forms.CharField(
        label="Area",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter observation area",
            }
        ),
    )

    observer_name = forms.CharField(
        label="Observer Name",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "",
            }
        ),
    )

    # =========================================================================
    # A. ACTIVATOR
    # =========================================================================

    activator = forms.CharField(
        label=(
            "What prompted the behaviour "
            "(sign, instruction, condition, habit)?"
        ),
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": (
                    "Describe what prompted the behaviour"
                ),
            }
        ),
    )

    # =========================================================================
    # B. BEHAVIOUR
    # =========================================================================

    behaviour_type = forms.ChoiceField(
        label="Observation Type",
        choices=BBSObservation.BehaviourType.choices,
        widget=forms.RadioSelect(),
    )

    behaviour_categories = forms.MultipleChoiceField(
        label="Category",
        choices=BEHAVIOUR_CATEGORY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    behaviour_description = forms.CharField(
        label="Describe the Behaviour",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": (
                    "Describe the safe or at-risk "
                    "behaviour observed"
                ),
            }
        ),
    )

    # =========================================================================
    # C. CONSEQUENCE
    # =========================================================================

    consequences = forms.MultipleChoiceField(
        label="Consequence / Feedback",
        choices=CONSEQUENCE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    feedback = forms.CharField(
        label="Feedback Given",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": (
                    "Feedback given on the spot"
                ),
            }
        ),
    )

    # =========================================================================
    # CRITICAL BEHAVIOUR CHECKLIST
    # =========================================================================

    ppe_status = forms.ChoiceField(
        label=(
            "PPE compliance "
            "(helmet, gloves, goggles, footwear)"
        ),
        choices=BBSObservation.ChecklistStatus.choices,
        widget=forms.RadioSelect(),
    )

    guarding_loto_status = forms.ChoiceField(
        label=(
            "Machine guarding / LOTO "
            "in place & used"
        ),
        choices=BBSObservation.ChecklistStatus.choices,
        widget=forms.RadioSelect(),
    )

    ergonomics_status = forms.ChoiceField(
        label=(
            "Body position, ergonomics, "
            "pinch points avoided"
        ),
        choices=BBSObservation.ChecklistStatus.choices,
        widget=forms.RadioSelect(),
    )

    tools_equipment_status = forms.ChoiceField(
        label="Correct tool / equipment for task",
        choices=BBSObservation.ChecklistStatus.choices,
        widget=forms.RadioSelect(),
    )

    housekeeping_status = forms.ChoiceField(
        label=(
            "Housekeeping "
            "(walkways, spills, storage)"
        ),
        choices=BBSObservation.ChecklistStatus.choices,
        widget=forms.RadioSelect(),
    )

    permit_procedure_status = forms.ChoiceField(
        label="Permit-to-work / procedure followed",
        choices=BBSObservation.ChecklistStatus.choices,
        widget=forms.RadioSelect(),
    )

    # =========================================================================
    # ROOT CAUSE
    # =========================================================================

    root_causes = forms.MultipleChoiceField(
        label="If At-Risk, likely root cause",
        choices=ROOT_CAUSE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    root_cause_other = forms.CharField(
        label="Other Root Cause",
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Please specify other root cause"
                ),
            }
        ),
    )

    corrective_action = forms.CharField(
        label="Corrective / Preventive Action",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": (
                    "Describe corrective or "
                    "preventive action"
                ),
            }
        ),
    )

    # =========================================================================
    # ACKNOWLEDGEMENT
    # =========================================================================

    observer_sign = forms.CharField(
        label="Observer Sign / Name",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "",
            }
        ),
    )

    supervisor_sign = forms.CharField(
        label="Supervisor Sign / Name",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "",
            }
        ),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta:
        model = BBSObservation

        fields = (
            "employee_name",
            "card_no",
            "observation_date",
            "observation_time",
            "shift",
            "area",
            "observer_name",
            "activator",
            "behaviour_type",
            "behaviour_categories",
            "behaviour_description",
            "consequences",
            "feedback",
            "ppe_status",
            "guarding_loto_status",
            "ergonomics_status",
            "tools_equipment_status",
            "housekeeping_status",
            "permit_procedure_status",
            "root_causes",
            "root_cause_other",
            "corrective_action",
            "observer_sign",
            "supervisor_sign",
        )

    # =========================================================================
    # INITIAL VALUES / FORM SETUP
    # =========================================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        now = timezone.localtime()

        if not self.is_bound:
            self.fields[
                "observation_date"
            ].initial = timezone.localdate()

            self.fields[
                "observation_time"
            ].initial = now.strftime("%H:%M")

        # Prevent browser selection of a future date.
        self.fields[
            "observation_date"
        ].widget.attrs["max"] = (
            timezone.localdate().isoformat()
        )

    # =========================================================================
    # FIELD VALIDATION
    # =========================================================================

    def clean_employee_name(self):
        employee_name = (
            self.cleaned_data
            .get(
                "employee_name",
                "",
            )
            .strip()
        )

        if not employee_name:
            raise ValidationError(
                "Employee name is required."
            )

        return employee_name

    def clean_card_no(self):
        """
        Normalize Card No. before duplicate checking/storage.
        """

        card_no = (
            self.cleaned_data
            .get(
                "card_no",
                "",
            )
            .strip()
            .upper()
        )

        if not card_no:
            raise ValidationError(
                "Card number is required."
            )

        return card_no

    def clean_area(self):
        area = (
            self.cleaned_data
            .get(
                "area",
                "",
            )
            .strip()
        )

        if not area:
            raise ValidationError(
                "Area is required."
            )

        return area

    def clean_observer_name(self):
        return (
            self.cleaned_data
            .get(
                "observer_name",
                "",
            )
            .strip()
        )

    def clean_root_cause_other(self):
        return (
            self.cleaned_data
            .get(
                "root_cause_other",
                "",
            )
            .strip()
        )

    def clean_observer_sign(self):
        return (
            self.cleaned_data
            .get(
                "observer_sign",
                "",
            )
            .strip()
        )

    def clean_supervisor_sign(self):
        return (
            self.cleaned_data
            .get(
                "supervisor_sign",
                "",
            )
            .strip()
        )

    # =========================================================================
    # FORM-LEVEL VALIDATION
    # =========================================================================

    def clean(self):
        cleaned_data = super().clean()

        card_no = cleaned_data.get(
            "card_no"
        )

        observation_date = cleaned_data.get(
            "observation_date"
        )

        behaviour_type = cleaned_data.get(
            "behaviour_type"
        )

        root_causes = (
            cleaned_data.get(
                "root_causes"
            )
            or []
        )

        root_cause_other = (
            cleaned_data.get(
                "root_cause_other"
            )
            or ""
        )

        # ---------------------------------------------------------------------
        # FUTURE DATE VALIDATION
        # ---------------------------------------------------------------------

        if (
            observation_date
            and observation_date
            > timezone.localdate()
        ):
            self.add_error(
                "observation_date",
                (
                    "Future observation dates "
                    "are not allowed."
                ),
            )

        # ---------------------------------------------------------------------
        # ONE SUBMISSION PER CARD / DATE
        # ---------------------------------------------------------------------

        if card_no and observation_date:

            existing_submission = (
                BBSObservation.objects
                .filter(
                    card_no__iexact=card_no,
                    observation_date=observation_date,
                )
            )

            if (
                self.instance
                and self.instance.pk
            ):
                existing_submission = (
                    existing_submission.exclude(
                        pk=self.instance.pk
                    )
                )

            if existing_submission.exists():
                raise ValidationError(
                    (
                        "A BBS observation has already "
                        "been submitted for this Card No. "
                        "on the selected date."
                    )
                )

        # ---------------------------------------------------------------------
        # OTHER ROOT CAUSE VALIDATION
        # ---------------------------------------------------------------------

        if (
            root_cause_other
            and "OTHER" not in root_causes
        ):
            self.add_error(
                "root_cause_other",
                (
                    "Select 'Other' as a root cause "
                    "before entering another root cause."
                ),
            )

        if (
            "OTHER" in root_causes
            and not root_cause_other
        ):
            self.add_error(
                "root_cause_other",
                (
                    "Please specify the other "
                    "root cause."
                ),
            )

        # ---------------------------------------------------------------------
        # DETERMINE WHETHER ANY AT-RISK CONDITION EXISTS
        # ---------------------------------------------------------------------

        checklist_fields = (
            "ppe_status",
            "guarding_loto_status",
            "ergonomics_status",
            "tools_equipment_status",
            "housekeeping_status",
            "permit_procedure_status",
        )

        has_at_risk_check = any(
            cleaned_data.get(field_name)
            == BBSObservation.ChecklistStatus.AT_RISK
            for field_name in checklist_fields
        )

        observation_is_at_risk = (
            behaviour_type
            == BBSObservation.BehaviourType.AT_RISK
            or has_at_risk_check
        )

        # ---------------------------------------------------------------------
        # ROOT CAUSE APPLICABILITY
        # ---------------------------------------------------------------------

        if (
            root_causes
            and not observation_is_at_risk
        ):
            self.add_error(
                "root_causes",
                (
                    "Root cause should only be selected "
                    "when an At-Risk behaviour or "
                    "checklist condition is identified."
                ),
            )

        return cleaned_data