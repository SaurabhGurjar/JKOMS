# usermanagement/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    OrganizationUnitType,
    OrganizationUnit,
    Designation,
    Position,
    PositionReporting,
    Employee,
    EmployeePositionAssignment,
    User,
    Module,
    RoleType,
    Role,
    Permission,
    RolePermission,
    RoleAssignment,
    RoleAssignmentScope,
    Delegation,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTransition,
    AuthorityRule,
    WorkflowInstance,
    WorkflowAction,
    AuditLog,
)


# =============================================================================
# ADMIN SITE
# =============================================================================

admin.site.site_header = "JKOMS Administration"
admin.site.site_title = "JKOMS Admin"
admin.site.index_title = "JK Operations Management System"


# =============================================================================
# ORGANIZATION UNIT TYPE
# =============================================================================


@admin.register(OrganizationUnitType)
class OrganizationUnitTypeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "is_active",
        "updated_at",
    )

    list_filter = ("is_active",)

    search_fields = (
        "code",
        "name",
        "description",
    )

    ordering = ("name",)


# =============================================================================
# ORGANIZATION UNIT
# =============================================================================


@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "unit_type",
        "parent",
        "display_order",
        "is_active",
        "valid_from",
        "valid_to",
    )

    list_filter = (
        "unit_type",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
        "parent__code",
        "parent__name",
    )

    autocomplete_fields = (
        "parent",
        "unit_type",
    )

    ordering = (
        "display_order",
        "name",
    )

    list_select_related = (
        "unit_type",
        "parent",
    )

    fieldsets = (
        (
            "Organization Unit",
            {
                "fields": (
                    "code",
                    "name",
                    "unit_type",
                    "parent",
                )
            },
        ),
        (
            "Configuration",
            {
                "fields": (
                    "display_order",
                    "is_active",
                )
            },
        ),
        (
            "Validity",
            {
                "fields": (
                    "valid_from",
                    "valid_to",
                )
            },
        ),
    )


# =============================================================================
# DESIGNATION
# =============================================================================


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "grade",
        "rank_order",
        "is_active",
    )

    list_filter = (
        "grade",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
        "grade",
    )

    ordering = (
        "rank_order",
        "name",
    )


# =============================================================================
# POSITION REPORTING INLINE
# =============================================================================


class PositionReportingInline(admin.TabularInline):
    model = PositionReporting

    fk_name = "position"

    extra = 0

    autocomplete_fields = (
        "reports_to_position",
    )

    fields = (
        "reports_to_position",
        "relationship_type",
        "is_primary",
        "valid_from",
        "valid_to",
        "is_active",
    )


# =============================================================================
# POSITION
# =============================================================================


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "organization_unit",
        "designation",
        "position_category",
        "is_head_position",
        "sanctioned_strength",
        "is_active",
    )

    list_filter = (
        "organization_unit__unit_type",
        "organization_unit",
        "designation",
        "position_category",
        "is_head_position",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
        "organization_unit__code",
        "organization_unit__name",
        "designation__name",
    )

    autocomplete_fields = (
        "organization_unit",
        "designation",
    )

    list_select_related = (
        "organization_unit",
        "designation",
    )

    ordering = (
        "organization_unit",
        "display_order",
        "name",
    )

    inlines = [
        PositionReportingInline,
    ]

    fieldsets = (
        (
            "Position",
            {
                "fields": (
                    "code",
                    "name",
                    "organization_unit",
                    "designation",
                )
            },
        ),
        (
            "Position Configuration",
            {
                "fields": (
                    "position_category",
                    "is_head_position",
                    "sanctioned_strength",
                    "display_order",
                    "is_active",
                )
            },
        ),
        (
            "Validity",
            {
                "fields": (
                    "valid_from",
                    "valid_to",
                )
            },
        ),
    )


# =============================================================================
# POSITION REPORTING
# =============================================================================


@admin.register(PositionReporting)
class PositionReportingAdmin(admin.ModelAdmin):
    list_display = (
        "position",
        "reports_to_position",
        "relationship_type",
        "is_primary",
        "is_active",
        "valid_from",
        "valid_to",
    )

    list_filter = (
        "relationship_type",
        "is_primary",
        "is_active",
    )

    search_fields = (
        "position__code",
        "position__name",
        "reports_to_position__code",
        "reports_to_position__name",
    )

    autocomplete_fields = (
        "position",
        "reports_to_position",
    )

    list_select_related = (
        "position",
        "reports_to_position",
    )


# =============================================================================
# EMPLOYEE POSITION INLINE
# =============================================================================


