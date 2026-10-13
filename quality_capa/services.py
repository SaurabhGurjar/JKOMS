# quality_capa/services.py
from __future__ import annotations

import copy
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from usermanagement.models import (
    AuditLog,
    WorkflowAction,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowTransition,
)
from usermanagement.services import (
    get_applicable_role_assignments,
    get_primary_position,
    get_user_positions,
    user_has_jkoms_permission,
)

from .models import (
    CAPA,
    CAPAAction,
    CAPAFormDefinition,
    CAPAFormField,
    CAPAStatusHistory,
    CAPAVerification,
)


CAPA_ENTITY_TYPE = "quality_capa.CAPA"
CAPA_MODULE_CODE = "QUALITY_CAPA"
DEFAULT_FORM_CODE = "L/SYS/GN/FR.01"
DEFAULT_WORKFLOW_CODE = "QUALITY_CAPA"


class CAPAServiceError(Exception):
    """Base exception for CAPA service failures."""


class CAPAConfigurationError(CAPAServiceError):
    """Raised when required CAPA configuration is unavailable."""


class CAPATransitionError(CAPAServiceError):
    """Raised when a requested CAPA lifecycle transition is invalid."""


PERMISSION_CODES = {
    "view": "quality.capa.view",
    "create": "quality.capa.create",
    "edit": "quality.capa.edit",
    "submit": "quality.capa.submit",
    "review": "quality.capa.review",
    "approve": "quality.capa.approve",
    "assign_action": "quality.capa.assign_action",
    "update_action": "quality.capa.update_action",
    "verify": "quality.capa.verify",
    "effectiveness_review": "quality.capa.effectiveness_review",
    "close": "quality.capa.close",
    "cancel": "quality.capa.cancel",
    "export": "quality.capa.export",
    "form_publish": "quality.capa.form.publish",
    "action_override": "quality.capa.action.override",
}


