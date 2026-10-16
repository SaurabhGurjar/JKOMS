# usermanagement/authority_resolver.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import QuerySet

from .models import AuthorityRule
from .services import (
    get_applicable_role_assignments,
    get_user_positions,
    user_has_jkoms_permission,
)


class AuthorityResolutionError(ImproperlyConfigured):
    """Raised when workflow authority configuration is invalid or unsupported."""


@dataclass(frozen=True)
class AuthorityDecision:
    allowed: bool
    reason: str
    matched_rule_id: int | None = None
    strategy: str | None = None
    evaluated_rule_ids: tuple[int, ...] = field(default_factory=tuple)

    def require(self) -> None:
        if not self.allowed:
            raise PermissionDenied(self.reason)


# The aliases let existing databases use readable values while providing one
# stable internal vocabulary. Unknown strategies fail closed.
STRATEGY_ALIASES = {
    "SPECIFIC_USER": "SPECIFIC_USER",
    "USER": "SPECIFIC_USER",
    "POSITION": "POSITION",
    "SPECIFIC_POSITION": "POSITION",
    "ROLE": "ROLE_WITH_SCOPE",
    "ROLE_WITH_SCOPE": "ROLE_WITH_SCOPE",
    "PERMISSION": "PERMISSION_HOLDER",
    "PERMISSION_HOLDER": "PERMISSION_HOLDER",
    "STEP_REQUIREMENTS": "STEP_REQUIREMENTS",
}


def _model_has_field(model_or_instance: Any, field_name: str) -> bool:
    model = model_or_instance if isinstance(model_or_instance, type) else type(model_or_instance)
    try:
        model._meta.get_field(field_name)
    except Exception:
        return False
    return True


def _value(instance: Any, field_name: str, default=None):
    return getattr(instance, field_name, default)


def _normalized_strategy(rule: AuthorityRule) -> str:
    raw = str(_value(rule, "resolution_strategy", "") or "").strip().upper()
    strategy = STRATEGY_ALIASES.get(raw)
    if not strategy:
        raise AuthorityResolutionError(
            f"Authority rule {rule.pk} uses unsupported resolution strategy {raw!r}."
        )
    return strategy


def _active_rules_for_step(step) -> list[AuthorityRule]:
    queryset = AuthorityRule.objects.filter(workflow_step=step)
    if _model_has_field(AuthorityRule, "is_active"):
        queryset = queryset.filter(is_active=True)

    select_related = []
    for relation in (
        "role",
        "position",
        "permission",
        "organization_unit_type",
        "specific_user",
    ):
        if _model_has_field(AuthorityRule, relation):
            select_related.append(relation)
    if select_related:
        queryset = queryset.select_related(*select_related)

    order_fields = []
    if _model_has_field(AuthorityRule, "priority"):
        order_fields.append("priority")
    order_fields.append("pk")
    return list(queryset.order_by(*order_fields))


def _organization_type_matches(rule, organization_unit) -> bool:
    required_type_id = _value(rule, "organization_unit_type_id")
    if not required_type_id:
        return True
    if organization_unit is None:
        return False

    actual_type_id = (
        getattr(organization_unit, "unit_type_id", None)
        or getattr(organization_unit, "organization_unit_type_id", None)
        or getattr(organization_unit, "type_id", None)
    )
    return actual_type_id == required_type_id


def _user_has_scoped_role(*, user, role_id, organization_unit, module) -> bool:
    if not role_id:
        return False
    assignments = get_applicable_role_assignments(
        user=user,
        organization_unit=organization_unit,
        module=module,
    )
    return any(assignment.role_id == role_id for assignment in assignments)


def _user_occupies_position(*, user, position_id) -> bool:
    if not position_id:
        return False
    return get_user_positions(user).filter(pk=position_id).exists()


