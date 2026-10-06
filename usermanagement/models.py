# usermanagement/models.py

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings


# =============================================================================
# ORGANIZATION STRUCTURE
# =============================================================================


class OrganizationUnitType(models.Model):
    """
    Defines configurable organization unit types.

    Examples:
    PLANT, SUB_PLANT, FUNCTION, DEPARTMENT, SECTION,
    SUB_SECTION, AREA, LINE, CELL, LAB, WORKSHOP, OFFICE.
    """

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Organization Unit Type"
        verbose_name_plural = "Organization Unit Types"

    def __str__(self):
        return f"{self.code} - {self.name}"


class OrganizationUnit(models.Model):
    """
    Generic organization node.

    Unlimited hierarchy is created through parent.

    Examples:
    LTP
      -> Quality
          -> Sub-Plant 2
              -> Tube Plant
    """

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)

    unit_type = models.ForeignKey(
        OrganizationUnitType,
        on_delete=models.PROTECT,
        related_name="organization_units",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )

    display_order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Organization Unit"
        verbose_name_plural = "Organization Units"

    def clean(self):
        super().clean()

        if self.pk and self.parent_id == self.pk:
            raise ValidationError(
                {"parent": "An organization unit cannot be its own parent."}
            )

        # Detect parent hierarchy cycle.
        parent = self.parent
        visited = set()

        while parent:
            if parent.pk in visited:
                raise ValidationError(
                    {"parent": "Circular organization hierarchy detected."}
                )

            visited.add(parent.pk)

            if self.pk and parent.pk == self.pk:
                raise ValidationError(
                    {"parent": "Circular organization hierarchy is not allowed."}
                )

            parent = parent.parent

        if self.valid_from and self.valid_to:
            if self.valid_to < self.valid_from:
                raise ValidationError(
                    {"valid_to": "Valid-to date cannot be before valid-from date."}
                )

    def __str__(self):
        return f"{self.code} - {self.name}"


# =============================================================================
# DESIGNATION
# =============================================================================


class Designation(models.Model):
    """
    HR designation/title.

    Designation does NOT determine system authority.

    Examples:
    General Manager
    Senior Manager
    Manager
    Assistant Manager
    Engineer
    Executive
    Operator
    """

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)

    grade = models.CharField(max_length=30, blank=True)

    rank_order = models.PositiveIntegerField(
        default=0,
        help_text="Used for display/order only, not reporting authority.",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rank_order", "name"]

    def __str__(self):
        if self.grade:
            return f"{self.name} ({self.grade})"
        return self.name


# =============================================================================
# POSITION
# =============================================================================


class Position(models.Model):
    """
    Represents an organizational job/responsibility.

    Examples:
    Plant Head
    Plant Quality Head
    Sub-Plant 2 Quality Head
    Tube Plant Section Manager
    """

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)

    organization_unit = models.ForeignKey(
        OrganizationUnit,
        on_delete=models.PROTECT,
        related_name="positions",
    )

    designation = models.ForeignKey(
        Designation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="positions",
    )

    position_category = models.CharField(
        max_length=50,
        blank=True,
    )

    is_head_position = models.BooleanField(
        default=False,
        help_text="Indicates that this position heads its organization unit.",
    )

    sanctioned_strength = models.PositiveIntegerField(default=1)

    display_order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "organization_unit",
            "display_order",
            "name",
        ]

    def clean(self):
        super().clean()

        if self.valid_from and self.valid_to:
            if self.valid_to < self.valid_from:
                raise ValidationError(
                    {"valid_to": "Valid-to date cannot be before valid-from date."}
                )

    def __str__(self):
        return f"{self.code} - {self.name}"


# =============================================================================
# POSITION REPORTING STRUCTURE
# =============================================================================


