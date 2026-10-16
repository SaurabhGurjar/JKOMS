# quality_capa/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from usermanagement.services import get_user_positions, user_has_jkoms_permission

from .forms import (
    CAPAActionAssignForm,
    CAPAActionCompleteForm,
    CAPAActionProgressForm,
    CAPAActionVerifyForm,
    CAPAAttachmentForm,
    CAPACreateForm,
    CAPADocumentUpdateForm,
    CAPADraftUpdateForm,
    CAPAFollowUpAuditForm,
    CAPARootCauseForm,
    CAPATransitionForm,
    CAPAVerificationForm,
)
from .models import CAPA, CAPAAction, CAPAAttachment, CAPARootCause
from .services import (
    ALLOWED_STATUS_TRANSITIONS,
    CAPATransitionError,
    PERMISSION_CODES,
    approve_action_plan,
    assign_capa_action,
    cancel_capa,
    close_capa,
    complete_capa_action,
    create_capa,
    reject_capa,
    send_for_verification,
    start_effectiveness_review,
    start_review,
    start_root_cause_analysis,
    submit_action_plan,
    submit_capa,
    transition_capa,
    update_capa_draft,
    verify_capa_action,
)


CAPA_SELECT_RELATED = (
    "source",
    "category",
    "organization_unit",
    "originating_organization_unit",
    "owner_position",
    "owner_employee",
    "reported_by_employee",
    "workflow_instance__current_step",
    "created_by",
    "updated_by",
)


def _has_permission(user, code, organization_unit):
    return user_has_jkoms_permission(
        user=user,
        permission_code=code,
        organization_unit=organization_unit,
    )


def _require_permission(user, code, organization_unit):
    if not _has_permission(user, code, organization_unit):
        raise PermissionDenied


def _get_capa_for_user(user, pk, permission=PERMISSION_CODES["view"]):
    capa = get_object_or_404(
        CAPA.objects.select_related(*CAPA_SELECT_RELATED).prefetch_related(
            "management_systems",
            "root_causes",
            "actions__responsible_employee",
            "actions__responsible_position",
            "verifications",
            "attachments",
            "follow_up_audits",
            "document_updates",
            "status_history__changed_by",
        ),
        pk=pk,
    )
    _require_permission(user, permission, capa.organization_unit)
    return capa


def _form_error_message(exc):
    if isinstance(exc, ValidationError):
        if hasattr(exc, "message_dict"):
            return "; ".join(
                f"{field}: {', '.join(values)}"
                for field, values in exc.message_dict.items()
            )
        return "; ".join(exc.messages)
    return str(exc)


def _transition_capabilities(user, capa):
    capabilities = {}
    for status in ALLOWED_STATUS_TRANSITIONS.get(capa.status, set()):
        permission_map = {
            CAPA.Status.SUBMITTED: "submit",
            CAPA.Status.UNDER_REVIEW: "review",
            CAPA.Status.ROOT_CAUSE_ANALYSIS: "review",
            CAPA.Status.ACTION_PLAN_REVIEW: "review",
            CAPA.Status.ACTION_IN_PROGRESS: "approve",
            CAPA.Status.VERIFICATION: "verify",
            CAPA.Status.EFFECTIVENESS_REVIEW: "effectiveness_review",
            CAPA.Status.CLOSED: "close",
            CAPA.Status.REJECTED: "review",
            CAPA.Status.CANCELLED: "cancel",
            CAPA.Status.DRAFT: "edit",
        }
        key = permission_map[status]
        capabilities[status] = _has_permission(
            user, PERMISSION_CODES[key], capa.organization_unit
        )
    return capabilities


