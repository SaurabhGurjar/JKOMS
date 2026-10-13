# quality_capa/models.py
from __future__ import annotations

import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone

from usermanagement.models import Employee, OrganizationUnit, Position, WorkflowInstance


ALLOWED_ATTACHMENT_EXTENSIONS = [
    "pdf", "png", "jpg", "jpeg", "webp", "doc", "docx",
    "xls", "xlsx", "csv", "txt",
]
MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024


def validate_attachment_size(uploaded_file):
    if uploaded_file and uploaded_file.size > MAX_ATTACHMENT_SIZE:
        raise ValidationError("Attachment size cannot exceed 20 MB.")


def capa_attachment_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    safe_filename = f"{uuid.uuid4().hex}{extension}"
    capa_number = (
        instance.capa.capa_number
        if instance.capa_id and instance.capa.capa_number
        else "unassigned"
    )
    attachment_type = getattr(instance, "attachment_type", "general") or "general"
    return f"quality_capa/{capa_number}/{attachment_type.lower()}/{safe_filename}"


class CAPANumberSequence(models.Model):
    """Monthly CAPA sequence in CAPA-YYYY-MM-NNNN format."""

    year = models.PositiveIntegerField(db_index=True)
    month = models.PositiveSmallIntegerField(db_index=True)
    last_number = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month"]
        verbose_name = "CAPA Number Sequence"
        verbose_name_plural = "CAPA Number Sequences"
        constraints = [
            models.UniqueConstraint(
                fields=["year", "month"],
                name="unique_capa_sequence_year_month",
            ),
            models.CheckConstraint(
                condition=Q(month__gte=1) & Q(month__lte=12),
                name="capa_sequence_month_range",
            ),
            models.CheckConstraint(
                condition=Q(last_number__gte=0),
                name="capa_sequence_number_nonnegative",
            ),
        ]

    @classmethod
    def get_next_number(cls, reference_date=None):
        reference_date = reference_date or timezone.localdate()
        year, month = reference_date.year, reference_date.month
        with transaction.atomic():
            sequence, _ = cls.objects.get_or_create(
                year=year,
                month=month,
                defaults={"last_number": 0},
            )
            cls.objects.filter(pk=sequence.pk).update(
                last_number=F("last_number") + 1,
                updated_at=timezone.now(),
            )
            sequence.refresh_from_db(fields=["last_number", "updated_at"])
            return f"CAPA-{year:04d}-{month:02d}-{sequence.last_number:04d}"

    def __str__(self):
        return f"CAPA-{self.year:04d}-{self.month:02d}: {self.last_number:04d}"


