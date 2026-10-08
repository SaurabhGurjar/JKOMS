from django.db import models

# Create your models here.
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# =============================================================================
# BBS OBSERVATION
# =============================================================================


class BBSObservation(models.Model):
    """
    Behaviour Based Safety (BBS) daily observation.

    Initial implementation:
    - Public submission
    - No JKOMS login required
    - Employee identifies themselves using Name + Card No.
    - One submission per Card No. per Observation Date
    - Used for daily/monthly compliance monitoring

    The observed employee remains anonymous.
    """

    # -------------------------------------------------------------------------
    # SHIFT
    # -------------------------------------------------------------------------

    class Shift(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"

    # -------------------------------------------------------------------------
    # BEHAVIOUR TYPE
    # -------------------------------------------------------------------------

    class BehaviourType(models.TextChoices):
        SAFE = "SAFE", "Safe Act"
        AT_RISK = "AT_RISK", "At-Risk Act"

    # -------------------------------------------------------------------------
    # CHECKLIST STATUS
    # -------------------------------------------------------------------------

    class ChecklistStatus(models.TextChoices):
        SAFE = "SAFE", "Safe"
        AT_RISK = "AT_RISK", "At-Risk"
        NA = "NA", "N/A"

    # =========================================================================
    # EMPLOYEE / SUBMITTER
    # =========================================================================

    employee_name = models.CharField(
        max_length=150,
        help_text="Name of the employee submitting the BBS observation.",
    )

    card_no = models.CharField(
        max_length=30,
        db_index=True,
        help_text="Employee card number.",
    )

    # =========================================================================
    # OBSERVATION INFORMATION
    # =========================================================================

    observation_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
    )

    observation_time = models.TimeField(
        default=timezone.localtime,
    )

    shift = models.CharField(
        max_length=1,
        choices=Shift.choices,
        db_index=True,
    )

    area = models.CharField(
        max_length=150,
    )

    observer_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional observer name.",
    )

    # =========================================================================
    # A. ACTIVATOR
    # =========================================================================

    activator = models.TextField(
        blank=True,
        help_text=(
            "What prompted the behaviour, such as "
            "sign, instruction, condition or habit."
        ),
    )

    # =========================================================================
    # B. BEHAVIOUR
    # =========================================================================

    behaviour_type = models.CharField(
        max_length=20,
        choices=BehaviourType.choices,
        db_index=True,
    )

    behaviour_categories = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Selected behaviour categories such as "
            "PPE, LOTO, Ergonomics, Tools, "
            "Housekeeping or Permit."
        ),
    )

    behaviour_description = models.TextField(
        blank=True,
    )

    # =========================================================================
    # C. CONSEQUENCE / FEEDBACK
    # =========================================================================

    consequences = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Selected consequences or feedback actions."
        ),
    )

    feedback = models.TextField(
        blank=True,
        help_text="Feedback given on the spot.",
    )

    # =========================================================================
    # CRITICAL BEHAVIOUR CHECKLIST
    # =========================================================================

    ppe_status = models.CharField(
        max_length=20,
        choices=ChecklistStatus.choices,
        verbose_name="PPE Compliance",
    )

    guarding_loto_status = models.CharField(
        max_length=20,
        choices=ChecklistStatus.choices,
        verbose_name="Machine Guarding / LOTO",
    )

    ergonomics_status = models.CharField(
        max_length=20,
        choices=ChecklistStatus.choices,
        verbose_name="Body Position / Ergonomics",
    )

    tools_equipment_status = models.CharField(
        max_length=20,
        choices=ChecklistStatus.choices,
        verbose_name="Tools / Equipment",
    )

    housekeeping_status = models.CharField(
        max_length=20,
        choices=ChecklistStatus.choices,
        verbose_name="Housekeeping",
    )

    permit_procedure_status = models.CharField(
        max_length=20,
        choices=ChecklistStatus.choices,
        verbose_name="Permit / Procedure",
    )

    # =========================================================================
    # AT-RISK ROOT CAUSE
    # =========================================================================

    root_causes = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Likely root causes selected when "
            "at-risk behaviour is observed."
        ),
    )

    root_cause_other = models.CharField(
        max_length=250,
        blank=True,
    )

    corrective_action = models.TextField(
        blank=True,
        help_text=(
            "Corrective or preventive action identified "
            "during the observation."
        ),
    )

    # =========================================================================
    # SIGN / ACKNOWLEDGEMENT
    # =========================================================================

    observer_sign = models.CharField(
        max_length=150,
        blank=True,
    )

    supervisor_sign = models.CharField(
        max_length=150,
        blank=True,
    )

    # =========================================================================
    # PUBLIC SUBMISSION INFORMATION
    # =========================================================================

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.TextField(
        blank=True,
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta:
        ordering = [
            "-observation_date",
            "-submitted_at",
        ]

        verbose_name = "BBS Observation"
        verbose_name_plural = "BBS Observations"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "card_no",
                    "observation_date",
                ],
                name="unique_daily_bbs_card_submission",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "observation_date",
                    "card_no",
                ],
                name="bbs_date_card_idx",
            ),
            models.Index(
                fields=[
                    "observation_date",
                    "shift",
                ],
                name="bbs_date_shift_idx",
            ),
            models.Index(
                fields=[
                    "behaviour_type",
                    "observation_date",
                ],
                name="bbs_behavior_date_idx",
            ),
        ]

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        super().clean()

        if self.employee_name:
            self.employee_name = (
                self.employee_name.strip()
            )

        if self.card_no:
            self.card_no = (
                self.card_no.strip().upper()
            )

        if self.area:
            self.area = self.area.strip()

        if self.observer_name:
            self.observer_name = (
                self.observer_name.strip()
            )

        # Other root cause should only contain a value when
        # OTHER has been selected.
        if (
            self.root_cause_other
            and "OTHER" not in self.root_causes
        ):
            raise ValidationError(
                {
                    "root_cause_other": (
                        "Select 'Other' as a root cause "
                        "before entering another root cause."
                    )
                }
            )

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def has_at_risk_check(self):
        """
        Return True if any critical behaviour checklist item
        has been marked At-Risk.
        """

        checklist_values = (
            self.ppe_status,
            self.guarding_loto_status,
            self.ergonomics_status,
            self.tools_equipment_status,
            self.housekeeping_status,
            self.permit_procedure_status,
        )

        return (
            self.ChecklistStatus.AT_RISK
            in checklist_values
        )

    @property
    def is_at_risk(self):
        """
        Overall indication that the observation contains
        an at-risk behaviour.
        """

        return (
            self.behaviour_type
            == self.BehaviourType.AT_RISK
            or self.has_at_risk_check
        )

    def __str__(self):
        return (
            f"{self.observation_date} - "
            f"{self.card_no} - "
            f"{self.employee_name}"
        )