ALLOWED_STATUS_TRANSITIONS = {
    CAPA.Status.DRAFT: {
        CAPA.Status.SUBMITTED,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.SUBMITTED: {
        CAPA.Status.UNDER_REVIEW,
        CAPA.Status.REJECTED,
        CAPA.Status.DRAFT,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.UNDER_REVIEW: {
        CAPA.Status.ROOT_CAUSE_ANALYSIS,
        CAPA.Status.REJECTED,
        CAPA.Status.DRAFT,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.ROOT_CAUSE_ANALYSIS: {
        CAPA.Status.ACTION_PLAN_REVIEW,
        CAPA.Status.UNDER_REVIEW,
        CAPA.Status.REJECTED,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.ACTION_PLAN_REVIEW: {
        CAPA.Status.ACTION_IN_PROGRESS,
        CAPA.Status.ROOT_CAUSE_ANALYSIS,
        CAPA.Status.REJECTED,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.ACTION_IN_PROGRESS: {
        CAPA.Status.VERIFICATION,
        CAPA.Status.ACTION_PLAN_REVIEW,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.VERIFICATION: {
        CAPA.Status.EFFECTIVENESS_REVIEW,
        CAPA.Status.ACTION_IN_PROGRESS,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.EFFECTIVENESS_REVIEW: {
        CAPA.Status.CLOSED,
        CAPA.Status.ACTION_IN_PROGRESS,
        CAPA.Status.VERIFICATION,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.CLOSED: set(),
    CAPA.Status.REJECTED: {
        CAPA.Status.DRAFT,
        CAPA.Status.CANCELLED,
    },
    CAPA.Status.CANCELLED: set(),
}


TRANSITION_PERMISSIONS = {
    CAPA.Status.SUBMITTED: PERMISSION_CODES["submit"],
    CAPA.Status.UNDER_REVIEW: PERMISSION_CODES["review"],
    CAPA.Status.ROOT_CAUSE_ANALYSIS: PERMISSION_CODES["review"],
    CAPA.Status.ACTION_PLAN_REVIEW: PERMISSION_CODES["review"],
    CAPA.Status.ACTION_IN_PROGRESS: PERMISSION_CODES["approve"],
    CAPA.Status.VERIFICATION: PERMISSION_CODES["verify"],
    CAPA.Status.EFFECTIVENESS_REVIEW: PERMISSION_CODES["effectiveness_review"],
    CAPA.Status.CLOSED: PERMISSION_CODES["close"],
    CAPA.Status.REJECTED: PERMISSION_CODES["review"],
    CAPA.Status.CANCELLED: PERMISSION_CODES["cancel"],
    CAPA.Status.DRAFT: PERMISSION_CODES["edit"],
}


TRANSITION_ACTIONS = {
    CAPA.Status.SUBMITTED: "SUBMIT",
    CAPA.Status.UNDER_REVIEW: "START_REVIEW",
    CAPA.Status.ROOT_CAUSE_ANALYSIS: "START_ROOT_CAUSE_ANALYSIS",
    CAPA.Status.ACTION_PLAN_REVIEW: "SUBMIT_ACTION_PLAN",
    CAPA.Status.ACTION_IN_PROGRESS: "APPROVE_ACTION_PLAN",
    CAPA.Status.VERIFICATION: "SEND_FOR_VERIFICATION",
    CAPA.Status.EFFECTIVENESS_REVIEW: "START_EFFECTIVENESS_REVIEW",
    CAPA.Status.CLOSED: "CLOSE",
    CAPA.Status.REJECTED: "REJECT",
    CAPA.Status.CANCELLED: "CANCEL",
    CAPA.Status.DRAFT: "RETURN_TO_DRAFT",
}


def _require_authenticated_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication is required.")
    if not user.is_active:
        raise PermissionDenied("Inactive users cannot perform CAPA operations.")


def _require_active_workforce_user(user):
    _require_authenticated_user(user)
    employee = getattr(user, "employee", None)
    if employee is None:
        return
    if not employee.is_active:
        raise PermissionDenied("The linked employee record is inactive.")
    if employee.employment_status != employee.EmploymentStatus.ACTIVE:
        raise PermissionDenied("The linked employee is not in active employment status.")


def _require_permission(user, permission_code, organization_unit):
    _require_active_workforce_user(user)
    if not user_has_jkoms_permission(
        user=user,
        permission_code=permission_code,
        organization_unit=organization_unit,
    ):
        raise PermissionDenied(
            f"You do not have permission {permission_code!r} for this organization unit."
        )


def _client_ip(request):
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR")


def _user_agent(request):
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:2000]


def _json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "pk"):
        return value.pk
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _model_snapshot(instance, field_names):
    return {
        field_name: _json_safe(getattr(instance, field_name, None))
        for field_name in field_names
    }


def _write_audit_log(
    *,
    user,
    entity_type,
    entity_id,
    action,
    old_values=None,
    new_values=None,
    request=None,
):
    employee = getattr(user, "employee", None) if user else None
    return AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        employee=employee,
        module_code=CAPA_MODULE_CODE,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        old_values=_json_safe(old_values or {}),
        new_values=_json_safe(new_values or {}),
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


# =============================================================================
# DYNAMIC FORM DEFINITIONS
# =============================================================================


def get_published_form_definition(form_code=DEFAULT_FORM_CODE, reference_date=None):
    reference_date = reference_date or timezone.localdate()
    return (
        CAPAFormDefinition.objects
        .filter(
            code=form_code,
            status=CAPAFormDefinition.Status.PUBLISHED,
        )
        .filter(
            Q(effective_from__isnull=True) | Q(effective_from__lte=reference_date),
            Q(effective_to__isnull=True) | Q(effective_to__gte=reference_date),
        )
        .prefetch_related("sections__fields")
        .order_by("-revision_date", "-pk")
        .first()
    )


def build_form_definition_snapshot(form_definition):
    if form_definition is None:
        return {}

    sections = []
    for section in form_definition.sections.order_by("display_order", "id"):
        fields = []
        for field in section.fields.order_by("display_order", "id"):
            fields.append(
                {
                    "id": field.pk,
                    "code": field.code,
                    "label": field.label,
                    "label_hi": field.label_hi,
                    "help_text": field.help_text,
                    "field_type": field.field_type,
                    "display_order": field.display_order,
                    "is_required": field.is_required,
                    "is_visible": field.is_visible,
                    "is_read_only": field.is_read_only,
                    "choices": copy.deepcopy(field.choices),
                    "validation_rules": copy.deepcopy(field.validation_rules),
                    "display_rules": copy.deepcopy(field.display_rules),
                    "maps_to_model_field": field.maps_to_model_field,
                }
            )

        sections.append(
            {
                "id": section.pk,
                "code": section.code,
                "title": section.title,
                "title_hi": section.title_hi,
                "description": section.description,
                "display_order": section.display_order,
                "is_visible": section.is_visible,
                "configuration": copy.deepcopy(section.configuration),
                "fields": fields,
            }
        )

    return {
        "schema": "JKOMS.CAPA.FORM_DEFINITION.V1",
        "definition_id": form_definition.pk,
        "code": form_definition.code,
        "name": form_definition.name,
        "revision_number": form_definition.revision_number,
        "revision_date": form_definition.revision_date.isoformat(),
        "effective_from": (
            form_definition.effective_from.isoformat()
            if form_definition.effective_from
            else None
        ),
        "effective_to": (
            form_definition.effective_to.isoformat()
            if form_definition.effective_to
            else None
        ),
        "qms_document_code": form_definition.qms_document_code,
        "qms_revision_reference": form_definition.qms_revision_reference,
        "configuration": copy.deepcopy(form_definition.configuration),
        "sections": sections,
    }


@transaction.atomic
def publish_form_definition(
    *,
    form_definition_id,
    user,
    effective_from=None,
    request=None,
):
    _require_permission(user, PERMISSION_CODES["form_publish"], None)

    definition = (
        CAPAFormDefinition.objects
        .select_for_update()
        .prefetch_related("sections__fields")
        .get(pk=form_definition_id)
    )

    if definition.status == CAPAFormDefinition.Status.RETIRED:
        raise ValidationError("A retired form definition cannot be published.")
    if definition.status == CAPAFormDefinition.Status.PUBLISHED:
        raise ValidationError("This form definition is already published.")
    if not definition.sections.exists():
        raise ValidationError("A form definition must contain at least one section.")
    if not CAPAFormField.objects.filter(
        section__form_definition=definition,
        is_visible=True,
    ).exists():
        raise ValidationError("A published form must contain at least one visible field.")

    now = timezone.now()
    effective_from = effective_from or timezone.localdate()

    current_definitions = (
        CAPAFormDefinition.objects
        .select_for_update()
        .filter(
            code=definition.code,
            status=CAPAFormDefinition.Status.PUBLISHED,
        )
        .exclude(pk=definition.pk)
    )

    for current in current_definitions:
        current.status = CAPAFormDefinition.Status.RETIRED
        if current.effective_from and effective_from <= current.effective_from:
            raise ValidationError(
                {
                    "effective_from": (
                        "The new revision must become effective after "
                        "the current revision."
                    )
                }
            )
        previous_day = effective_from - timedelta(days=1)
        current.effective_to = previous_day
        current.save(update_fields=["status", "effective_to", "updated_at"])

    definition.status = CAPAFormDefinition.Status.PUBLISHED
    definition.effective_from = definition.effective_from or effective_from
    definition.effective_to = None
    definition.published_by = user
    definition.published_at = now
    definition.full_clean()
    definition.save(
        update_fields=[
            "status",
            "effective_from",
            "effective_to",
            "published_by",
            "published_at",
            "updated_at",
        ]
    )

    _write_audit_log(
        user=user,
        entity_type="CAPA_FORM_DEFINITION",
        entity_id=definition.pk,
        action="PUBLISH",
        new_values=build_form_definition_snapshot(definition),
        request=request,
    )
    return definition


def _field_definitions_from_snapshot(snapshot):
    result = {}
    for section in snapshot.get("sections", []):
        for field in section.get("fields", []):
            if field.get("code"):
                result[field["code"]] = field
    return result


def _choice_codes(field_definition):
    values = set()
    for choice in field_definition.get("choices") or []:
        if isinstance(choice, dict):
            code = choice.get("code", choice.get("value"))
        else:
            code = choice
        if code is not None:
            values.add(str(code))
    return values


def _is_empty(value):
    return value is None or value == "" or value == [] or value == {}


def _validate_dynamic_value(field_definition, value):
    field_type = field_definition.get("field_type")
    rules = field_definition.get("validation_rules") or {}
    code = field_definition.get("code", "field")

    if _is_empty(value):
        return value

    try:
        if field_type in {CAPAFormField.FieldType.TEXT, CAPAFormField.FieldType.TEXTAREA}:
            if not isinstance(value, str):
                raise ValidationError("Value must be text.")
            minimum = rules.get("min_length")
            maximum = rules.get("max_length")
            pattern = rules.get("regex")
            if minimum is not None and len(value) < int(minimum):
                raise ValidationError(f"Minimum length is {minimum}.")
            if maximum is not None and len(value) > int(maximum):
                raise ValidationError(f"Maximum length is {maximum}.")
            if pattern and not re.fullmatch(pattern, value):
                raise ValidationError("Value does not match the configured pattern.")
            return value

        if field_type == CAPAFormField.FieldType.INTEGER:
            converted = int(value)
        elif field_type == CAPAFormField.FieldType.DECIMAL:
            converted = Decimal(str(value))
        elif field_type == CAPAFormField.FieldType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if str(value).lower() in {"true", "1", "yes", "on"}:
                return True
            if str(value).lower() in {"false", "0", "no", "off"}:
                return False
            raise ValidationError("Value must be true or false.")
        elif field_type == CAPAFormField.FieldType.DATE:
            converted = value if isinstance(value, date) else parse_date(str(value))
            if converted is None:
                raise ValidationError("Enter a valid date.")
            return converted.isoformat()
        elif field_type == CAPAFormField.FieldType.DATETIME:
            converted = value if isinstance(value, datetime) else parse_datetime(str(value))
            if converted is None:
                raise ValidationError("Enter a valid date and time.")
            return converted.isoformat()
        elif field_type == CAPAFormField.FieldType.CHOICE:
            allowed = _choice_codes(field_definition)
            if allowed and str(value) not in allowed:
                raise ValidationError("Select a valid choice.")
            return value
        elif field_type == CAPAFormField.FieldType.MULTI_CHOICE:
            if not isinstance(value, (list, tuple)):
                raise ValidationError("Select one or more valid choices.")
            allowed = _choice_codes(field_definition)
            invalid = {str(item) for item in value} - allowed if allowed else set()
            if invalid:
                raise ValidationError(f"Invalid choices: {', '.join(sorted(invalid))}.")
            return list(value)
        elif field_type == CAPAFormField.FieldType.FILE:
            try:
                return int(value)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    "Dynamic file fields must contain a valid CAPAAttachment ID."
                ) from exc
        elif field_type in {
            CAPAFormField.FieldType.USER,
            CAPAFormField.FieldType.EMPLOYEE,
            CAPAFormField.FieldType.POSITION,
            CAPAFormField.FieldType.ORGANIZATION_UNIT,
        }:
            return int(value)
        else:
            return value

        minimum = rules.get("min")
        maximum = rules.get("max")
        if minimum is not None and converted < Decimal(str(minimum)):
            raise ValidationError(f"Minimum value is {minimum}.")
        if maximum is not None and converted > Decimal(str(maximum)):
            raise ValidationError(f"Maximum value is {maximum}.")
        return _json_safe(converted)
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValidationError("Enter a valid value.") from exc
    except ValidationError as exc:
        raise ValidationError({code: exc.messages}) from exc


def validate_dynamic_form_response(snapshot, response, enforce_required=False):
    response = response or {}
    if not isinstance(response, dict):
        raise ValidationError({"form_response": "Dynamic form response must be an object."})

    field_definitions = _field_definitions_from_snapshot(snapshot or {})
    unknown_fields = set(response) - set(field_definitions)
    if unknown_fields:
        raise ValidationError(
            {
                "form_response": (
                    "Unknown dynamic fields: " + ", ".join(sorted(unknown_fields))
                )
            }
        )

    errors = {}
    cleaned = {}
    for code, field_definition in field_definitions.items():
        if not field_definition.get("is_visible", True):
            continue
        value = response.get(code)
        if enforce_required and field_definition.get("is_required") and _is_empty(value):
            errors[code] = "This field is required."
            continue
        if code in response:
            try:
                cleaned[code] = _validate_dynamic_value(field_definition, value)
            except ValidationError as exc:
                if hasattr(exc, "error_dict"):
                    errors[code] = [
                        message
                        for error in exc.error_dict.get(code, [])
                        for message in error.messages
                    ]
                else:
                    errors[code] = exc.messages

    if errors:
        raise ValidationError(errors)
    return cleaned


# =============================================================================
# CAPA CREATE AND UPDATE
# =============================================================================


DRAFT_EDITABLE_FIELDS = {
    "title",
    "capa_type",
    "source",
    "category",
    "originating_organization_unit",
    "owner_position",
    "owner_employee",
    "reported_by_employee",
    "location_text",
    "nonconformity_number",
    "nonconformance_category",
    "is_repeated_nonconformance",
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
    "immediate_correction",
    "correction_containment_action",
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
}


CAPA_AUDIT_FIELDS = (
    "capa_number",
    "title",
    "capa_type",
    "status",
    "form_definition_id",
    "location_text",
    "nonconformity_number",
    "nonconformance_category",
    "is_repeated_nonconformance",
    "source_id",
    "category_id",
    "organization_unit_id",
    "originating_organization_unit_id",
    "owner_position_id",
    "owner_employee_id",
    "reported_by_employee_id",
    "auditor_name",
    "auditee_name",
    "audit_date",
    "section_area_audited",
    "clause_reference",
    "document_reference",
    "occurrence_date",
    "detection_date",
    "target_completion_date",
    "actual_completion_date",
    "problem_description",
    "immediate_correction",
    "correction_containment_action",
    "scope",
    "impact_description",
    "priority",
    "severity_score",
    "occurrence_score",
    "detection_score",
    "risk_priority_number",
    "risk_level",
    "source_reference",
    "is_active",
)


def _capa_audit_snapshot(capa):
    snapshot = _model_snapshot(capa, CAPA_AUDIT_FIELDS)
    snapshot["form_response"] = copy.deepcopy(capa.form_response)
    if capa.pk:
        snapshot["management_system_ids"] = list(
            capa.management_systems.order_by("pk").values_list("pk", flat=True)
        )
    else:
        snapshot["management_system_ids"] = []
    return snapshot


@transaction.atomic
def create_capa(
    *,
    user,
    organization_unit,
    source,
    category,
    title,
    problem_description,
    form_definition=None,
    form_code=DEFAULT_FORM_CODE,
    form_response=None,
    management_systems=None,
    request=None,
    **optional_fields,
):
    _require_permission(user, PERMISSION_CODES["create"], organization_unit)

    if form_definition is None:
        form_definition = get_published_form_definition(form_code=form_code)

    snapshot = build_form_definition_snapshot(form_definition)
    cleaned_response = validate_dynamic_form_response(
        snapshot,
        form_response or {},
        enforce_required=False,
    )

    allowed_fields = {
        field.name
        for field in CAPA._meta.concrete_fields
        if field.name not in {
            "id",
            "capa_number",
            "status",
            "workflow_instance",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "risk_priority_number",
            "risk_level",
            "form_definition_snapshot",
            "form_response",
        }
    }
    invalid_fields = set(optional_fields) - allowed_fields
    if invalid_fields:
        raise ValidationError(
            "Unsupported CAPA fields: " + ", ".join(sorted(invalid_fields))
        )

    capa = CAPA(
        title=title,
        problem_description=problem_description,
        organization_unit=organization_unit,
        source=source,
        category=category,
        form_definition=form_definition,
        form_definition_snapshot=snapshot,
        form_response=cleaned_response,
        created_by=user,
        updated_by=user,
        status=CAPA.Status.DRAFT,
        **optional_fields,
    )
    capa.full_clean(exclude=["capa_number"])
    capa.save()

    if management_systems:
        capa.management_systems.set(management_systems)

    CAPAStatusHistory.objects.create(
        capa=capa,
        from_status=None,
        to_status=CAPA.Status.DRAFT,
        action="CREATE",
        comments="CAPA created as draft.",
        changed_by=user,
        changed_as_position=get_primary_position(user),
        metadata={
            "form_definition_id": form_definition.pk if form_definition else None,
            "form_revision": form_definition.revision_number if form_definition else None,
        },
    )

    _write_audit_log(
        user=user,
        entity_type="CAPA",
        entity_id=capa.pk,
        action="CREATE",
        new_values=_capa_audit_snapshot(capa),
        request=request,
    )
    return capa


@transaction.atomic
def update_capa_draft(
    *,
    capa_id,
    user,
    changes,
    form_response=None,
    management_systems=None,
    request=None,
):
    capa = CAPA.objects.select_for_update().get(pk=capa_id)
    _require_permission(user, PERMISSION_CODES["edit"], capa.organization_unit)

    if capa.status != CAPA.Status.DRAFT:
        raise CAPATransitionError("Only a draft CAPA can be edited through this operation.")

    invalid_fields = set(changes) - DRAFT_EDITABLE_FIELDS
    if invalid_fields:
        raise ValidationError(
            "Unsupported or immutable fields: " + ", ".join(sorted(invalid_fields))
        )

    old_values = _capa_audit_snapshot(capa)
    for field_name, value in changes.items():
        setattr(capa, field_name, value)

    if form_response is not None:
        capa.form_response = validate_dynamic_form_response(
            capa.form_definition_snapshot,
            form_response,
            enforce_required=False,
        )

    capa.updated_by = user
    capa.full_clean()
    capa.save()

    if management_systems is not None:
        capa.management_systems.set(management_systems)

    _write_audit_log(
        user=user,
        entity_type="CAPA",
        entity_id=capa.pk,
        action="UPDATE_DRAFT",
        old_values=old_values,
        new_values=_capa_audit_snapshot(capa),
        request=request,
    )
    return capa


@transaction.atomic
def reassign_capa_organization(
    *,
    capa_id,
    new_organization_unit,
    user,
    comments,
    request=None,
):
    if not comments or not comments.strip():
        raise ValidationError({"comments": "Reassignment comments are required."})
    capa = CAPA.objects.select_for_update().get(pk=capa_id)
    if capa.status != CAPA.Status.DRAFT:
        raise CAPATransitionError("Only a draft CAPA can be reassigned to another organization.")
    _require_permission(user, PERMISSION_CODES["edit"], capa.organization_unit)
    _require_permission(user, PERMISSION_CODES["create"], new_organization_unit)
    old_values = _capa_audit_snapshot(capa)
    capa.organization_unit = new_organization_unit
    capa.updated_by = user
    capa.full_clean()
    capa.save(update_fields=["organization_unit", "updated_by", "updated_at"])
    _write_audit_log(
        user=user,
        entity_type="CAPA",
        entity_id=capa.pk,
        action="REASSIGN_ORGANIZATION",
        old_values=old_values,
        new_values={**_capa_audit_snapshot(capa), "comments": comments},
        request=request,
    )
    return capa


# =============================================================================
# WORKFLOW AND LIFECYCLE
# =============================================================================


def _get_active_workflow_definition(workflow_code, reference_date=None):
    reference_date = reference_date or timezone.localdate()
    return (
        WorkflowDefinition.objects
        .filter(
            code=workflow_code,
            entity_type=CAPA_ENTITY_TYPE,
            status=WorkflowDefinition.Status.ACTIVE,
        )
        .filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=reference_date),
            Q(valid_to__isnull=True) | Q(valid_to__gte=reference_date),
        )
        .select_related("module")
        .order_by("-version")
        .first()
    )


def _get_start_step(workflow_definition):
    return (
        workflow_definition.steps
        .filter(step_type=WorkflowStep.StepType.START)
        .order_by("sequence", "pk")
        .first()
        or workflow_definition.steps.order_by("sequence", "pk").first()
    )


@transaction.atomic
def _start_capa_workflow(
    *,
    capa,
    user,
    workflow_code=DEFAULT_WORKFLOW_CODE,
):
    _require_permission(user, PERMISSION_CODES["submit"], capa.organization_unit)
    if capa.workflow_instance_id:
        return capa.workflow_instance

    workflow_definition = _get_active_workflow_definition(workflow_code)
    if workflow_definition is None:
        raise CAPAConfigurationError(
            f"No active workflow definition {workflow_code!r} exists for {CAPA_ENTITY_TYPE}."
        )

    start_step = _get_start_step(workflow_definition)
    if start_step is None:
        raise CAPAConfigurationError("The active CAPA workflow has no steps.")

    instance = WorkflowInstance.objects.create(
        workflow_definition=workflow_definition,
        business_object_type=CAPA_ENTITY_TYPE,
        business_object_id=capa.pk,
        organization_unit=capa.organization_unit,
        current_step=start_step,
        status=WorkflowInstance.Status.IN_PROGRESS,
        started_by=user,
    )
    capa.workflow_instance = instance
    capa.save(update_fields=["workflow_instance", "updated_at"])
    return instance


def _validate_transition(capa, to_status):
    allowed = ALLOWED_STATUS_TRANSITIONS.get(capa.status, set())
    if to_status not in allowed:
        raise CAPATransitionError(
            f"CAPA cannot move from {capa.get_status_display()} to "
            f"{CAPA.Status(to_status).label}."
        )


def _validate_stage_requirements(capa, to_status):
    errors = {}

    if to_status == CAPA.Status.SUBMITTED:
        if not capa.title.strip():
            errors["title"] = "Title is required before submission."
        if not capa.problem_description.strip():
            errors["problem_description"] = "Problem description is required before submission."
        validate_dynamic_form_response(
            capa.form_definition_snapshot,
            capa.form_response,
            enforce_required=True,
        )

    elif to_status == CAPA.Status.ACTION_PLAN_REVIEW:
        if not capa.root_causes.exists():
            errors["root_causes"] = "At least one root-cause record is required."

    elif to_status == CAPA.Status.ACTION_IN_PROGRESS:
        if not capa.actions.exists():
            errors["actions"] = "At least one CAPA action is required."

    elif to_status == CAPA.Status.VERIFICATION:
        incomplete = capa.actions.filter(is_mandatory=True).exclude(
            status__in=[CAPAAction.Status.COMPLETED, CAPAAction.Status.VERIFIED]
        )
        if incomplete.exists():
            errors["actions"] = "All mandatory actions must be completed before verification."

    elif to_status == CAPA.Status.CLOSED:
        if capa.actions.filter(is_mandatory=True).exclude(
            status__in=[CAPAAction.Status.COMPLETED, CAPAAction.Status.VERIFIED]
        ).exists():
            errors["actions"] = "All mandatory actions must be completed before closure."
        acceptable_results = {
            CAPAVerification.Result.SATISFACTORY,
            CAPAVerification.Result.EFFECTIVE,
        }
        if not capa.verifications.filter(
            is_final=True,
            result__in=acceptable_results,
        ).exists():
            errors["verifications"] = (
                "A satisfactory or effective final verification is required before closure."
            )

    if errors:
        raise ValidationError(errors)


def _require_step_authority(user, instance, capa):
    step = instance.current_step
    if step is None:
        raise CAPATransitionError("The workflow instance has no current step.")
    if step.required_permission_id and not user_has_jkoms_permission(
        user=user,
        permission_code=step.required_permission.code,
        organization_unit=capa.organization_unit,
    ):
        raise PermissionDenied("You do not hold the permission required by the current workflow step.")
    if step.required_role_id and not user.is_superuser:
        applicable_assignments = get_applicable_role_assignments(
            user=user,
            organization_unit=capa.organization_unit,
            module=instance.workflow_definition.module,
        )
        if not any(
            assignment.role_id == step.required_role_id
            for assignment in applicable_assignments
        ):
            raise PermissionDenied(
                "You do not hold the scoped role required by the current workflow step."
            )


def _perform_workflow_transition(*, instance, user, capa, action, comments):
    instance = (
        WorkflowInstance.objects
        .select_for_update()
        .select_related(
            "workflow_definition",
            "current_step__required_permission",
            "current_step__required_role",
        )
        .get(pk=instance.pk)
    )
    _require_step_authority(user, instance, capa)
    transitions = list(
        WorkflowTransition.objects
        .select_related("from_step", "to_step")
        .filter(
            workflow_definition=instance.workflow_definition,
            from_step=instance.current_step,
            action=action,
            is_active=True,
        )
        .order_by("pk")[:2]
    )
    if not transitions:
        raise CAPATransitionError(
            f"No active workflow transition exists for action {action!r} "
            f"from step {instance.current_step.code!r}."
        )
    if len(transitions) > 1:
        raise CAPAConfigurationError(
            f"Multiple workflow transitions are configured for action {action!r} "
            f"from step {instance.current_step.code!r}. "
            "Conditional transition resolution is not configured."
        )
    transition = transitions[0]
    workflow_action = WorkflowAction.objects.create(
        workflow_instance=instance,
        workflow_step=instance.current_step,
        action=action,
        acted_by=user,
        acted_as_position=get_primary_position(user),
        comments=comments,
    )
    instance.current_step = transition.to_step
    if transition.to_step is None or transition.to_step.step_type == WorkflowStep.StepType.END:
        instance.status = WorkflowInstance.Status.COMPLETED
        instance.completed_at = timezone.now()
    else:
        instance.status = WorkflowInstance.Status.IN_PROGRESS
        instance.completed_at = None
    instance.save(update_fields=["current_step", "status", "completed_at"])
    return workflow_action, instance


@transaction.atomic
def transition_capa(
    *,
    capa_id,
    user,
    to_status,
    comments="",
    action=None,
    workflow_code=DEFAULT_WORKFLOW_CODE,
    request=None,
):
    capa = (
        CAPA.objects
        .select_for_update()
        .select_related("organization_unit", "workflow_instance__current_step")
        .get(pk=capa_id)
    )

    _validate_transition(capa, to_status)
    permission_code = TRANSITION_PERMISSIONS[to_status]
    _require_permission(user, permission_code, capa.organization_unit)
    _validate_stage_requirements(capa, to_status)

    old_status = capa.status
    old_values = _capa_audit_snapshot(capa)
    transition_action = action or TRANSITION_ACTIONS[to_status]

    if to_status == CAPA.Status.SUBMITTED and not capa.workflow_instance_id:
        _start_capa_workflow(capa=capa, user=user, workflow_code=workflow_code)
        capa.refresh_from_db(fields=["workflow_instance"])

    capa.status = to_status
    capa.updated_by = user
    update_fields = ["status", "updated_by", "updated_at"]

    now = timezone.now()
    if to_status == CAPA.Status.SUBMITTED and capa.submitted_at is None:
        capa.submitted_at = now
        update_fields.append("submitted_at")
    if to_status == CAPA.Status.CLOSED:
        capa.closed_at = now
        capa.actual_completion_date = capa.actual_completion_date or timezone.localdate()
        update_fields.extend(["closed_at", "actual_completion_date"])

    capa.save(update_fields=update_fields)

    workflow_action = None
    if capa.workflow_instance_id:
        workflow_action, instance = _perform_workflow_transition(
            instance=capa.workflow_instance,
            user=user,
            capa=capa,
            action=transition_action,
            comments=comments,
        )
        if to_status == CAPA.Status.REJECTED:
            instance.status = WorkflowInstance.Status.REJECTED
            instance.completed_at = now
            instance.save(update_fields=["status", "completed_at"])
        elif to_status == CAPA.Status.CANCELLED:
            instance.status = WorkflowInstance.Status.CANCELLED
            instance.completed_at = now
            instance.save(update_fields=["status", "completed_at"])

    CAPAStatusHistory.objects.create(
        capa=capa,
        from_status=old_status,
        to_status=to_status,
        action=transition_action,
        comments=comments,
        changed_by=user,
        changed_as_position=get_primary_position(user),
        workflow_instance=capa.workflow_instance,
        metadata={
            "workflow_action_id": workflow_action.pk if workflow_action else None,
            "permission_code": permission_code,
        },
    )

    _write_audit_log(
        user=user,
        entity_type="CAPA",
        entity_id=capa.pk,
        action=transition_action,
        old_values=old_values,
        new_values=_capa_audit_snapshot(capa),
        request=request,
    )
    return capa


# Convenience wrappers used by views.


def submit_capa(*, capa_id, user, comments="", request=None):
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.SUBMITTED,
        comments=comments,
        request=request,
    )


def start_review(*, capa_id, user, comments="", request=None):
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.UNDER_REVIEW,
        comments=comments,
        request=request,
    )


def start_root_cause_analysis(*, capa_id, user, comments="", request=None):
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.ROOT_CAUSE_ANALYSIS,
        comments=comments,
        request=request,
    )