class PositionReporting(models.Model):
    """
    Defines position-to-position reporting.

    Reporting hierarchy is intentionally independent from
    the OrganizationUnit hierarchy.
    """

    class RelationshipType(models.TextChoices):
        SOLID_LINE = "SOLID_LINE", "Solid Line"
        DOTTED_LINE = "DOTTED_LINE", "Dotted Line"
        FUNCTIONAL = "FUNCTIONAL", "Functional"
        ADMINISTRATIVE = "ADMINISTRATIVE", "Administrative"
        TECHNICAL = "TECHNICAL", "Technical"

    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="reporting_relationships",
    )

    reports_to_position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="subordinate_relationships",
    )

    relationship_type = models.CharField(
        max_length=20,
        choices=RelationshipType.choices,
        default=RelationshipType.SOLID_LINE,
    )

    is_primary = models.BooleanField(default=True)

    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Position Reporting Relationship"
        verbose_name_plural = "Position Reporting Relationships"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "position",
                    "reports_to_position",
                    "relationship_type",
                ],
                name="unique_position_reporting_relationship",
            ),
        ]

    def clean(self):
        super().clean()

        if self.position_id == self.reports_to_position_id:
            raise ValidationError(
                "A position cannot report to itself."
            )

        if self.valid_from and self.valid_to:
            if self.valid_to < self.valid_from:
                raise ValidationError(
                    {"valid_to": "Valid-to date cannot be before valid-from date."}
                )

        # Reporting cycle detection for existing records.
        if self.position_id and self.reports_to_position_id:
            target_position = self.reports_to_position
            visited = set()

            while target_position:
                if target_position.pk in visited:
                    break

                visited.add(target_position.pk)

                if target_position.pk == self.position_id:
                    raise ValidationError(
                        "Circular position reporting is not allowed."
                    )

                relation = (
                    PositionReporting.objects
                    .filter(
                        position=target_position,
                        relationship_type=self.RelationshipType.SOLID_LINE,
                        is_primary=True,
                        is_active=True,
                    )
                    .exclude(pk=self.pk)
                    .select_related("reports_to_position")
                    .first()
                )

                if not relation:
                    break

                target_position = relation.reports_to_position

    def __str__(self):
        return (
            f"{self.position.name} -> "
            f"{self.reports_to_position.name}"
        )


# =============================================================================
# EMPLOYEE
# =============================================================================


class Employee(models.Model):

    class EmploymentStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        RETIRED = "RETIRED", "Retired"
        RESIGNED = "RESIGNED", "Resigned"
        TERMINATED = "TERMINATED", "Terminated"
        SUSPENDED = "SUSPENDED", "Suspended"

    employee_code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )

    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    email = models.EmailField(blank=True)

    mobile = models.CharField(
        max_length=20,
        blank=True,
    )

    date_of_joining = models.DateField(
        null=True,
        blank=True,
    )

    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
        db_index=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_code"]

    @property
    def full_name(self):
        return " ".join(
            value
            for value in [
                self.first_name,
                self.middle_name,
                self.last_name,
            ]
            if value
        )

    def __str__(self):
        return f"{self.employee_code} - {self.full_name}"


# =============================================================================
# EMPLOYEE POSITION ASSIGNMENT
# =============================================================================


class EmployeePositionAssignment(models.Model):

    class AssignmentType(models.TextChoices):
        PERMANENT = "PERMANENT", "Permanent"
        ACTING = "ACTING", "Acting"
        ADDITIONAL_CHARGE = "ADDITIONAL_CHARGE", "Additional Charge"
        TEMPORARY = "TEMPORARY", "Temporary"

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="position_assignments",
    )

    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )

    assignment_type = models.CharField(
        max_length=30,
        choices=AssignmentType.choices,
        default=AssignmentType.PERMANENT,
    )

    is_primary = models.BooleanField(default=True)

    effective_from = models.DateField()

    effective_to = models.DateField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "-effective_from",
        ]

    def clean(self):
        super().clean()

        if self.effective_to:
            if self.effective_to < self.effective_from:
                raise ValidationError(
                    {
                        "effective_to":
                            "Effective-to date cannot be before effective-from date."
                    }
                )

    def __str__(self):
        return (
            f"{self.employee.employee_code} -> "
            f"{self.position.name}"
        )


# =============================================================================
# CUSTOM USER
# =============================================================================


class User(AbstractUser):
    """
    JKOMS authentication user.

    User and Employee remain separate concepts.
    External/service accounts may exist without Employee.
    """

    employee = models.OneToOneField(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_account",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.employee:
            return (
                f"{self.username} - "
                f"{self.employee.full_name}"
            )
        return self.username


# =============================================================================
# JKOMS MODULE REGISTRY
# =============================================================================


class Module(models.Model):
    """
    Registers JKOMS modules/submodules.

    Core authorization does not depend on fixed module names.
    """

    code = models.CharField(
        max_length=50,
        unique=True,
    )

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    parent_module = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )

    route_name = models.CharField(
        max_length=150,
        blank=True,
    )

    icon = models.CharField(
        max_length=100,
        blank=True,
    )

    display_order = models.PositiveIntegerField(default=0)

    is_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def clean(self):
        super().clean()

        if self.pk and self.parent_module_id == self.pk:
            raise ValidationError(
                {"parent_module": "A module cannot be its own parent."}
            )

    def __str__(self):
        return f"{self.code} - {self.name}"