def _evaluate_rule(*, rule, user, workflow_instance, organization_unit) -> tuple[bool, str]:
    strategy = _normalized_strategy(rule)
    module = workflow_instance.workflow_definition.module

    if not _organization_type_matches(rule, organization_unit):
        return False, "The business object's organization unit does not match the rule."

    if strategy == "SPECIFIC_USER":
        specific_user_id = _value(rule, "specific_user_id")
        if not specific_user_id:
            raise AuthorityResolutionError(
                f"Authority rule {rule.pk} requires a specific user."
            )
        return user.pk == specific_user_id, "Matched the configured specific user."

    if strategy == "POSITION":
        position_id = _value(rule, "position_id")
        if not position_id:
            raise AuthorityResolutionError(
                f"Authority rule {rule.pk} requires a position."
            )
        return (
            _user_occupies_position(user=user, position_id=position_id),
            "Matched an active occupant of the configured position.",
        )

    if strategy == "ROLE_WITH_SCOPE":
        role_id = _value(rule, "role_id")
        if not role_id:
            raise AuthorityResolutionError(
                f"Authority rule {rule.pk} requires a role."
            )
        return (
            _user_has_scoped_role(
                user=user,
                role_id=role_id,
                organization_unit=organization_unit,
                module=module,
            ),
            "Matched the configured role within module and organization scope.",
        )

    if strategy == "PERMISSION_HOLDER":
        permission = _value(rule, "permission")
        permission_code = getattr(permission, "code", None)
        if not permission_code:
            raise AuthorityResolutionError(
                f"Authority rule {rule.pk} requires a permission."
            )
        return (
            user_has_jkoms_permission(
                user=user,
                permission_code=permission_code,
                organization_unit=organization_unit,
            ),
            "Matched the configured permission within organization scope.",
        )

    if strategy == "STEP_REQUIREMENTS":
        return _evaluate_step_requirements(
            user=user,
            workflow_instance=workflow_instance,
            organization_unit=organization_unit,
        )

    raise AuthorityResolutionError(
        f"Authority rule {rule.pk} cannot be evaluated with strategy {strategy!r}."
    )


def _evaluate_step_requirements(*, user, workflow_instance, organization_unit) -> tuple[bool, str]:
    step = workflow_instance.current_step
    if step is None:
        return False, "The workflow instance has no current step."

    required_permission = getattr(step, "required_permission", None)
    if required_permission is not None:
        if not user_has_jkoms_permission(
            user=user,
            permission_code=required_permission.code,
            organization_unit=organization_unit,
        ):
            return False, "The user lacks the permission required by the workflow step."

    required_role_id = getattr(step, "required_role_id", None)
    if required_role_id:
        if not _user_has_scoped_role(
            user=user,
            role_id=required_role_id,
            organization_unit=organization_unit,
            module=workflow_instance.workflow_definition.module,
        ):
            return False, "The user lacks the scoped role required by the workflow step."

    if required_permission is None and not required_role_id:
        return False, "The workflow step has no authority rule, role, or permission."

    return True, "Matched the workflow step's required role and permission."


def resolve_workflow_authority(
    *,
    user,
    workflow_instance,
    organization_unit,
    business_object=None,
    allow_step_fallback=True,
) -> AuthorityDecision:
    """Return a fail-closed decision for the current workflow step.

    Rules are evaluated by ascending priority and then primary key. Rules with
    the same priority are OR alternatives. The first matching priority group
    grants authority. If rules exist but none match, step fallback is not used;
    configured rules are authoritative. Step fields are used only when no rules
    exist and allow_step_fallback is True.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return AuthorityDecision(False, "Authentication is required.")
    if not user.is_active:
        return AuthorityDecision(False, "Inactive users cannot perform workflow actions.")
    if user.is_superuser:
        return AuthorityDecision(True, "Superuser authority override.")

    employee = getattr(user, "employee", None)
    if employee is not None and not getattr(employee, "is_active", True):
        return AuthorityDecision(False, "The linked employee record is inactive.")

    step = workflow_instance.current_step
    if step is None:
        return AuthorityDecision(False, "The workflow instance has no current step.")

    rules = _active_rules_for_step(step)
    evaluated: list[int] = []

    if rules:
        priorities = sorted({getattr(rule, "priority", 0) for rule in rules})
        for priority in priorities:
            priority_rules = [
                rule for rule in rules if getattr(rule, "priority", 0) == priority
            ]
            for rule in priority_rules:
                evaluated.append(rule.pk)
                matched, reason = _evaluate_rule(
                    rule=rule,
                    user=user,
                    workflow_instance=workflow_instance,
                    organization_unit=organization_unit,
                )
                if matched:
                    return AuthorityDecision(
                        True,
                        reason,
                        matched_rule_id=rule.pk,
                        strategy=_normalized_strategy(rule),
                        evaluated_rule_ids=tuple(evaluated),
                    )

        return AuthorityDecision(
            False,
            "The user does not match any configured authority rule for the current step.",
            evaluated_rule_ids=tuple(evaluated),
        )

    if not allow_step_fallback:
        return AuthorityDecision(
            False,
            "No authority rule is configured for the current workflow step.",
        )

    matched, reason = _evaluate_step_requirements(
        user=user,
        workflow_instance=workflow_instance,
        organization_unit=organization_unit,
    )
    return AuthorityDecision(matched, reason)


def require_workflow_authority(**kwargs) -> AuthorityDecision:
    decision = resolve_workflow_authority(**kwargs)
    decision.require()
    return decision