def submit_action_plan(*, capa_id, user, comments="", request=None):
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.ACTION_PLAN_REVIEW,
        comments=comments,
        request=request,
    )


def approve_action_plan(*, capa_id, user, comments="", request=None):
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.ACTION_IN_PROGRESS,
        comments=comments,
        request=request,
    )


def send_for_verification(*, capa_id, user, comments="", request=None):
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.VERIFICATION,
        comments=comments,
        request=request,
    )


def start_effectiveness_review(*, capa_id, user, comments="", request=None):
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.EFFECTIVENESS_REVIEW,
        comments=comments,
        request=request,
    )


def close_capa(*, capa_id, user, comments="", request=None):
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.CLOSED,
        comments=comments,
        request=request,
    )


def reject_capa(*, capa_id, user, comments, request=None):
    if not comments.strip():
        raise ValidationError({"comments": "Rejection comments are required."})
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.REJECTED,
        comments=comments,
        request=request,
    )


def cancel_capa(*, capa_id, user, comments, request=None):
    if not comments.strip():
        raise ValidationError({"comments": "Cancellation comments are required."})
    return transition_capa(
        capa_id=capa_id,
        user=user,
        to_status=CAPA.Status.CANCELLED,
        comments=comments,
        request=request,
    )


# =============================================================================
# ACTION OPERATIONS
# =============================================================================