# =============================================================================
# ROLE TYPE
# =============================================================================


class RoleType(models.Model):
    """
    Suggested role types:
    SYSTEM
    FUNCTIONAL
    WORKFLOW
    SPECIAL
    """

    code = models.CharField(
        max_length=30,
        unique=True,
    )

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


# =============================================================================
# ROLE
# =============================================================================


class Role(models.Model):

    code = models.CharField(
        max_length=50,
        unique=True,
    )

    name = models.CharField(max_length=150)

    role_type = models.ForeignKey(
        RoleType,
        on_delete=models.PROTECT,
        related_name="roles",
    )

    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="roles",
    )

    description = models.TextField(blank=True)

    is_system_role = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


# =============================================================================
# PERMISSION
# =============================================================================


class Permission(models.Model):
    """
    JKOMS business permission.

    Examples:
        quality.ncmr.view
        quality.ncmr.create
        quality.ncmr.approve
        masters.organization.edit
    """

    code = models.CharField(
        max_length=150,
        unique=True,
    )

    name = models.CharField(max_length=150)

    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name="permissions",
    )

    resource = models.CharField(max_length=100)

    action = models.CharField(max_length=50)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "module",
            "resource",
            "action",
        ]

    def __str__(self):
        return self.code


# =============================================================================
# ROLE PERMISSION
# =============================================================================


class RolePermission(models.Model):

    class Effect(models.TextChoices):
        ALLOW = "ALLOW", "Allow"
        DENY = "DENY", "Deny"

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )

    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )

    effect = models.CharField(
        max_length=10,
        choices=Effect.choices,
        default=Effect.ALLOW,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "role",
                    "permission",
                ],
                name="unique_role_permission",
            ),
        ]

    def __str__(self):
        return (
            f"{self.role.name} - "
            f"{self.permission.code} - "
            f"{self.effect}"
        )


# =============================================================================
# ROLE ASSIGNMENT
# =============================================================================


class RoleAssignment(models.Model):
    """
    Assigns a Role to either:
        1. User
        2. Position

    Exactly one target should be used.

    Position-based assignment is preferred for organizational authority.
    """

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_assignments",
    )

    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_assignments",
    )

    valid_from = models.DateField(
        null=True,
        blank=True,
    )

    valid_to = models.DateField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_assignments_created",
    )

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(user__isnull=False)
                        & models.Q(position__isnull=True)
                    )
                    |
                    (
                        models.Q(user__isnull=True)
                        & models.Q(position__isnull=False)
                    )
                ),
                name="role_assignment_exactly_one_target",
            ),
        ]

    def clean(self):
        super().clean()

        if bool(self.user_id) == bool(self.position_id):
            raise ValidationError(
                "Role must be assigned to exactly one User or Position."
            )

        if self.valid_from and self.valid_to:
            if self.valid_to < self.valid_from:
                raise ValidationError(
                    {"valid_to": "Valid-to date cannot be before valid-from date."}
                )

    def __str__(self):
        target = self.user or self.position
        return f"{self.role.name} -> {target}"


# =============================================================================
# ROLE ASSIGNMENT SCOPE
# =============================================================================


class RoleAssignmentScope(models.Model):
    """
    Restricts role authority by organization and/or module.

    Example:
        Role: Quality Approver
        Organization Unit: Sub-Plant 2
        Include Descendants: Yes
    """

    role_assignment = models.ForeignKey(
        RoleAssignment,
        on_delete=models.CASCADE,
        related_name="scopes",
    )

    organization_unit = models.ForeignKey(
        OrganizationUnit,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_scopes",
    )

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_scopes",
    )

    include_descendants = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.role_assignment} / "
            f"{self.organization_unit or 'All Organization'} / "
            f"{self.module or 'All Modules'}"
        )


# =============================================================================
# DELEGATION
# =============================================================================