class EmployeePositionAssignmentInline(admin.TabularInline):
    model = EmployeePositionAssignment

    extra = 0

    autocomplete_fields = (
        "position",
    )

    fields = (
        "position",
        "assignment_type",
        "is_primary",
        "effective_from",
        "effective_to",
        "is_active",
    )


# =============================================================================
# EMPLOYEE
# =============================================================================


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code",
        "full_name_display",
        "email",
        "mobile",
        "employment_status",
        "is_active",
    )

    list_filter = (
        "employment_status",
        "is_active",
    )

    search_fields = (
        "employee_code",
        "first_name",
        "middle_name",
        "last_name",
        "email",
        "mobile",
    )

    ordering = (
        "employee_code",
    )

    inlines = [
        EmployeePositionAssignmentInline,
    ]

    @admin.display(description="Employee Name")
    def full_name_display(self, obj):
        return obj.full_name


# =============================================================================
# EMPLOYEE POSITION ASSIGNMENT
# =============================================================================


@admin.register(EmployeePositionAssignment)
class EmployeePositionAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "position",
        "assignment_type",
        "is_primary",
        "effective_from",
        "effective_to",
        "is_active",
    )

    list_filter = (
        "assignment_type",
        "is_primary",
        "is_active",
    )

    search_fields = (
        "employee__employee_code",
        "employee__first_name",
        "employee__last_name",
        "position__code",
        "position__name",
    )

    autocomplete_fields = (
        "employee",
        "position",
    )

    list_select_related = (
        "employee",
        "position",
    )

    date_hierarchy = "effective_from"


# =============================================================================
# CUSTOM USER
# =============================================================================


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    list_display = (
        "username",
        "employee",
        "email",
        "is_staff",
        "is_active",
        "is_superuser",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "groups",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
        "employee__employee_code",
        "employee__first_name",
        "employee__last_name",
    )

    autocomplete_fields = (
        "employee",
    )

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "JKOMS Employee Link",
            {
                "fields": (
                    "employee",
                )
            },
        ),
        (
            "JKOMS Audit Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "last_login",
        "date_joined",
    )


# =============================================================================
# MODULE
# =============================================================================


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "parent_module",
        "route_name",
        "display_order",
        "is_enabled",
    )

    list_filter = (
        "is_enabled",
        "parent_module",
    )

    search_fields = (
        "code",
        "name",
        "description",
    )

    autocomplete_fields = (
        "parent_module",
    )

    ordering = (
        "display_order",
        "name",
    )


# =============================================================================
# ROLE TYPE
# =============================================================================


@admin.register(RoleType)
class RoleTypeAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "code",
        "name",
        "description",
    )


# =============================================================================
# ROLE PERMISSION INLINE
# =============================================================================


class RolePermissionInline(admin.TabularInline):
    model = RolePermission

    extra = 0

    autocomplete_fields = (
        "permission",
    )

    fields = (
        "permission",
        "effect",
    )

# =============================================================================
# ROLE PERMISSION INLINE
# =============================================================================


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0

    autocomplete_fields = (
        "permission",
    )

    fields = (
        "permission",
        "effect",
    )


# =============================================================================
# ROLE
# =============================================================================


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "role_type",
        "module",
        "is_system_role",
        "is_active",
    )

    list_filter = (
        "role_type",
        "module",
        "is_system_role",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
        "description",
        "role_type__name",
        "module__name",
    )

    autocomplete_fields = (
        "role_type",
        "module",
    )

    list_select_related = (
        "role_type",
        "module",
    )

    ordering = (
        "name",
    )

    inlines = [
        RolePermissionInline,
    ]

    fieldsets = (
        (
            "Role Information",
            {
                "fields": (
                    "code",
                    "name",
                    "role_type",
                    "module",
                )
            },
        ),
        (
            "Configuration",
            {
                "fields": (
                    "description",
                    "is_system_role",
                    "is_active",
                )
            },
        ),
    )


# =============================================================================
# PERMISSION
# =============================================================================


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "module",
        "resource",
        "action",
        "is_active",
    )

    list_filter = (
        "module",
        "resource",
        "action",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
        "resource",
        "action",
        "description",
        "module__name",
    )

    autocomplete_fields = (
        "module",
    )

    list_select_related = (
        "module",
    )

    ordering = (
        "module",
        "resource",
        "action",
    )