@transaction.atomic
def assign_capa_action(
    *,
    capa_id,
    user,
    action_type,
    description="",
    title="",
    responsible_position=None,
    responsible_employee=None,
    target_date=None,
    root_cause=None,
    is_mandatory=False,
    requires_verification=False,
    request=None,
):
    capa = CAPA.objects.select_for_update().get(pk=capa_id)
    _require_permission(user, PERMISSION_CODES["assign_action"], capa.organization_unit)
    assignable_statuses = {
        CAPA.Status.ROOT_CAUSE_ANALYSIS,
        CAPA.Status.ACTION_PLAN_REVIEW,
        CAPA.Status.ACTION_IN_PROGRESS,
    }
    if capa.status not in assignable_statuses:
        raise CAPATransitionError(
            "Actions cannot be assigned in the current CAPA status."
        )

    last_sequence = (
        capa.actions.order_by("-sequence").values_list("sequence", flat=True).first()
        or 0
    )
    action = CAPAAction(
        capa=capa,
        root_cause=root_cause,
        sequence=last_sequence + 1,
        action_type=action_type,
        title=title,
        description=description,
        responsible_position=responsible_position,
        responsible_employee=responsible_employee,
        assigned_by=user,
        assigned_at=timezone.now(),
        target_date=target_date,
        status=CAPAAction.Status.ASSIGNED,
        is_mandatory=is_mandatory,
        requires_verification=requires_verification,
        created_by=user,
        updated_by=user,
    )
    action.full_clean()
    action.save()

    _write_audit_log(
        user=user,
        entity_type="CAPA_ACTION",
        entity_id=action.pk,
        action="ASSIGN",
        new_values={
            "capa_id": capa.pk,
            "sequence": action.sequence,
            "action_type": action.action_type,
            "responsible_employee_id": action.responsible_employee_id,
            "responsible_position_id": action.responsible_position_id,
            "target_date": action.target_date,
        },
        request=request,
    )
    return action