class Delegation(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending Approval"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        REVOKED = "REVOKED", "Revoked"
        REJECTED = "REJECTED", "Rejected"

    delegator_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_given",
    )

    delegate_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_received",
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="delegations",
    )

    organization_unit = models.ForeignKey(
        OrganizationUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="delegations",
    )

    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="delegations",
    )

    valid_from = models.DateTimeField()

    valid_to = models.DateTimeField()

    reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delegations_approved",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if (
            self.delegator_user_id
            and self.delegator_user_id == self.delegate_user_id
        ):
            raise ValidationError(
                "A user cannot delegate authority to themselves."
            )

        if (
            self.valid_from
            and self.valid_to
            and self.valid_to <= self.valid_from
        ):
            raise ValidationError(
                {
                    "valid_to":
                        "Delegation end time must be after the start time."
                }
            )

    def __str__(self):
        return (
            f"{self.delegator_user} -> "
            f"{self.delegate_user}"
        )


# =============================================================================
# WORKFLOW DEFINITION
# =============================================================================


class WorkflowDefinition(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        RETIRED = "RETIRED", "Retired"

    code = models.CharField(max_length=100)

    name = models.CharField(max_length=150)

    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name="workflow_definitions",
    )

    entity_type = models.CharField(
        max_length=100,
        help_text="Business entity handled by this workflow.",
    )

    version = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    valid_from = models.DateField(
        null=True,
        blank=True,
    )

    valid_to = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "module",
            "code",
            "-version",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "code",
                    "version",
                ],
                name="unique_workflow_code_version",
            ),
        ]

    def clean(self):
        super().clean()

        if self.valid_from and self.valid_to:
            if self.valid_to < self.valid_from:
                raise ValidationError(
                    {"valid_to": "Valid-to cannot be before valid-from."}
                )

    def __str__(self):
        return f"{self.name} v{self.version}"


# =============================================================================
# WORKFLOW STEP
# =============================================================================


class WorkflowStep(models.Model):

    class StepType(models.TextChoices):
        START = "START", "Start"
        SUBMIT = "SUBMIT", "Submit"
        REVIEW = "REVIEW", "Review"
        APPROVAL = "APPROVAL", "Approval"
        ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT", "Acknowledgement"
        SYSTEM = "SYSTEM", "System"
        END = "END", "End"

    workflow_definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.CASCADE,
        related_name="steps",
    )

    code = models.CharField(max_length=50)

    name = models.CharField(max_length=150)

    sequence = models.PositiveIntegerField(default=0)

    step_type = models.CharField(
        max_length=30,
        choices=StepType.choices,
    )

    required_role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="required_workflow_steps",
    )

    required_permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="required_workflow_steps",
    )

    is_mandatory = models.BooleanField(default=True)

    allow_rejection = models.BooleanField(default=True)

    allow_return = models.BooleanField(default=True)

    configuration = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "workflow_definition",
            "sequence",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "workflow_definition",
                    "code",
                ],
                name="unique_workflow_step_code",
            ),
        ]

    def __str__(self):
        return (
            f"{self.workflow_definition.name} - "
            f"{self.name}"
        )


# =============================================================================
# WORKFLOW TRANSITION
# =============================================================================


class WorkflowTransition(models.Model):

    workflow_definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.CASCADE,
        related_name="transitions",
    )

    from_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name="outgoing_transitions",
    )

    to_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="incoming_transitions",
    )

    action = models.CharField(
        max_length=50,
    )

    condition_definition = models.JSONField(
        default=dict,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "workflow_definition",
                    "from_step",
                    "to_step",
                    "action",
                ],
                name="unique_workflow_transition",
            ),
        ]

    def clean(self):
        super().clean()

        if self.from_step_id:
            if (
                self.from_step.workflow_definition_id
                != self.workflow_definition_id
            ):
                raise ValidationError(
                    {
                        "from_step":
                            "From-step must belong to the selected workflow."
                    }
                )

        if self.to_step_id:
            if (
                self.to_step.workflow_definition_id
                != self.workflow_definition_id
            ):
                raise ValidationError(
                    {
                        "to_step":
                            "To-step must belong to the selected workflow."
                    }
                )

    def __str__(self):
        destination = self.to_step.name if self.to_step else "END"

        return (
            f"{self.from_step.name} "
            f"--{self.action}--> "
            f"{destination}"
        )


# =============================================================================
# AUTHORITY RULE
# =============================================================================


