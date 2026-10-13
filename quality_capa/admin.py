# quality_capa/admin.py

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    CAPA,
    CAPAAction,
    CAPAAttachment,
    CAPACategory,
    CAPADocumentUpdate,
    CAPAFollowUpAudit,
    CAPAFormDefinition,
    CAPAFormField,
    CAPAFormSection,
    CAPAManagementSystem,
    CAPANumberSequence,
    CAPARootCause,
    CAPASource,
    CAPAStatusHistory,
    CAPAVerification,
)


admin.site.site_header = "LTPOMS Administration"
admin.site.site_title = "LTPOMS Admin"
admin.site.index_title = "LTPOMS Master Data and Transaction Administration"


class ReadOnlyAuditMixin:
    """Make standard audit fields read-only when present on a model."""

    audit_field_names = (
        "created_at",
        "updated_at",
        "uploaded_at",
        "changed_at",
        "published_at",
        "submitted_at",
        "closed_at",
    )

    def get_readonly_fields(self, request, obj=None):
        parent_fields = list(super().get_readonly_fields(request, obj))
        model_field_names = {
            field.name
            for field in self.model._meta.get_fields()
            if getattr(field, "concrete", False)
        }
        audit_fields = [
            name
            for name in self.audit_field_names
            if name in model_field_names
        ]
        return tuple(dict.fromkeys(parent_fields + audit_fields))


class CAPARootCauseInline(admin.StackedInline):
    model = CAPARootCause
    extra = 0
    show_change_link = True
    classes = ("collapse",)
    fields = (
        "sequence",
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
        "confirmed_by",
        "confirmed_at",
        "created_by",
    )
    autocomplete_fields = (
        "confirmed_by",
        "created_by",
    )


class CAPAActionInline(admin.TabularInline):
    model = CAPAAction
    extra = 0
    show_change_link = True
    classes = ("collapse",)
    fields = (
        "sequence",
        "action_type",
        "title",
        "responsible_position",
        "responsible_employee",
        "target_date",
        "revised_target_date",
        "actual_date",
        "status",
        "completion_percentage",
    )
    autocomplete_fields = (
        "responsible_position",
        "responsible_employee",
    )


class CAPAVerificationInline(admin.TabularInline):
    model = CAPAVerification
    extra = 0
    show_change_link = True
    classes = ("collapse",)
    fields = (
        "review_type",
        "action",
        "review_date",
        "reviewed_by",
        "result",
        "effectiveness_score",
        "follow_up_required",
        "follow_up_date",
        "is_final",
    )
    autocomplete_fields = (
        "action",
        "reviewed_by",
    )


class CAPAAttachmentInline(admin.TabularInline):
    model = CAPAAttachment
    extra = 0
    show_change_link = True
    classes = ("collapse",)
    fields = (
        "attachment_type",
        "title",
        "file",
        "uploaded_by",
        "is_active",
        "uploaded_at",
    )
    readonly_fields = ("uploaded_at",)
    autocomplete_fields = ("uploaded_by",)


class CAPAFollowUpAuditInline(admin.TabularInline):
    model = CAPAFollowUpAudit
    extra = 0
    show_change_link = True
    classes = ("collapse",)
    fields = (
        "due_date",
        "verified_on",
        "verified_by",
        "verified_as_position",
        "result",
    )
    autocomplete_fields = (
        "verified_by",
        "verified_as_position",
    )


class CAPADocumentUpdateInline(admin.TabularInline):
    model = CAPADocumentUpdate
    extra = 0
    show_change_link = True
    classes = ("collapse",)
    fields = (
        "document_type",
        "update_required",
        "document_reference",
        "updated_on",
        "updated_by",
        "attachment",
    )
    autocomplete_fields = ("updated_by",)