@login_required
@require_GET
def capa_list(request):
    queryset = CAPA.objects.select_related(
        "organization_unit", "source", "category", "owner_employee"
    ).filter(is_active=True)

    # Authorization remains the final control. This Python-side filtering is
    # appropriate for the initial rollout; optimize with descendant ID queries later.
    queryset = [
        capa
        for capa in queryset.order_by("-created_at")
        if _has_permission(request.user, PERMISSION_CODES["view"], capa.organization_unit)
    ]

    query = request.GET.get("q", "").strip().lower()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    if query:
        queryset = [
            capa
            for capa in queryset
            if query in capa.capa_number.lower()
            or query in capa.title.lower()
            or query in (capa.nonconformity_number or "").lower()
        ]
    if status:
        queryset = [capa for capa in queryset if capa.status == status]
    if priority:
        queryset = [capa for capa in queryset if capa.priority == priority]

    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "quality_capa/capa_list.html",
        {
            "page_obj": page,
            "status_choices": CAPA.Status.choices,
            "priority_choices": CAPA.Priority.choices,
            "can_create": request.user.is_superuser,
        },
    )


@login_required
@require_GET
def capa_detail(request, pk):
    capa = _get_capa_for_user(request.user, pk)
    context = {
        "capa": capa,
        "transition_capabilities": _transition_capabilities(request.user, capa),
        "can_edit": capa.status == CAPA.Status.DRAFT
        and _has_permission(request.user, PERMISSION_CODES["edit"], capa.organization_unit),
        "can_assign_action": _has_permission(
            request.user, PERMISSION_CODES["assign_action"], capa.organization_unit
        ),
        "can_verify": _has_permission(
            request.user, PERMISSION_CODES["verify"], capa.organization_unit
        ),
    }
    return render(request, "quality_capa/capa_detail.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def capa_create(request):
    form = CAPACreateForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        management_systems = data.pop("management_systems", [])
        organization_unit = data.pop("organization_unit")
        source = data.pop("source")
        category = data.pop("category")
        title = data.pop("title")
        problem_description = data.pop("problem_description")
        try:
            capa = create_capa(
                user=request.user,
                organization_unit=organization_unit,
                source=source,
                category=category,
                title=title,
                problem_description=problem_description,
                form_definition=None,
                form_response={},
                management_systems=management_systems,
                request=request,
                **data,
            )
        except (ValidationError, PermissionDenied) as exc:
            if isinstance(exc, PermissionDenied):
                raise
            form.add_error(None, _form_error_message(exc))
        else:
            messages.success(request, f"{capa.capa_number} created as a draft.")
            return redirect("quality_capa:detail", pk=capa.pk)
    return render(request, "quality_capa/capa_form.html", {"form": form, "mode": "create"})


@login_required
@require_http_methods(["GET", "POST"])
def capa_edit(request, pk):
    capa = _get_capa_for_user(request.user, pk, PERMISSION_CODES["edit"])
    if capa.status != CAPA.Status.DRAFT:
        raise PermissionDenied("Only draft CAPAs can be edited.")
    form = CAPADraftUpdateForm(
        request.POST or None,
        request.FILES or None,
        instance=capa,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        changes = {
            name: value
            for name, value in form.cleaned_data.items()
            if name != "management_systems"
        }
        try:
            capa = update_capa_draft(
                capa_id=capa.pk,
                user=request.user,
                changes=changes,
                management_systems=form.cleaned_data.get("management_systems", []),
                request=request,
            )
        except ValidationError as exc:
            form.add_error(None, _form_error_message(exc))
        else:
            messages.success(request, f"{capa.capa_number} updated.")
            return redirect("quality_capa:detail", pk=capa.pk)
    return render(
        request,
        "quality_capa/capa_form.html",
        {"form": form, "capa": capa, "mode": "edit"},
    )


def _transition_to(status):
    def handler(*, capa_id, user, comments="", request=None):
        return transition_capa(
            capa_id=capa_id,
            user=user,
            to_status=status,
            comments=comments,
            request=request,
        )
    return handler


TRANSITION_HANDLERS = {
    "submit": (submit_capa, False),
    "start-review": (start_review, False),
    "start-root-cause": (start_root_cause_analysis, False),
    "submit-action-plan": (submit_action_plan, False),
    "approve-action-plan": (approve_action_plan, False),
    "send-verification": (send_for_verification, False),
    "start-effectiveness": (start_effectiveness_review, False),
    "close": (close_capa, False),
    "reject": (reject_capa, True),
    "cancel": (cancel_capa, True),
    "return-draft": (_transition_to(CAPA.Status.DRAFT), True),
    "return-review": (_transition_to(CAPA.Status.UNDER_REVIEW), True),
    "return-root-cause": (_transition_to(CAPA.Status.ROOT_CAUSE_ANALYSIS), True),
    "return-action-plan": (_transition_to(CAPA.Status.ACTION_PLAN_REVIEW), True),
    "return-action-progress": (_transition_to(CAPA.Status.ACTION_IN_PROGRESS), True),
    "return-verification": (_transition_to(CAPA.Status.VERIFICATION), True),
}


@login_required
@require_http_methods(["GET", "POST"])
def capa_transition(request, pk, operation):
    capa = _get_capa_for_user(request.user, pk)
    if operation not in TRANSITION_HANDLERS:
        raise Http404
    handler, require_comments = TRANSITION_HANDLERS[operation]
    form = CAPATransitionForm(request.POST or None, require_comments=require_comments)
    if request.method == "POST" and form.is_valid():
        try:
            capa = handler(
                capa_id=capa.pk,
                user=request.user,
                comments=form.cleaned_data.get("comments", ""),
                request=request,
            )
        except PermissionDenied:
            raise
        except (ValidationError, CAPATransitionError) as exc:
            form.add_error(None, _form_error_message(exc))
        else:
            messages.success(request, f"CAPA status changed to {capa.get_status_display()}.")
            return redirect("quality_capa:detail", pk=capa.pk)
    return render(
        request,
        "quality_capa/transition_form.html",
        {"form": form, "capa": capa, "operation": operation},
    )


@login_required
@require_http_methods(["GET", "POST"])
def root_cause_create(request, pk):
    capa = _get_capa_for_user(request.user, pk, PERMISSION_CODES["review"])
    if capa.status not in {CAPA.Status.UNDER_REVIEW, CAPA.Status.ROOT_CAUSE_ANALYSIS}:
        raise PermissionDenied("Root cause can only be entered during review or analysis.")
    form = CAPARootCauseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            root_cause = form.save(commit=False)
            root_cause.capa = capa
            root_cause.sequence = (capa.root_causes.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
            root_cause.created_by = request.user
            if root_cause.is_confirmed:
                root_cause.confirmed_by = request.user
                root_cause.confirmed_at = timezone.now()
            root_cause.full_clean()
            root_cause.save()
        messages.success(request, "Root cause added.")
        return redirect("quality_capa:detail", pk=capa.pk)
    return render(request, "quality_capa/related_form.html", {"form": form, "capa": capa, "title": "Add root cause"})


@login_required
@require_http_methods(["GET", "POST"])
def action_assign(request, pk):
    capa = _get_capa_for_user(request.user, pk, PERMISSION_CODES["assign_action"])
    form = CAPAActionAssignForm(request.POST or None, capa=capa)
    if request.method == "POST" and form.is_valid():
        try:
            action = assign_capa_action(
                capa_id=capa.pk,
                user=request.user,
                request=request,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, _form_error_message(exc))
        else:
            messages.success(request, f"Action {action.sequence} assigned.")
            return redirect("quality_capa:detail", pk=capa.pk)
    return render(request, "quality_capa/related_form.html", {"form": form, "capa": capa, "title": "Assign CAPA action"})


def _user_can_update_action_in_view(user, action):
    if user.is_superuser:
        return True
    employee = getattr(user, "employee", None)
    if employee and action.responsible_employee_id == employee.pk:
        return True
    if action.responsible_position_id and get_user_positions(user).filter(
        pk=action.responsible_position_id
    ).exists():
        return True
    return _has_permission(
        user,
        PERMISSION_CODES["action_override"],
        action.capa.organization_unit,
    )


@login_required
@require_http_methods(["GET", "POST"])
def action_progress(request, action_id):
    action = get_object_or_404(CAPAAction.objects.select_related("capa__organization_unit"), pk=action_id)
    _require_permission(request.user, PERMISSION_CODES["update_action"], action.capa.organization_unit)
    if not _user_can_update_action_in_view(request.user, action):
        raise PermissionDenied(
            "Only the action owner, responsible position occupant, or override user may update progress."
        )
    form = CAPAActionProgressForm(request.POST or None, instance=action)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.updated_by = request.user
        updated.full_clean()
        updated.save()
        messages.success(request, "Action progress updated.")
        return redirect("quality_capa:detail", pk=action.capa_id)
    return render(request, "quality_capa/related_form.html", {"form": form, "capa": action.capa, "title": "Update action progress"})


@login_required
@require_http_methods(["GET", "POST"])
def action_complete(request, action_id):
    action = get_object_or_404(CAPAAction.objects.select_related("capa__organization_unit"), pk=action_id)
    form = CAPAActionCompleteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_capa_action(
                action_id=action.pk,
                user=request.user,
                completion_details=form.cleaned_data["completion_details"],
                actual_date=form.cleaned_data.get("actual_date"),
                request=request,
            )
        except PermissionDenied:
            raise
        except ValidationError as exc:
            form.add_error(None, _form_error_message(exc))
        else:
            messages.success(request, "Action completed.")
            return redirect("quality_capa:detail", pk=action.capa_id)
    return render(request, "quality_capa/related_form.html", {"form": form, "capa": action.capa, "title": "Complete action"})


@login_required
@require_http_methods(["GET", "POST"])
def action_verify(request, action_id):
    action = get_object_or_404(CAPAAction.objects.select_related("capa__organization_unit"), pk=action_id)
    form = CAPAActionVerifyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            verify_capa_action(
                action_id=action.pk,
                user=request.user,
                comments=form.cleaned_data.get("comments", ""),
                request=request,
            )
        except PermissionDenied:
            raise
        except ValidationError as exc:
            form.add_error(None, _form_error_message(exc))
        else:
            messages.success(request, "Action verified.")
            return redirect("quality_capa:detail", pk=action.capa_id)
    return render(request, "quality_capa/related_form.html", {"form": form, "capa": action.capa, "title": "Verify action"})


@login_required
@require_http_methods(["GET", "POST"])
def verification_create(request, pk):
    capa = _get_capa_for_user(request.user, pk, PERMISSION_CODES["verify"])
    form = CAPAVerificationForm(request.POST or None, capa=capa, user=request.user)
    if request.method == "POST" and form.is_valid():
        verification = form.save(commit=False)
        verification.capa = capa
        verification.reviewed_by = request.user
        verification.full_clean()
        verification.save()
        messages.success(request, "Verification recorded.")
        return redirect("quality_capa:detail", pk=capa.pk)
    return render(request, "quality_capa/related_form.html", {"form": form, "capa": capa, "title": "Record verification"})


@login_required
@require_http_methods(["GET", "POST"])
def attachment_create(request, pk):
    capa = _get_capa_for_user(request.user, pk)
    form = CAPAAttachmentForm(request.POST or None, request.FILES or None, capa=capa)
    if request.method == "POST" and form.is_valid():
        attachment = form.save(commit=False)
        attachment.capa = capa
        attachment.uploaded_by = request.user
        attachment.full_clean()
        attachment.save()
        messages.success(request, "Attachment uploaded.")
        return redirect("quality_capa:detail", pk=capa.pk)
    return render(request, "quality_capa/related_form.html", {"form": form, "capa": capa, "title": "Upload attachment"})


@login_required
@require_GET
def attachment_download(request, attachment_id):
    attachment = get_object_or_404(
        CAPAAttachment.objects.select_related("capa__organization_unit"),
        pk=attachment_id,
        is_active=True,
    )
    _require_permission(request.user, PERMISSION_CODES["view"], attachment.capa.organization_unit)
    if not attachment.file:
        raise Http404
    response = HttpResponse(attachment.file.open("rb"), content_type="application/octet-stream")
    filename = attachment.original_filename or attachment.file.name.rsplit("/", 1)[-1]
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