class AuthorityRule(models.Model):

    class ResolutionStrategy(models.TextChoices):
        ROLE_WITH_SCOPE = (
            "ROLE_WITH_SCOPE",
            "Role with Scope",
        )
        POSITION = (
            "POSITION",
            "Position",
        )
        REPORTING_MANAGER = (
            "REPORTING_MANAGER",
            "Reporting Manager",
        )
        ORG_UNIT_HEAD = (
            "ORG_UNIT_HEAD",
            "Organization Unit Head",
        )
        PARENT_UNIT_HEAD = (
            "PARENT_UNIT_HEAD",
            "Parent Organization Unit Head",
        )
        SPECIFIC_USER = (
            "SPECIFIC_USER",
            "Specific User",
        )
        INITIATOR_MANAGER = (
            "INITIATOR_MANAGER",
            "Initiator Manager",
        )

    workflow_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name="authority_rules",
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authority_rules",
    )

    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authority_rules",
    )

    permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authority_rules",
    )

    organization_unit_type = models.ForeignKey(
        OrganizationUnitType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authority_rules",
    )

    specific_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="specific_authority_rules",
    )

    resolution_strategy = models.CharField(
        max_length=30,
        choices=ResolutionStrategy.choices,
    )

    priority = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "workflow_step",
            "priority",
        ]

    def clean(self):
        super().clean()

        if (
            self.resolution_strategy
            == self.ResolutionStrategy.SPECIFIC_USER
            and not self.specific_user_id
        ):
            raise ValidationError(
                {
                    "specific_user":
                        "Specific User is required for this resolution strategy."
                }
            )

    def __str__(self):
        return (
            f"{self.workflow_step} - "
            f"{self.get_resolution_strategy_display()}"
        )


# =============================================================================
# WORKFLOW INSTANCE
# =============================================================================


class WorkflowInstance(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    workflow_definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.PROTECT,
        related_name="instances",
    )

    business_object_type = models.CharField(
        max_length=100,
        db_index=True,
    )

    business_object_id = models.PositiveBigIntegerField(
        db_index=True,
    )

    organization_unit = models.ForeignKey(
        OrganizationUnit,
        on_delete=models.PROTECT,
        related_name="workflow_instances",
    )

    current_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="current_instances",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workflows_started",
    )

    started_at = models.DateTimeField(auto_now_add=True)

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]

        indexes = [
            models.Index(
                fields=[
                    "business_object_type",
                    "business_object_id",
                ]
            ),
        ]

    def clean(self):
        super().clean()

        if self.current_step_id:
            if (
                self.current_step.workflow_definition_id
                != self.workflow_definition_id
            ):
                raise ValidationError(
                    {
                        "current_step":
                            "Current step must belong to the workflow definition."
                    }
                )

    def __str__(self):
        return (
            f"{self.workflow_definition.name}: "
            f"{self.business_object_type} "
            f"#{self.business_object_id}"
        )


# =============================================================================
# WORKFLOW ACTION / HISTORY
# =============================================================================


class WorkflowAction(models.Model):

    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name="actions",
    )

    workflow_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.PROTECT,
        related_name="workflow_actions",
    )

    action = models.CharField(max_length=50)

    acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workflow_actions",
    )

    acted_as_position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_actions",
    )

    comments = models.TextField(blank=True)

    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["acted_at"]

    def __str__(self):
        return (
            f"{self.workflow_instance} - "
            f"{self.action} by {self.acted_by}"
        )


# =============================================================================
# AUDIT LOG
# =============================================================================


class AuditLog(models.Model):
    """
    Generic JKOMS audit trail.

    old_values/new_values allow any present or future module
    to use the same audit framework.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    module_code = models.CharField(
        max_length=50,
        db_index=True,
    )

    entity_type = models.CharField(
        max_length=100,
        db_index=True,
    )

    entity_id = models.CharField(
        max_length=100,
        db_index=True,
    )

    action = models.CharField(
        max_length=50,
        db_index=True,
    )

    old_values = models.JSONField(
        default=dict,
        blank=True,
    )

    new_values = models.JSONField(
        default=dict,
        blank=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.TextField(blank=True)

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-timestamp"]

        indexes = [
            models.Index(
                fields=[
                    "module_code",
                    "entity_type",
                    "entity_id",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "timestamp",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.module_code}:"
            f"{self.entity_type}:"
            f"{self.entity_id} - "
            f"{self.action}"
        )