class CAPAStatusHistoryInline(admin.TabularInline):
    model = CAPAStatusHistory
    extra = 0
    can_delete = False
    show_change_link = True
    classes = ("collapse",)
    fields = (
        "from_status",
        "to_status",
        "action",
        "comments",
        "changed_by",
        "changed_as_position",
        "changed_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CAPA)
class CAPAAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = (
        "capa_number",
        "short_title",
        "organization_unit",
        "nonconformance_category",
        "status_badge",
        "priority_badge",
        "owner_employee",
        "target_completion_date",
        "overdue_indicator",
        "created_at",
    )
    list_filter = (
        "status",
        "capa_type",
        "nonconformance_category",
        "is_repeated_nonconformance",
        "priority",
        "risk_level",
        "source",
        "category",
        "management_systems",
        "organization_unit",
        "is_active",
        "created_at",
    )
    search_fields = (
        "capa_number",
        "title",
        "nonconformity_number",
        "source_reference",
        "problem_description",
        "auditor_name",
        "auditee_name",
        "clause_reference",
        "document_reference",
        "organization_unit__code",
        "organization_unit__name",
        "owner_employee__employee_code",
        "owner_employee__first_name",
        "owner_employee__last_name",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_select_related = (
        "source",
        "category",
        "organization_unit",
        "owner_position",
        "owner_employee",
        "form_definition",
        "workflow_instance",
        "created_by",
        "updated_by",
    )
    autocomplete_fields = (
        "source",
        "category",
        "organization_unit",
        "originating_organization_unit",
        "owner_position",
        "owner_employee",
        "reported_by_employee",
        "form_definition",
        "workflow_instance",
        "created_by",
        "updated_by",
    )
    filter_horizontal = ("management_systems",)
    readonly_fields = (
        "capa_number",
        "risk_priority_number",
        "risk_level",
        "form_definition_snapshot",
        "submitted_at",
        "closed_at",
        "created_at",
        "updated_at",
    )
    save_on_top = True
    list_per_page = 50
    preserve_filters = True
    inlines = (
        CAPARootCauseInline,
        CAPAActionInline,
        CAPAVerificationInline,
        CAPAFollowUpAuditInline,
        CAPADocumentUpdateInline,
        CAPAAttachmentInline,
        CAPAStatusHistoryInline,
    )
    fieldsets = (
        (
            "CAPA Identification",
            {
                "fields": (
                    ("capa_number", "status"),
                    "title",
                    ("capa_type", "nonconformance_category"),
                    ("nonconformity_number", "is_repeated_nonconformance"),
                    ("source", "category"),
                    "source_reference",
                )
            },
        ),
        (
            "Controlled Form Revision",
            {
                "classes": ("collapse",),
                "fields": (
                    "form_definition",
                    "form_response",
                    "form_definition_snapshot",
                ),
            },
        ),
        (
            "Management System and Organization",
            {
                "fields": (
                    "management_systems",
                    "location_text",
                    ("organization_unit", "originating_organization_unit"),
                    ("owner_position", "owner_employee"),
                    "reported_by_employee",
                )
            },
        ),
        (
            "Audit Information",
            {
                "classes": ("collapse",),
                "fields": (
                    ("audit_date", "section_area_audited"),
                    ("auditor_name", "auditor_signature"),
                    ("auditee_name", "auditee_signature"),
                    ("clause_reference", "document_reference"),
                ),
            },
        ),
        (
            "Non-conformance Details",
            {
                "fields": (
                    ("occurrence_date", "detection_date"),
                    "problem_description",
                    "correction_containment_action",
                    "immediate_correction",
                    "scope",
                    "impact_description",
                )
            },
        ),
        (
            "Impact and Risk",
            {
                "classes": ("collapse",),
                "fields": (
                    (
                        "regulatory_impact",
                        "customer_impact",
                        "safety_impact",
                        "production_impact",
                        "financial_impact",
                    ),
                    ("priority", "risk_level", "risk_priority_number"),
                    ("severity_score", "occurrence_score", "detection_score"),
                ),
            },
        ),
        (
            "Dates and Workflow",
            {
                "fields": (
                    ("target_completion_date", "actual_completion_date"),
                    "workflow_instance",
                    ("submitted_at", "closed_at"),
                )
            },
        ),
        (
            "Record Control",
            {
                "classes": ("collapse",),
                "fields": (
                    ("created_by", "updated_by"),
                    ("created_at", "updated_at"),
                    "is_active",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "organization_unit",
                "owner_employee",
                "source",
                "category",
            )
            .prefetch_related("management_systems")
        )

    @admin.display(description="Title")
    def short_title(self, obj):
        return obj.title if len(obj.title) <= 55 else f"{obj.title[:52]}..."

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            CAPA.Status.DRAFT: "#6c757d",
            CAPA.Status.SUBMITTED: "#0d6efd",
            CAPA.Status.UNDER_REVIEW: "#6f42c1",
            CAPA.Status.ROOT_CAUSE_ANALYSIS: "#fd7e14",
            CAPA.Status.ACTION_PLAN_REVIEW: "#795548",
            CAPA.Status.ACTION_IN_PROGRESS: "#0dcaf0",
            CAPA.Status.VERIFICATION: "#20c997",
            CAPA.Status.EFFECTIVENESS_REVIEW: "#198754",
            CAPA.Status.CLOSED: "#198754",
            CAPA.Status.REJECTED: "#dc3545",
            CAPA.Status.CANCELLED: "#343a40",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;'
            'border-radius:10px;font-size:11px;white-space:nowrap;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Priority", ordering="priority")
    def priority_badge(self, obj):
        colors = {
            CAPA.Priority.LOW: "#198754",
            CAPA.Priority.MEDIUM: "#0d6efd",
            CAPA.Priority.HIGH: "#fd7e14",
            CAPA.Priority.CRITICAL: "#dc3545",
        }
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            colors.get(obj.priority, "#343a40"),
            obj.get_priority_display(),
        )

    @admin.display(description="Overdue", boolean=True)
    def overdue_indicator(self, obj):
        return obj.is_overdue


@admin.register(CAPASource)
class CAPASourceAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = ("code", "name", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "description")
    ordering = ("display_order", "name")


@admin.register(CAPACategory)
class CAPACategoryAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = ("code", "name", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "description")
    ordering = ("display_order", "name")


@admin.register(CAPAManagementSystem)
class CAPAManagementSystemAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = ("code", "name", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "description")
    ordering = ("display_order", "name")


class CAPAFormFieldInline(admin.TabularInline):
    model = CAPAFormField
    extra = 0
    show_change_link = True
    fields = (
        "display_order",
        "code",
        "label",
        "field_type",
        "is_required",
        "is_visible",
        "is_read_only",
        "maps_to_model_field",
    )
    ordering = ("display_order", "id")


@admin.register(CAPAFormSection)
class CAPAFormSectionAdmin(admin.ModelAdmin):
    list_display = (
        "form_definition",
        "display_order",
        "code",
        "title",
        "is_visible",
        "field_count",
    )
    list_filter = ("is_visible", "form_definition__status", "form_definition")
    search_fields = (
        "code",
        "title",
        "title_hi",
        "form_definition__code",
        "form_definition__revision_number",
    )
    autocomplete_fields = ("form_definition",)
    ordering = ("form_definition", "display_order", "id")
    inlines = (CAPAFormFieldInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("form_definition").annotate(
            _field_count=Count("fields")
        )

    @admin.display(description="Fields", ordering="_field_count")
    def field_count(self, obj):
        return obj._field_count


class CAPAFormSectionInline(admin.TabularInline):
    model = CAPAFormSection
    extra = 0
    show_change_link = True
    fields = (
        "display_order",
        "code",
        "title",
        "title_hi",
        "is_visible",
    )
    ordering = ("display_order", "id")


@admin.register(CAPAFormDefinition)
class CAPAFormDefinitionAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "revision_number",
        "revision_date",
        "status_badge",
        "effective_from",
        "effective_to",
        "section_count",
        "published_at",
    )
    list_filter = ("status", "revision_date", "effective_from", "effective_to")
    search_fields = (
        "code",
        "name",
        "revision_number",
        "qms_document_code",
        "qms_revision_reference",
    )
    autocomplete_fields = ("published_by",)
    date_hierarchy = "revision_date"
    ordering = ("code", "-revision_date")
    save_on_top = True
    inlines = (CAPAFormSectionInline,)
    fieldsets = (
        (
            "Controlled Form",
            {
                "fields": (
                    ("code", "revision_number"),
                    "name",
                    ("revision_date", "status"),
                    ("effective_from", "effective_to"),
                )
            },
        ),
        (
            "QMS Document Control Link",
            {
                "fields": (
                    "qms_document_code",
                    "qms_revision_reference",
                    "qms_document_url",
                )
            },
        ),
        (
            "Configuration",
            {
                "classes": ("collapse",),
                "fields": ("configuration",),
            },
        ),
        (
            "Publication",
            {
                "fields": (
                    "published_by",
                    "published_at",
                    ("created_at", "updated_at"),
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _section_count=Count("sections")
        )

    @admin.display(description="Sections", ordering="_section_count")
    def section_count(self, obj):
        return obj._section_count

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            CAPAFormDefinition.Status.DRAFT: "#6c757d",
            CAPAFormDefinition.Status.PUBLISHED: "#198754",
            CAPAFormDefinition.Status.RETIRED: "#343a40",
        }
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;'
            'border-radius:10px;font-size:11px;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )


@admin.register(CAPAFormField)
class CAPAFormFieldAdmin(admin.ModelAdmin):
    list_display = (
        "section",
        "display_order",
        "code",
        "label",
        "field_type",
        "is_required",
        "is_visible",
        "is_read_only",
        "maps_to_model_field",
    )
    list_filter = (
        "field_type",
        "is_required",
        "is_visible",
        "is_read_only",
        "section__form_definition",
    )
    search_fields = (
        "code",
        "label",
        "label_hi",
        "maps_to_model_field",
        "section__code",
        "section__form_definition__code",
    )
    autocomplete_fields = ("section",)
    ordering = ("section", "display_order", "id")
    fieldsets = (
        (
            "Field",
            {
                "fields": (
                    "section",
                    ("code", "field_type"),
                    ("label", "label_hi"),
                    "help_text",
                    "display_order",
                )
            },
        ),
        (
            "Behaviour",
            {
                "fields": (
                    ("is_required", "is_visible", "is_read_only"),
                    "maps_to_model_field",
                )
            },
        ),
        (
            "Dynamic Configuration",
            {
                "classes": ("collapse",),
                "fields": (
                    "choices",
                    "validation_rules",
                    "display_rules",
                ),
            },
        ),
    )


@admin.register(CAPARootCause)
class CAPARootCauseAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = (
        "capa",
        "sequence",
        "analysis_method",
        "cause_type",
        "is_confirmed",
        "confirmed_by",
        "updated_at",
    )
    list_filter = ("analysis_method", "cause_type", "is_confirmed")
    search_fields = (
        "capa__capa_number",
        "cause_statement",
        "why_1",
        "why_2",
        "why_3",
        "why_4",
        "why_5",
    )
    autocomplete_fields = ("capa", "confirmed_by", "created_by")
    ordering = ("capa", "sequence")


@admin.register(CAPAAction)
class CAPAActionAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = (
        "capa",
        "sequence",
        "action_type",
        "short_title",
        "responsible_employee",
        "effective_due_date",
        "status",
        "completion_percentage",
        "overdue_indicator",
    )
    list_filter = (
        "action_type",
        "status",
        "is_mandatory",
        "requires_verification",
        "target_date",
    )
    search_fields = (
        "capa__capa_number",
        "title",
        "description",
        "responsible_employee__employee_code",
        "responsible_employee__first_name",
        "responsible_employee__last_name",
    )
    autocomplete_fields = (
        "capa",
        "root_cause",
        "responsible_position",
        "responsible_employee",
        "assigned_by",
        "revised_date_approved_by",
        "verified_by",
        "created_by",
        "updated_by",
    )
    date_hierarchy = "target_date"
    ordering = ("capa", "sequence")

    @admin.display(description="Title")
    def short_title(self, obj):
        text = obj.title or obj.description or ""
        return text if len(text) <= 45 else f"{text[:42]}..."

    @admin.display(description="Due date", ordering="target_date")
    def effective_due_date(self, obj):
        return obj.effective_target_date

    @admin.display(description="Overdue", boolean=True)
    def overdue_indicator(self, obj):
        return obj.is_overdue


@admin.register(CAPAVerification)
class CAPAVerificationAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = (
        "capa",
        "review_type",
        "action",
        "review_date",
        "reviewed_by",
        "result",
        "effectiveness_score",
        "is_final",
    )
    list_filter = ("review_type", "result", "follow_up_required", "is_final")
    search_fields = (
        "capa__capa_number",
        "observations",
        "recommendation",
        "reviewed_by__username",
    )
    autocomplete_fields = (
        "capa",
        "action",
        "reviewed_by",
        "reviewed_as_position",
    )
    date_hierarchy = "review_date"


@admin.register(CAPAFollowUpAudit)
class CAPAFollowUpAuditAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = (
        "capa",
        "due_date",
        "verified_on",
        "verified_by",
        "result",
    )
    list_filter = ("result", "due_date", "verified_on")
    search_fields = (
        "capa__capa_number",
        "observations",
        "verified_by__username",
    )
    autocomplete_fields = (
        "capa",
        "verified_by",
        "verified_as_position",
    )
    date_hierarchy = "due_date"


@admin.register(CAPADocumentUpdate)
class CAPADocumentUpdateAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = (
        "capa",
        "document_type",
        "update_required",
        "document_reference",
        "updated_on",
        "updated_by",
    )
    list_filter = ("document_type", "update_required", "updated_on")
    search_fields = (
        "capa__capa_number",
        "document_reference",
        "description",
    )
    autocomplete_fields = ("capa", "updated_by")
    date_hierarchy = "updated_on"


@admin.register(CAPAAttachment)
class CAPAAttachmentAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    list_display = (
        "capa",
        "attachment_type",
        "title",
        "original_filename",
        "uploaded_by",
        "uploaded_at",
        "is_active",
    )
    list_filter = ("attachment_type", "is_active", "uploaded_at")
    search_fields = (
        "capa__capa_number",
        "title",
        "description",
        "original_filename",
    )
    autocomplete_fields = (
        "capa",
        "action",
        "root_cause",
        "uploaded_by",
    )
    readonly_fields = ("original_filename", "uploaded_at")
    date_hierarchy = "uploaded_at"


@admin.register(CAPAStatusHistory)
class CAPAStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "capa",
        "from_status",
        "to_status",
        "action",
        "changed_by",
        "changed_at",
    )
    list_filter = ("from_status", "to_status", "action", "changed_at")
    search_fields = (
        "capa__capa_number",
        "comments",
        "changed_by__username",
    )
    autocomplete_fields = (
        "capa",
        "changed_by",
        "changed_as_position",
        "workflow_instance",
    )
    readonly_fields = (
        "capa",
        "from_status",
        "to_status",
        "action",
        "comments",
        "changed_by",
        "changed_as_position",
        "workflow_instance",
        "changed_at",
        "metadata",
    )
    date_hierarchy = "changed_at"
    ordering = ("-changed_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CAPANumberSequence)
class CAPANumberSequenceAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "last_number", "updated_at")
    list_filter = ("year", "month")
    ordering = ("-year", "-month")
    readonly_fields = (
        "year",
        "month",
        "last_number",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and obj is not None

    def has_delete_permission(self, request, obj=None):
        return False