def _user_can_update_action(user, action):
    if user.is_superuser:
        return True
    employee = getattr(user, "employee", None)
    if employee and action.responsible_employee_id == employee.pk:
        return True
    if action.responsible_position_id and get_user_positions(user).filter(
        pk=action.responsible_position_id
    ).exists():
        return True
    return user_has_jkoms_permission(
        user=user,
        permission_code=PERMISSION_CODES["action_override"],
        organization_unit=action.capa.organization_unit,
    )


@transaction.atomic
def complete_capa_action(
    *,
    action_id,
    user,
    completion_details,
    actual_date=None,
    request=None,
):
    action = (
        CAPAAction.objects
        .select_for_update()
        .select_related("capa__organization_unit")
        .get(pk=action_id)
    )
    _require_permission(
        user,
        PERMISSION_CODES["update_action"],
        action.capa.organization_unit,
    )
    if not _user_can_update_action(user, action):
        raise PermissionDenied(
            "Only the responsible employee, responsible position occupant, "
            "or an authorized override user may complete this action."
        )
    if action.status in {
        CAPAAction.Status.COMPLETED,
        CAPAAction.Status.VERIFIED,
        CAPAAction.Status.CANCELLED,
    }:
        raise ValidationError(
            "This CAPA action cannot be completed in its current status."
        )
    if not completion_details or not completion_details.strip():
        raise ValidationError(
            {"completion_details": "Completion details are required."}
        )

    old_values = {
        "status": action.status,
        "completion_percentage": action.completion_percentage,
        "actual_date": action.actual_date,
    }
    action.status = CAPAAction.Status.COMPLETED
    action.completion_percentage = 100
    action.actual_date = actual_date or timezone.localdate()
    action.completion_details = completion_details
    action.updated_by = user
    action.full_clean()
    action.save()

    _write_audit_log(
        user=user,
        entity_type="CAPA_ACTION",
        entity_id=action.pk,
        action="COMPLETE",
        old_values=old_values,
        new_values={
            "status": action.status,
            "completion_percentage": action.completion_percentage,
            "actual_date": action.actual_date,
            "completion_details": action.completion_details,
        },
        request=request,
    )
    return action


