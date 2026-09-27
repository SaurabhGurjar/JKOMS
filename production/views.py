from django.contrib.auth.decorators import login_required
from django.http import Http404, FileResponse
from django.shortcuts import render
import os
from django.conf import settings


# Temporary department data for page design.
# Later, this will be moved to the database.
DEPARTMENTS = [
    
    {
        "slug": "mixing",
        "name": "Mixing",
        "icon": "fa-solid fa-gears",
        "description": (
            "Compound mixing, Banbury operations, "
            "and mixed compound preparation."
        ),
        "color_class": "department-purple",
    },
    {
        "slug": "extrusion",
        "name": "Extrusion",
        "icon": "fa-solid fa-grip-lines",
        "description": (
            "Tread, sidewall, inner liner, "
            "and component extrusion operations."
        ),
        "color_class": "department-cyan",
    },
    {
        "slug": "calendaring",
        "name": "Calendaring",
        "icon": "fa-solid fa-layer-group",
        "description": (
            "Fabric and steel cord calendaring "
            "and component preparation."
        ),
        "color_class": "department-green",
    },
    {
        "slug": "bead",
        "name": "Bead",
        "icon": "fa-solid fa-circle-notch",
        "description": (
            "Bead wire preparation, winding, "
            "and apex application."
        ),
        "color_class": "department-yellow",
    },
    {
        "slug": "cutter",
        "name": "Cutter",
        "icon": "fa-solid fa-scissors",
        "description": (
            "Bias cutting, ply preparation, and cut component "
            "handling operations."
        ),
        "color_class": "department-blue",
    },
    {
        "slug": "tyre-building",
        "name": "Tyre Building",
        "icon": "fa-solid fa-screwdriver-wrench",
        "description": (
            "Green tyre building and tyre "
            "assembly operations."
        ),
        "color_class": "department-orange",
    },
    {
        "slug": "curing",
        "name": "Curing",
        "icon": "fa-solid fa-temperature-high",
        "description": (
            "Tyre curing, curing press operations, "
            "and mould management."
        ),
        "color_class": "department-red",
    },
    # {
    #     "slug": "final-inspection",
    #     "name": "Final Inspection",
    #     "icon": "fa-solid fa-circle-check",
    #     "description": (
    #         "Finished tyre inspection, grading, "
    #         "and quality verification."
    #     ),
    #     "color_class": "department-teal",
    # },
]


# Configuration for each Production secondary-navbar link.
ENTRY_TYPES = {
    "daily": {
        "title": "Daily Production Entry",
        "short_title": "Daily Entry",
        "icon": "fa-solid fa-calendar-day",
        "description": (
            "Select a department to enter its "
            "daily production information."
        ),
    },
    "shift": {
        "title": "Shift Production Entry",
        "short_title": "Shift Entry",
        "icon": "fa-solid fa-clock",
        "description": (
            "Select a department to enter its "
            "shift-wise production information."
        ),
    },
    "target": {
        "title": "Production Target Entry",
        "short_title": "Target Entry",
        "icon": "fa-solid fa-bullseye",
        "description": (
            "Select a department to define its "
            "production target."
        ),
    },
    "rejection": {
        "title": "Production Rejection Entry",
        "short_title": "Rejection Entry",
        "icon": "fa-solid fa-triangle-exclamation",
        "description": (
            "Select a department to record its "
            "rejection information."
        ),
    },
    "downtime": {
        "title": "Production Downtime Entry",
        "short_title": "Downtime Entry",
        "icon": "fa-solid fa-stopwatch",
        "description": (
            "Select a department to record its "
            "downtime and production loss."
        ),
    },
    "machine-status": {
        "title": "Machine Status Entry",
        "short_title": "Machine Status",
        "icon": "fa-solid fa-screwdriver-wrench",
        "description": (
            "Select a department to update its "
            "machine operating status."
        ),
    },
}


def get_entry_config(entry_type):
    """
    Return configuration for an entry type.

    An invalid entry type returns a 404 response.
    """

    entry_config = ENTRY_TYPES.get(entry_type)

    if entry_config is None:
        raise Http404("Invalid production entry type.")

    return entry_config


def get_department(department_slug):
    """
    Return a department using its URL slug.

    An invalid department returns a 404 response.
    """

    selected_department = next(
        (
            department
            for department in DEPARTMENTS
            if department["slug"] == department_slug
        ),
        None,
    )

    if selected_department is None:
        raise Http404("Invalid production department.")

    return selected_department


@login_required
def production_dashboard(request):
    """
    Display the Production Dashboard.
    """

    context = {
        "departments": DEPARTMENTS,
        "entry_types": ENTRY_TYPES,
        "active_page": "dashboard",
    }

    return render(
        request,
        "production/dashboard.html",
        context,
    )


@login_required
def department_selection(request, entry_type):
    """
    Display department cards for the selected entry type.

    Examples:
    /production/entry/daily/
    /production/entry/shift/
    /production/entry/rejection/
    """

    entry_config = get_entry_config(entry_type)

    context = {
        "departments": DEPARTMENTS,
        "entry_type": entry_type,
        "entry_config": entry_config,
    }

    return render(
        request,
        "production/department_selection.html",
        context,
    )


@login_required
def production_entry_form(
    request,
    entry_type,
    department,
):
    """
    Display an entry form for the selected entry type
    and department.

    Examples:
    /production/entry/shift/mixing/
    /production/entry/rejection/curing/
    /production/entry/downtime/tyre-building/
    """

    entry_config = get_entry_config(entry_type)
    selected_department = get_department(department)

    context = {
        "departments": DEPARTMENTS,
        "entry_type": entry_type,
        "entry_config": entry_config,
        "selected_department": selected_department,
    }

    return render(
        request,
        "production/production_entry_form.html",
        context,
    )

def download_file(request, filename):
    file_path = os.path.join(settings.MEDIA_ROOT, filename)
    if os.path.exists(file_path):
        return FileResponse(
    open(file_path, "rb"),
        as_attachment=True,
        filename=filename
    )
    raise Http404("File not found")