class CAPASource(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class CAPACategory(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "CAPA categories"

    def __str__(self):
        return f"{self.code} - {self.name}"


class CAPAManagementSystem(models.Model):
    """IATF, ISO, SA and other management systems applicable to a CAPA."""

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class CAPAFormDefinition(models.Model):
    """Versioned form definition linked later to a controlled QMS revision."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    code = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=150, default="CAPA Report")
    revision_number = models.CharField(max_length=20)
    revision_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    # Temporary bridge until the QMS Document Control app is implemented.
    qms_document_code = models.CharField(max_length=100, blank=True)
    qms_revision_reference = models.CharField(max_length=100, blank=True)
    qms_document_url = models.URLField(blank=True)

    configuration = models.JSONField(default=dict, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_form_definitions_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code", "-revision_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "revision_number"],
                name="unique_capa_form_revision",
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(status="PUBLISHED"),
                name="one_published_capa_form_per_code",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "Effective-to date cannot be before effective-from date."
        if self.status == self.Status.PUBLISHED and not self.published_at:
            errors["published_at"] = "Published-at time is required for a published definition."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.code} / {self.revision_number} / {self.revision_date:%d-%m-%Y}"


class CAPAFormSection(models.Model):
    form_definition = models.ForeignKey(
        CAPAFormDefinition,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    code = models.SlugField(max_length=100)
    title = models.CharField(max_length=200)
    title_hi = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["form_definition", "display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["form_definition", "code"],
                name="unique_capa_form_section_code",
            )
        ]

    def __str__(self):
        return f"{self.form_definition} - {self.title}"


class CAPAFormField(models.Model):
    class FieldType(models.TextChoices):
        TEXT = "TEXT", "Single-line Text"
        TEXTAREA = "TEXTAREA", "Multi-line Text"
        INTEGER = "INTEGER", "Integer"
        DECIMAL = "DECIMAL", "Decimal"
        BOOLEAN = "BOOLEAN", "Yes / No"
        DATE = "DATE", "Date"
        DATETIME = "DATETIME", "Date and Time"
        CHOICE = "CHOICE", "Single Choice"
        MULTI_CHOICE = "MULTI_CHOICE", "Multiple Choice"
        FILE = "FILE", "File"
        USER = "USER", "User"
        EMPLOYEE = "EMPLOYEE", "Employee"
        POSITION = "POSITION", "Position"
        ORGANIZATION_UNIT = "ORGANIZATION_UNIT", "Organization Unit"
        STATIC_TEXT = "STATIC_TEXT", "Instruction / Static Text"

    section = models.ForeignKey(
        CAPAFormSection,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    code = models.SlugField(max_length=100)
    label = models.CharField(max_length=250)
    label_hi = models.CharField(max_length=250, blank=True)
    help_text = models.TextField(blank=True)
    field_type = models.CharField(max_length=30, choices=FieldType.choices)
    display_order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    is_read_only = models.BooleanField(default=False)
    choices = models.JSONField(default=list, blank=True)
    validation_rules = models.JSONField(default=dict, blank=True)
    display_rules = models.JSONField(default=dict, blank=True)
    maps_to_model_field = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["section", "display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "code"],
                name="unique_capa_form_field_code",
            )
        ]

    def clean(self):
        super().clean()
        choice_types = {self.FieldType.CHOICE, self.FieldType.MULTI_CHOICE}
        if self.field_type in choice_types and not self.choices:
            raise ValidationError({"choices": "Choices are required for choice fields."})

    def __str__(self):
        return f"{self.section} - {self.label}"


class CAPA(models.Model):
    class CAPAType(models.TextChoices):
        CORRECTIVE = "CORRECTIVE", "Corrective Action"
        PREVENTIVE = "PREVENTIVE", "Preventive Action"
        CORRECTIVE_PREVENTIVE = "CORRECTIVE_PREVENTIVE", "Corrective and Preventive Action"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        ROOT_CAUSE_ANALYSIS = "ROOT_CAUSE_ANALYSIS", "Root Cause Analysis"
        ACTION_PLAN_REVIEW = "ACTION_PLAN_REVIEW", "Action Plan Review"
        ACTION_IN_PROGRESS = "ACTION_IN_PROGRESS", "Action In Progress"
        VERIFICATION = "VERIFICATION", "Verification"
        EFFECTIVENESS_REVIEW = "EFFECTIVENESS_REVIEW", "Effectiveness Review"
        CLOSED = "CLOSED", "Closed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class RiskLevel(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class NonConformanceCategory(models.TextChoices):
        MAJOR = "MAJOR", "Major"
        MINOR = "MINOR", "Minor"
        OBSERVATION = "OBSERVATION", "Observation"
        OTHER = "OTHER", "Other"

    capa_number = models.CharField(max_length=30, unique=True, editable=False, db_index=True)
    title = models.CharField(max_length=250)
    capa_type = models.CharField(
        max_length=30,
        choices=CAPAType.choices,
        default=CAPAType.CORRECTIVE_PREVENTIVE,
        db_index=True,
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)

    # Controlled form revision. Optional during initial rollout.
    form_definition = models.ForeignKey(
        CAPAFormDefinition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capas",
    )
    form_response = models.JSONField(default=dict, blank=True)
    form_definition_snapshot = models.JSONField(default=dict, blank=True, editable=False)

    management_systems = models.ManyToManyField(
        CAPAManagementSystem,
        blank=True,
        related_name="capas",
    )
    location_text = models.CharField(max_length=150, blank=True)
    nonconformity_number = models.CharField(max_length=100, blank=True, db_index=True)
    nonconformance_category = models.CharField(
        max_length=20,
        choices=NonConformanceCategory.choices,
        blank=True,
        db_index=True,
    )
    is_repeated_nonconformance = models.BooleanField(default=False)

    source = models.ForeignKey(CAPASource, on_delete=models.PROTECT, related_name="capas")
    category = models.ForeignKey(CAPACategory, on_delete=models.PROTECT, related_name="capas")
    organization_unit = models.ForeignKey(
        OrganizationUnit,
        on_delete=models.PROTECT,
        related_name="capas",
    )
    originating_organization_unit = models.ForeignKey(
        OrganizationUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="originated_capas",
    )
    owner_position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="owned_capas",
    )
    owner_employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="owned_capas",
    )
    reported_by_employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reported_capas",
    )

    auditor_name = models.CharField(max_length=200, blank=True)
    auditor_signature = models.FileField(
        upload_to="quality_capa/signatures/auditor/%Y/%m/",
        null=True,
        blank=True,
    )
    auditee_name = models.CharField(max_length=200, blank=True)
    auditee_signature = models.FileField(
        upload_to="quality_capa/signatures/auditee/%Y/%m/",
        null=True,
        blank=True,
    )
    audit_date = models.DateField(null=True, blank=True)
    section_area_audited = models.CharField(max_length=250, blank=True)
    clause_reference = models.CharField(max_length=250, blank=True)
    document_reference = models.CharField(max_length=250, blank=True)

    occurrence_date = models.DateField(null=True, blank=True)
    detection_date = models.DateField(default=timezone.localdate)
    target_completion_date = models.DateField(null=True, blank=True, db_index=True)
    actual_completion_date = models.DateField(null=True, blank=True)

    problem_description = models.TextField()
    immediate_correction = models.TextField(blank=True)
    correction_containment_action = models.TextField(blank=True)
    scope = models.TextField(blank=True)
    impact_description = models.TextField(blank=True)

    regulatory_impact = models.BooleanField(default=False)
    customer_impact = models.BooleanField(default=False)
    safety_impact = models.BooleanField(default=False)
    production_impact = models.BooleanField(default=False)
    financial_impact = models.BooleanField(default=False)

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )
    severity_score = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    occurrence_score = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    detection_score = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    risk_priority_number = models.PositiveIntegerField(default=1, editable=False, db_index=True)
    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
        db_index=True,
    )
    source_reference = models.CharField(max_length=150, blank=True)

    workflow_instance = models.OneToOneField(
        WorkflowInstance,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capas_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capas_updated",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_unit", "status"], name="capa_org_status_idx"),
            models.Index(fields=["owner_employee", "status"], name="capa_owner_status_idx"),
            models.Index(fields=["priority", "target_completion_date"], name="capa_priority_due_idx"),
            models.Index(fields=["source", "category"], name="capa_source_category_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(severity_score__gte=1) & Q(severity_score__lte=10),
                name="capa_severity_range",
            ),
            models.CheckConstraint(
                condition=Q(occurrence_score__gte=1) & Q(occurrence_score__lte=10),
                name="capa_occurrence_range",
            ),
            models.CheckConstraint(
                condition=Q(detection_score__gte=1) & Q(detection_score__lte=10),
                name="capa_detection_range",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.occurrence_date and self.detection_date and self.detection_date < self.occurrence_date:
            errors["detection_date"] = "Detection date cannot be before occurrence date."
        if self.target_completion_date and self.detection_date and self.target_completion_date < self.detection_date:
            errors["target_completion_date"] = "Target completion date cannot be before detection date."
        if self.actual_completion_date and self.detection_date and self.actual_completion_date < self.detection_date:
            errors["actual_completion_date"] = "Actual completion date cannot be before detection date."
        if (
            self.owner_position_id
            and self.organization_unit_id
            and self.owner_position.organization_unit_id != self.organization_unit_id
        ):
            errors["owner_position"] = "Owner position must belong to the responsible organization unit."
        if errors:
            raise ValidationError(errors)

    def calculate_risk(self):
        self.risk_priority_number = (
            (self.severity_score or 1)
            * (self.occurrence_score or 1)
            * (self.detection_score or 1)
        )
        if self.risk_priority_number <= 20:
            self.risk_level = self.RiskLevel.LOW
        elif self.risk_priority_number <= 60:
            self.risk_level = self.RiskLevel.MEDIUM
        elif self.risk_priority_number <= 150:
            self.risk_level = self.RiskLevel.HIGH
        else:
            self.risk_level = self.RiskLevel.CRITICAL

    @property
    def display_number(self):
        return f"CAPA No.: {self.capa_number}"

    @property
    def is_overdue(self):
        return bool(
            self.target_completion_date
            and self.status not in {self.Status.CLOSED, self.Status.CANCELLED, self.Status.REJECTED}
            and self.target_completion_date < timezone.localdate()
        )

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    def save(self, *args, **kwargs):
        if not self.capa_number:
            self.capa_number = CAPANumberSequence.get_next_number(timezone.localdate())
        self.calculate_risk()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.capa_number} - {self.title}"


class CAPARootCause(models.Model):
    class AnalysisMethod(models.TextChoices):
        FIVE_WHY = "FIVE_WHY", "5 Why"
        FISHBONE = "FISHBONE", "Fishbone / Ishikawa"
        FAULT_TREE = "FAULT_TREE", "Fault Tree Analysis"
        PARETO = "PARETO", "Pareto Analysis"
        FMEA = "FMEA", "FMEA"
        BRAINSTORMING = "BRAINSTORMING", "Brainstorming"
        OTHER = "OTHER", "Other"

    class CauseType(models.TextChoices):
        ROOT_CAUSE = "ROOT_CAUSE", "Root Cause"
        CONTRIBUTING_CAUSE = "CONTRIBUTING_CAUSE", "Contributing Cause"
        ESCAPE_CAUSE = "ESCAPE_CAUSE", "Escape Cause"

    capa = models.ForeignKey(CAPA, on_delete=models.CASCADE, related_name="root_causes")
    sequence = models.PositiveIntegerField(default=1)
    analysis_method = models.CharField(
        max_length=30,
        choices=AnalysisMethod.choices,
        default=AnalysisMethod.FIVE_WHY,
    )
    cause_type = models.CharField(
        max_length=30,
        choices=CauseType.choices,
        default=CauseType.ROOT_CAUSE,
    )
    why_1 = models.TextField(blank=True)
    why_2 = models.TextField(blank=True)
    why_3 = models.TextField(blank=True)
    why_4 = models.TextField(blank=True)
    why_5 = models.TextField(blank=True)
    cause_statement = models.TextField(blank=True)
    analysis_details = models.TextField(blank=True)
    evidence = models.TextField(blank=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_root_causes_confirmed",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_root_causes_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["capa", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["capa", "sequence"],
                name="unique_capa_root_cause_sequence",
            )
        ]

    def __str__(self):
        return f"{self.capa.capa_number} - Cause {self.sequence}"


class CAPAAction(models.Model):
    class ActionType(models.TextChoices):
        CORRECTION = "CORRECTION", "Immediate Correction"
        CONTAINMENT = "CONTAINMENT", "Containment"
        INTERMEDIATE = "INTERMEDIATE", "Intermediate / Short-Term Action"
        CORRECTIVE = "CORRECTIVE", "Corrective Action"
        PREVENTIVE = "PREVENTIVE", "Preventive Action"
        HORIZONTAL_DEPLOYMENT = "HORIZONTAL_DEPLOYMENT", "Horizontal Deployment"
        VERIFICATION = "VERIFICATION", "Verification Action"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        ON_HOLD = "ON_HOLD", "On Hold"

    capa = models.ForeignKey(CAPA, on_delete=models.CASCADE, related_name="actions")
    root_cause = models.ForeignKey(
        CAPARootCause,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="actions",
    )
    sequence = models.PositiveIntegerField(default=1)
    action_type = models.CharField(
        max_length=30,
        choices=ActionType.choices,
        default=ActionType.CORRECTIVE,
        db_index=True,
    )
    title = models.CharField(max_length=250, blank=True)
    description = models.TextField(blank=True)
    responsible_position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_actions",
    )
    responsible_employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_actions",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_actions_assigned",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True, db_index=True)
    revised_target_date = models.DateField(null=True, blank=True)
    revision_reason = models.TextField(blank=True)
    revised_date_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_action_revised_dates_approved",
    )
    revised_date_approved_at = models.DateTimeField(null=True, blank=True)
    actual_date = models.DateField(null=True, blank=True)
    completion_details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    completion_percentage = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    is_mandatory = models.BooleanField(default=False)
    requires_verification = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_actions_verified",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_comments = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_actions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_actions_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["capa", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["capa", "sequence"],
                name="unique_capa_action_sequence",
            ),
            models.CheckConstraint(
                condition=Q(completion_percentage__gte=0) & Q(completion_percentage__lte=100),
                name="capa_action_percentage_range",
            ),
        ]
        indexes = [
            models.Index(fields=["responsible_employee", "status"], name="capa_action_owner_status_idx"),
            models.Index(fields=["status", "target_date"], name="capa_action_status_due_idx"),
        ]

    @property
    def effective_target_date(self):
        return self.revised_target_date or self.target_date

    @property
    def is_overdue(self):
        return bool(
            self.effective_target_date
            and self.status not in {self.Status.COMPLETED, self.Status.VERIFIED, self.Status.CANCELLED}
            and self.effective_target_date < timezone.localdate()
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.root_cause_id and self.capa_id and self.root_cause.capa_id != self.capa_id:
            errors["root_cause"] = "Selected root cause must belong to this CAPA."
        if self.revised_target_date and self.target_date and self.revised_target_date < self.target_date:
            errors["revised_target_date"] = "Revised target date cannot precede the original target date."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.capa.capa_number} - Action {self.sequence}"


class CAPAAttachment(models.Model):
    class AttachmentType(models.TextChoices):
        INITIAL_EVIDENCE = "INITIAL_EVIDENCE", "Initial Evidence"
        ROOT_CAUSE = "ROOT_CAUSE", "Root Cause Analysis"
        ACTION_PLAN = "ACTION_PLAN", "Action Plan"
        COMPLETION_EVIDENCE = "COMPLETION_EVIDENCE", "Completion Evidence"
        VERIFICATION_EVIDENCE = "VERIFICATION_EVIDENCE", "Verification Evidence"
        EFFECTIVENESS_EVIDENCE = "EFFECTIVENESS_EVIDENCE", "Effectiveness Evidence"
        OTHER = "OTHER", "Other"

    capa = models.ForeignKey(CAPA, on_delete=models.CASCADE, related_name="attachments")
    action = models.ForeignKey(
        CAPAAction,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
    )
    root_cause = models.ForeignKey(
        CAPARootCause,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
    )
    attachment_type = models.CharField(
        max_length=30,
        choices=AttachmentType.choices,
        default=AttachmentType.OTHER,
        db_index=True,
    )
    title = models.CharField(max_length=250, blank=True)
    description = models.TextField(blank=True)
    file = models.FileField(
        upload_to=capa_attachment_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS),
            validate_attachment_size,
        ],
    )
    original_filename = models.CharField(max_length=255, blank=True, editable=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_attachments_uploaded",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.capa.capa_number} - {self.title or self.original_filename}"


class CAPAVerification(models.Model):
    class ReviewType(models.TextChoices):
        INTERMEDIATE = "INTERMEDIATE", "Intermediate Action Verification"
        CORRECTIVE = "CORRECTIVE", "Corrective Action Verification"
        HORIZONTAL_DEPLOYMENT = "HORIZONTAL_DEPLOYMENT", "Horizontal Deployment Verification"
        IMPLEMENTATION = "IMPLEMENTATION", "Implementation Verification"
        EFFECTIVENESS = "EFFECTIVENESS", "Effectiveness Review"
        FINAL_CLOSURE = "FINAL_CLOSURE", "Final Closure Review"

    class Result(models.TextChoices):
        SATISFACTORY = "SATISFACTORY", "Satisfactory"
        UNSATISFACTORY = "UNSATISFACTORY", "Unsatisfactory"
        EFFECTIVE = "EFFECTIVE", "Effective"
        PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE", "Partially Effective"
        NOT_EFFECTIVE = "NOT_EFFECTIVE", "Not Effective"
        MORE_EVIDENCE_REQUIRED = "MORE_EVIDENCE_REQUIRED", "More Evidence Required"

    capa = models.ForeignKey(CAPA, on_delete=models.CASCADE, related_name="verifications")
    action = models.ForeignKey(
        CAPAAction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verifications",
    )
    review_type = models.CharField(max_length=30, choices=ReviewType.choices, db_index=True)
    review_date = models.DateField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_verifications",
    )
    reviewed_as_position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_verifications",
    )
    verification_method = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    result = models.CharField(max_length=30, choices=Result.choices, blank=True, db_index=True)
    effectiveness_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_comments = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    is_final = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["capa", "-review_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["capa"],
                condition=Q(is_final=True),
                name="unique_final_verification_per_capa",
            )
        ]

    def __str__(self):
        return f"{self.capa.capa_number} - {self.get_review_type_display()}"


class CAPAFollowUpAudit(models.Model):
    capa = models.ForeignKey(CAPA, on_delete=models.CASCADE, related_name="follow_up_audits")
    due_date = models.DateField(null=True, blank=True, db_index=True)
    verified_on = models.DateField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_follow_up_audits",
    )
    verified_as_position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_follow_up_audits",
    )
    result = models.CharField(
        max_length=30,
        choices=CAPAVerification.Result.choices,
        blank=True,
    )
    observations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["capa", "due_date"]

    def __str__(self):
        return f"{self.capa.capa_number} - Follow-up Audit"


class CAPADocumentUpdate(models.Model):
    class DocumentType(models.TextChoices):
        CONTROL_PLAN = "CONTROL_PLAN", "Control Plan"
        FMEA = "FMEA", "FMEA"
        PROCESS_FLOW_CHART = "PROCESS_FLOW_CHART", "Process Flow Chart"
        WORK_INSTRUCTION = "WORK_INSTRUCTION", "Work Instruction"
        OTHER = "OTHER", "Other"

    capa = models.ForeignKey(CAPA, on_delete=models.CASCADE, related_name="document_updates")
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    update_required = models.BooleanField(default=False)
    document_reference = models.CharField(max_length=250, blank=True)
    description = models.TextField(blank=True)
    updated_on = models.DateField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_document_updates",
    )
    attachment = models.FileField(
        upload_to="quality_capa/document_updates/%Y/%m/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS),
            validate_attachment_size,
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["capa", "document_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["capa", "document_type"],
                name="unique_capa_document_update_type",
            )
        ]

    def __str__(self):
        return f"{self.capa.capa_number} - {self.get_document_type_display()}"


class CAPAStatusHistory(models.Model):
    capa = models.ForeignKey(CAPA, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(
        max_length=30,
        choices=CAPA.Status.choices,
        null=True,
        blank=True,
    )
    to_status = models.CharField(max_length=30, choices=CAPA.Status.choices, db_index=True)
    action = models.CharField(max_length=50, db_index=True)
    comments = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capa_status_changes",
    )
    changed_as_position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_status_changes",
    )
    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="capa_status_history",
    )
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["changed_at"]
        indexes = [
            models.Index(fields=["capa", "changed_at"], name="capa_history_date_idx"),
            models.Index(fields=["changed_by", "changed_at"], name="capa_history_user_idx"),
        ]

    def clean(self):
        super().clean()
        if self.from_status and self.from_status == self.to_status:
            raise ValidationError({"to_status": "New status must differ from previous status."})

    def __str__(self):
        return f"{self.capa.capa_number}: {self.from_status or 'NEW'} -> {self.to_status}"
