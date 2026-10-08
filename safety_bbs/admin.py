from django.contrib import admin

from .models import BBSObservation


# =============================================================================
# BBS OBSERVATION ADMIN
# =============================================================================


@admin.register(BBSObservation)
class BBSObservationAdmin(admin.ModelAdmin):
    """
    Django Admin configuration for BBS observations.

    BBS observations are created through the public
    Safety-BBS form.

    Admin is primarily used for:
    - Monitoring submissions
    - Searching observations
    - Reviewing At-Risk observations
    - Checking daily submissions
    - Investigating submitted data
    """

    # =========================================================================
    # LIST DISPLAY
    # =========================================================================

    list_display = (
        "observation_date",
        "observation_time",
        "card_no",
        "employee_name",
        "shift",
        "area",
        "behaviour_type",
        "at_risk_display",
        "submitted_at",
    )

    # =========================================================================
    # FILTERS
    # =========================================================================

    list_filter = (
        "shift",
        "behaviour_type",
        "ppe_status",
        "guarding_loto_status",
        "ergonomics_status",
        "tools_equipment_status",
        "housekeeping_status",
        "permit_procedure_status",
        "observation_date",
    )

    # =========================================================================
    # SEARCH
    # =========================================================================

    search_fields = (
        "card_no",
        "employee_name",
        "area",
        "observer_name",
        "activator",
        "behaviour_description",
        "feedback",
        "root_cause_other",
        "corrective_action",
        "observer_sign",
        "supervisor_sign",
    )

    # =========================================================================
    # ORDERING
    # =========================================================================

    ordering = (
        "-observation_date",
        "-submitted_at",
    )

    date_hierarchy = "observation_date"

    # =========================================================================
    # READ ONLY FIELDS
    # =========================================================================

    readonly_fields = (
        "at_risk_summary",
        "ip_address",
        "user_agent",
        "submitted_at",
        "updated_at",
    )

    # =========================================================================
    # FIELDSETS
    # =========================================================================

    fieldsets = (

        (
            "Employee / Submitter",
            {
                "fields": (
                    "employee_name",
                    "card_no",
                ),
            },
        ),

        (
            "Observation Information",
            {
                "fields": (
                    "observation_date",
                    "observation_time",
                    "shift",
                    "area",
                    "observer_name",
                ),
            },
        ),

        (
            "A. Activator",
            {
                "fields": (
                    "activator",
                ),
            },
        ),

        (
            "B. Behaviour",
            {
                "fields": (
                    "behaviour_type",
                    "behaviour_categories",
                    "behaviour_description",
                ),
            },
        ),

        (
            "C. Consequence / Feedback",
            {
                "fields": (
                    "consequences",
                    "feedback",
                ),
            },
        ),

        (
            "Critical Behaviour Checklist",
            {
                "fields": (
                    "ppe_status",
                    "guarding_loto_status",
                    "ergonomics_status",
                    "tools_equipment_status",
                    "housekeeping_status",
                    "permit_procedure_status",
                    "at_risk_summary",
                ),
            },
        ),

        (
            "At-Risk Root Cause",
            {
                "fields": (
                    "root_causes",
                    "root_cause_other",
                    "corrective_action",
                ),
            },
        ),

        (
            "Acknowledgement / Signature",
            {
                "fields": (
                    "observer_sign",
                    "supervisor_sign",
                ),
            },
        ),

        (
            "Submission Information",
            {
                "fields": (
                    "ip_address",
                    "user_agent",
                    "submitted_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

    )

    # =========================================================================
    # AT-RISK LIST COLUMN
    # =========================================================================

    @admin.display(
        boolean=True,
        description="At-Risk?",
    )
    def at_risk_display(self, obj):
        """
        Overall At-Risk status.

        Uses the model's is_at_risk property, therefore an observation
        is considered At-Risk when either:

        - behaviour_type is AT_RISK
        - any critical behaviour checklist item is AT_RISK
        """

        return obj.is_at_risk

    # =========================================================================
    # AT-RISK SUMMARY
    # =========================================================================

    @admin.display(
        description="At-Risk Summary"
    )
    def at_risk_summary(self, obj):
        """
        Human-readable summary of all At-Risk conditions.
        """

        if not obj:
            return "-"

        items = []

        # Overall behaviour
        if (
            obj.behaviour_type
            == BBSObservation.BehaviourType.AT_RISK
        ):
            items.append(
                "Overall Behaviour"
            )

        # PPE
        if (
            obj.ppe_status
            == BBSObservation.ChecklistStatus.AT_RISK
        ):
            items.append(
                "PPE"
            )

        # Guarding / LOTO
        if (
            obj.guarding_loto_status
            == BBSObservation.ChecklistStatus.AT_RISK
        ):
            items.append(
                "Guarding / LOTO"
            )

        # Ergonomics
        if (
            obj.ergonomics_status
            == BBSObservation.ChecklistStatus.AT_RISK
        ):
            items.append(
                "Position / Ergonomics"
            )

        # Tools / Equipment
        if (
            obj.tools_equipment_status
            == BBSObservation.ChecklistStatus.AT_RISK
        ):
            items.append(
                "Tools / Equipment"
            )

        # Housekeeping
        if (
            obj.housekeeping_status
            == BBSObservation.ChecklistStatus.AT_RISK
        ):
            items.append(
                "Housekeeping"
            )

        # Permit / Procedure
        if (
            obj.permit_procedure_status
            == BBSObservation.ChecklistStatus.AT_RISK
        ):
            items.append(
                "Permit / Procedure"
            )

        if not items:
            return "No At-Risk condition identified"

        return ", ".join(items)

    # =========================================================================
    # ADMIN CREATION
    # =========================================================================

    def has_add_permission(
        self,
        request,
    ):
        """
        BBS records should normally originate from
        the public Safety-BBS form.
        """

        return False