@transaction.atomic
def verify_capa_action(
    *,
    action_id,
    user,
    comments="",
    request=None,
):
    action = (
        CAPAAction.objects
        .select_for_update()
        .select_related("capa__organization_unit")
        .get(pk=action_id)
    )
    _require_permission(user, PERMISSION_CODES["verify"], action.capa.organization_unit)

    if action.status != CAPAAction.Status.COMPLETED:
        raise ValidationError("Only a completed action can be verified.")
    employee = getattr(user, "employee", None)
    user_position_ids = set(
        get_user_positions(user).values_list("pk", flat=True)
    )
    if not user.is_superuser and (
        (employee and action.responsible_employee_id == employee.pk)
        or (
            action.responsible_position_id
            and action.responsible_position_id in user_position_ids
        )
    ):
        raise PermissionDenied(
            "The action owner cannot verify the same CAPA action."
        )

    action.status = CAPAAction.Status.VERIFIED
    action.verified_by = user
    action.verified_at = timezone.now()
    action.verification_comments = comments
    action.updated_by = user
    action.save(
        update_fields=[
            "status",
            "verified_by",
            "verified_at",
            "verification_comments",
            "updated_by",
            "updated_at",
        ]
    )

    _write_audit_log(
        user=user,
        entity_type="CAPA_ACTION",
        entity_id=action.pk,
        action="VERIFY",
        new_values={
            "status": action.status,
            "verified_by_id": user.pk,
            "verified_at": action.verified_at,
            "verification_comments": comments,
        },
        request=request,
    )
    return action