# =============================================================================
# ROLE PERMISSION
# =============================================================================


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):

    list_display = (
        "role",
        "permission",
        "effect",
    )

    list_filter = (
        "effect",
        "role",
        "permission__module",
    )

    search_fields = (
        "role__code",
        "role__name",
        "permission__code",
        "permission__name",
    )

    autocomplete_fields = (
        "role",
        "permission",
    )

    list_select_related = (
        "role",
        "permission",
    )


# =============================================================================
# ROLE ASSIGNMENT SCOPE INLINE
# =============================================================================


class RoleAssignmentScopeInline(admin.TabularInline):
    model = RoleAssignmentScope
    extra = 0

    autocomplete_fields = (
        "organization_unit",
        "module",
    )

    fields = (
        "organization_unit",
        "module",
        "include_descendants",
    )


# =============================================================================
# ROLE ASSIGNMENT
# =============================================================================


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):

    list_display = (
        "role",
        "assigned_target",
        "valid_from",
        "valid_to",
        "is_active",
        "assigned_by",
        "assigned_at",
    )

    list_filter = (
        "role",
        "is_active",
        "valid_from",
    )

    search_fields = (
        "role__code",
        "role__name",
        "user__username",
        "user__employee__employee_code",
        "position__code",
        "position__name",
    )

    autocomplete_fields = (
        "role",
        "user",
        "position",
        "assigned_by",
    )

    list_select_related = (
        "role",
        "user",
        "position",
        "assigned_by",
    )

    readonly_fields = (
        "assigned_at",
    )

    inlines = [
        RoleAssignmentScopeInline,
    ]

    ordering = (
        "-assigned_at",
    )

    @admin.display(description="Assigned To")
    def assigned_target(self, obj):
        if obj.user:
            return f"User: {obj.user}"

        if obj.position:
            return f"Position: {obj.position}"

        return "-"


# =============================================================================
# ROLE ASSIGNMENT SCOPE
# =============================================================================


@admin.register(RoleAssignmentScope)
class RoleAssignmentScopeAdmin(admin.ModelAdmin):

    list_display = (
        "role_assignment",
        "organization_unit",
        "module",
        "include_descendants",
    )

    list_filter = (
        "module",
        "include_descendants",
    )

    search_fields = (
        "role_assignment__role__code",
        "role_assignment__role__name",
        "organization_unit__code",
        "organization_unit__name",
        "module__code",
        "module__name",
    )

    autocomplete_fields = (
        "role_assignment",
        "organization_unit",
        "module",
    )

    list_select_related = (
        "role_assignment",
        "organization_unit",
        "module",
    )


# =============================================================================
# DELEGATION
# =============================================================================


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):

    list_display = (
        "delegator_user",
        "delegate_user",
        "role",
        "organization_unit",
        "module",
        "valid_from",
        "valid_to",
        "status",
    )

    list_filter = (
        "status",
        "module",
        "role",
    )

    search_fields = (
        "delegator_user__username",
        "delegator_user__employee__employee_code",
        "delegate_user__username",
        "delegate_user__employee__employee_code",
        "role__code",
        "role__name",
        "organization_unit__code",
        "organization_unit__name",
    )

    autocomplete_fields = (
        "delegator_user",
        "delegate_user",
        "role",
        "organization_unit",
        "module",
        "approved_by",
    )

    list_select_related = (
        "delegator_user",
        "delegate_user",
        "role",
        "organization_unit",
        "module",
        "approved_by",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    date_hierarchy = "valid_from"

    fieldsets = (
        (
            "Delegation",
            {
                "fields": (
                    "delegator_user",
                    "delegate_user",
                )
            },
        ),
        (
            "Authority",
            {
                "fields": (
                    "role",
                    "organization_unit",
                    "module",
                )
            },
        ),
        (
            "Validity",
            {
                "fields": (
                    "valid_from",
                    "valid_to",
                )
            },
        ),
        (
            "Approval",
            {
                "fields": (
                    "reason",
                    "status",
                    "approved_by",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# =============================================================================
# WORKFLOW STEP INLINE
# =============================================================================


class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 0

    fields = (
        "sequence",
        "code",
        "name",
        "step_type",
        "required_role",
        "required_permission",
        "is_mandatory",
        "allow_rejection",
        "allow_return",
    )

    autocomplete_fields = (
        "required_role",
        "required_permission",
    )

    ordering = (
        "sequence",
    )


# =============================================================================
# WORKFLOW DEFINITION
# =============================================================================


@admin.register(WorkflowDefinition)
class WorkflowDefinitionAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "module",
        "entity_type",
        "version",
        "status",
        "valid_from",
        "valid_to",
    )

    list_filter = (
        "module",
        "status",
        "entity_type",
    )

    search_fields = (
        "code",
        "name",
        "entity_type",
        "module__code",
        "module__name",
    )

    autocomplete_fields = (
        "module",
    )

    list_select_related = (
        "module",
    )

    ordering = (
        "module",
        "code",
        "-version",
    )

    inlines = [
        WorkflowStepInline,
    ]

    fieldsets = (
        (
            "Workflow",
            {
                "fields": (
                    "code",
                    "name",
                    "module",
                    "entity_type",
                    "version",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "valid_from",
                    "valid_to",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


# =============================================================================
# WORKFLOW STEP
# =============================================================================


@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):

    list_display = (
        "workflow_definition",
        "sequence",
        "code",
        "name",
        "step_type",
        "required_role",
        "required_permission",
        "is_mandatory",
    )

    list_filter = (
        "workflow_definition",
        "step_type",
        "is_mandatory",
        "allow_rejection",
        "allow_return",
    )

    search_fields = (
        "code",
        "name",
        "workflow_definition__code",
        "workflow_definition__name",
        "required_role__name",
        "required_permission__code",
    )

    autocomplete_fields = (
        "workflow_definition",
        "required_role",
        "required_permission",
    )

    list_select_related = (
        "workflow_definition",
        "required_role",
        "required_permission",
    )

    ordering = (
        "workflow_definition",
        "sequence",
    )

    fieldsets = (
        (
            "Workflow Step",
            {
                "fields": (
                    "workflow_definition",
                    "sequence",
                    "code",
                    "name",
                    "step_type",
                )
            },
        ),
        (
            "Authority Requirements",
            {
                "fields": (
                    "required_role",
                    "required_permission",
                )
            },
        ),
        (
            "Behavior",
            {
                "fields": (
                    "is_mandatory",
                    "allow_rejection",
                    "allow_return",
                )
            },
        ),
        (
            "Advanced Configuration",
            {
                "fields": (
                    "configuration",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# =============================================================================
# WORKFLOW TRANSITION
# =============================================================================


@admin.register(WorkflowTransition)
class WorkflowTransitionAdmin(admin.ModelAdmin):

    list_display = (
        "workflow_definition",
        "from_step",
        "action",
        "to_step",
        "is_active",
    )

    list_filter = (
        "workflow_definition",
        "action",
        "is_active",
    )

    search_fields = (
        "workflow_definition__code",
        "workflow_definition__name",
        "from_step__code",
        "from_step__name",
        "to_step__code",
        "to_step__name",
        "action",
    )

    autocomplete_fields = (
        "workflow_definition",
        "from_step",
        "to_step",
    )

    list_select_related = (
        "workflow_definition",
        "from_step",
        "to_step",
    )

    fieldsets = (
        (
            "Transition",
            {
                "fields": (
                    "workflow_definition",
                    "from_step",
                    "action",
                    "to_step",
                )
            },
        ),
        (
            "Condition",
            {
                "fields": (
                    "condition_definition",
                    "is_active",
                )
            },
        ),
    )


# =============================================================================
# AUTHORITY RULE
# =============================================================================


@admin.register(AuthorityRule)
class AuthorityRuleAdmin(admin.ModelAdmin):

    list_display = (
        "workflow_step",
        "resolution_strategy",
        "role",
        "position",
        "permission",
        "organization_unit_type",
        "specific_user",
        "priority",
        "is_active",
    )

    list_filter = (
        "resolution_strategy",
        "organization_unit_type",
        "is_active",
    )

    search_fields = (
        "workflow_step__code",
        "workflow_step__name",
        "role__code",
        "role__name",
        "position__code",
        "position__name",
        "permission__code",
        "specific_user__username",
    )

    autocomplete_fields = (
        "workflow_step",
        "role",
        "position",
        "permission",
        "organization_unit_type",
        "specific_user",
    )

    list_select_related = (
        "workflow_step",
        "role",
        "position",
        "permission",
        "organization_unit_type",
        "specific_user",
    )

    ordering = (
        "workflow_step",
        "priority",
    )

    fieldsets = (
        (
            "Workflow",
            {
                "fields": (
                    "workflow_step",
                    "resolution_strategy",
                    "priority",
                )
            },
        ),
        (
            "Authority Resolution",
            {
                "fields": (
                    "role",
                    "position",
                    "permission",
                    "organization_unit_type",
                    "specific_user",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                )
            },
        ),
    )


# =============================================================================
# WORKFLOW ACTION INLINE
# =============================================================================


class WorkflowActionInline(admin.TabularInline):
    model = WorkflowAction
    extra = 0

    can_delete = False

    fields = (
        "workflow_step",
        "action",
        "acted_by",
        "acted_as_position",
        "comments",
        "acted_at",
    )

    readonly_fields = (
        "workflow_step",
        "action",
        "acted_by",
        "acted_as_position",
        "comments",
        "acted_at",
    )

    ordering = (
        "acted_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


# =============================================================================
# WORKFLOW INSTANCE
# =============================================================================


@admin.register(WorkflowInstance)
class WorkflowInstanceAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "workflow_definition",
        "business_object_type",
        "business_object_id",
        "organization_unit",
        "current_step",
        "status",
        "started_by",
        "started_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "workflow_definition",
        "organization_unit",
    )

    search_fields = (
        "business_object_type",
        "business_object_id",
        "workflow_definition__code",
        "workflow_definition__name",
        "started_by__username",
    )

    autocomplete_fields = (
        "workflow_definition",
        "organization_unit",
        "current_step",
        "started_by",
    )

    list_select_related = (
        "workflow_definition",
        "organization_unit",
        "current_step",
        "started_by",
    )

    readonly_fields = (
        "started_at",
        "completed_at",
    )

    date_hierarchy = "started_at"

    ordering = (
        "-started_at",
    )

    inlines = [
        WorkflowActionInline,
    ]

    fieldsets = (
        (
            "Workflow",
            {
                "fields": (
                    "workflow_definition",
                    "current_step",
                    "status",
                )
            },
        ),
        (
            "Business Object",
            {
                "fields": (
                    "business_object_type",
                    "business_object_id",
                    "organization_unit",
                )
            },
        ),
        (
            "Execution",
            {
                "fields": (
                    "started_by",
                    "started_at",
                    "completed_at",
                )
            },
        ),
    )


# =============================================================================
# WORKFLOW ACTION
# =============================================================================


@admin.register(WorkflowAction)
class WorkflowActionAdmin(admin.ModelAdmin):

    list_display = (
        "workflow_instance",
        "workflow_step",
        "action",
        "acted_by",
        "acted_as_position",
        "acted_at",
    )

    list_filter = (
        "action",
        "workflow_step",
        "acted_at",
    )

    search_fields = (
        "workflow_instance__business_object_type",
        "workflow_instance__business_object_id",
        "workflow_step__name",
        "acted_by__username",
        "acted_as_position__code",
        "acted_as_position__name",
        "comments",
    )

    autocomplete_fields = (
        "workflow_instance",
        "workflow_step",
        "acted_by",
        "acted_as_position",
    )

    list_select_related = (
        "workflow_instance",
        "workflow_step",
        "acted_by",
        "acted_as_position",
    )

    readonly_fields = (
        "acted_at",
    )

    date_hierarchy = "acted_at"

    ordering = (
        "-acted_at",
    )


# =============================================================================
# AUDIT LOG
# =============================================================================


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):

    list_display = (
        "timestamp",
        "user",
        "employee",
        "module_code",
        "entity_type",
        "entity_id",
        "action",
        "ip_address",
    )

    list_filter = (
        "module_code",
        "entity_type",
        "action",
        "timestamp",
    )

    search_fields = (
        "user__username",
        "employee__employee_code",
        "employee__first_name",
        "employee__last_name",
        "module_code",
        "entity_type",
        "entity_id",
        "action",
    )

    readonly_fields = (
        "user",
        "employee",
        "module_code",
        "entity_type",
        "entity_id",
        "action",
        "old_values",
        "new_values",
        "ip_address",
        "user_agent",
        "timestamp",
    )

    list_select_related = (
        "user",
        "employee",
    )

    date_hierarchy = "timestamp"

    ordering = (
        "-timestamp",
    )

    fieldsets = (
        (
            "Audit Event",
            {
                "fields": (
                    "timestamp",
                    "user",
                    "employee",
                    "action",
                )
            },
        ),
        (
            "Entity",
            {
                "fields": (
                    "module_code",
                    "entity_type",
                    "entity_id",
                )
            },
        ),
        (
            "Changes",
            {
                "fields": (
                    "old_values",
                    "new_values",
                )
            },
        ),
        (
            "Request Information",
            {
                "fields": (
                    "ip_address",
                    "user_agent",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    # Audit records should not be manually created.
    def has_add_permission(self, request):
        return False

    # Audit records should be immutable.
    def has_change_permission(self, request, obj=None):
        return False

    # Audit records should not be manually deleted.
    def has_delete_permission(self, request, obj=None):
        return False