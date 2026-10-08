import calendar
from collections import defaultdict
from datetime import date
from io import BytesIO
from django.db.models import Q
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)

from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from openpyxl.utils import get_column_letter

from usermanagement.decorators import staff_required
# from usermanagement.models import Employee

from .forms import BBSObservationForm
from .models import BBSObservation


# =============================================================================
# PUBLIC BBS SUBMISSION
# =============================================================================


def bbs_observation_create(request):
    """
    Public BBS Observation submission.

    No LTPOMS authentication is required.

    Flow:
        GET
            -> Display blank BBS form

        POST
            -> Validate BBSObservationForm
            -> Save BBSObservation
            -> Capture request metadata
            -> Store submission summary in session
            -> Redirect to success page

    Validation handled by BBSObservationForm includes:
        - Required employee identification
        - Card No. normalization
        - Future date prevention
        - One submission per Card No. / Date
        - Root cause validation
        - At-Risk checklist validation

    Database uniqueness remains the final protection against
    duplicate Card No. / Date submissions.
    """

    # =========================================================================
    # POST
    # =========================================================================

    if request.method == "POST":

        form = BBSObservationForm(
            request.POST
        )

        if form.is_valid():

            try:

                with transaction.atomic():

                    observation = form.save(
                        commit=False
                    )

                    # ---------------------------------------------------------
                    # REQUEST METADATA
                    # ---------------------------------------------------------

                    observation.ip_address = (
                        get_client_ip(request)
                    )

                    observation.user_agent = (
                        request.META.get(
                            "HTTP_USER_AGENT",
                            "",
                        )[:1000]
                    )

                    # ---------------------------------------------------------
                    # SAVE
                    # ---------------------------------------------------------

                    observation.save()

            # -----------------------------------------------------------------
            # DATABASE DUPLICATE PROTECTION
            # -----------------------------------------------------------------

            except IntegrityError:

                form.add_error(
                    None,
                    (
                        "A BBS observation has already "
                        "been submitted for this Card No. "
                        "on the selected date."
                    ),
                )

            # -----------------------------------------------------------------
            # SUCCESS
            # -----------------------------------------------------------------

            else:

                request.session[
                    "bbs_last_submission"
                ] = {
                    "observation_id":
                        observation.pk,

                    "card_no":
                        observation.card_no,

                    "employee_name":
                        observation.employee_name,

                    "observation_date":
                        observation
                        .observation_date
                        .isoformat(),

                    "observation_time":
                        observation
                        .observation_time
                        .strftime("%H:%M"),

                    "shift":
                        observation.shift,

                    "area":
                        observation.area,
                }

                return redirect(
                    "safety_bbs:bbs_success"
                )

    # =========================================================================
    # GET
    # =========================================================================

    else:

        form = BBSObservationForm()

    # =========================================================================
    # RENDER FORM
    # =========================================================================

    context = {
        "form": form,

        "page_title":
            "BBS Observation Card",

        "page_description":
            "Behaviour Based Safety Programme",
    }

    return render(
        request,
        "safety_bbs/bbs_form.html",
        context,
    )


# =============================================================================
# PUBLIC SUBMISSION SUCCESS
# =============================================================================


def bbs_success(request):
    """
    Public acknowledgement page.

    The page can only be reached meaningfully after a successful
    BBS submission.

    The submission information is removed from the session after
    being displayed once.
    """

    submission = request.session.pop(
        "bbs_last_submission",
        None,
    )

    # -------------------------------------------------------------------------
    # DIRECT ACCESS WITHOUT SUBMISSION
    # -------------------------------------------------------------------------

    if not submission:

        return redirect(
            "safety_bbs:bbs_create"
        )

    # -------------------------------------------------------------------------
    # RENDER SUCCESS
    # -------------------------------------------------------------------------

    context = {
        "submission":
            submission,

        "page_title":
            "BBS Observation Submitted",
    }

    return render(
        request,
        "safety_bbs/bbs_success.html",
        context,
    )


# =============================================================================
# REQUEST HELPERS
# =============================================================================


def get_client_ip(request):
    """
    Return the requesting client's IP address.

    For the current LTPOMS deployment this uses REMOTE_ADDR.

    X-Forwarded-For is deliberately not trusted here because an
    arbitrary client can spoof that header unless LTPOMS is operating
    behind a specifically configured trusted reverse proxy.
    """

    return request.META.get(
        "REMOTE_ADDR"
    )
    
# =============================================================================
# BBS COMPLIANCE DASHBOARD
# =============================================================================


@staff_required
def bbs_dashboard(request):
    """
    Protected monthly BBS compliance dashboard.

    Displays:
        Employee Name
        Card No.
        Day-wise BBS submission status
        Total submitted days
        Applicable days
        Compliance percentage

    Current implementation:
        - Employee population is derived from BBS submissions.
        - One Card No. represents one employee.
        - Future dates are not counted as missed.
        - For the current month, compliance is calculated up to today.
        - For previous months, all calendar days are considered.

    Later this can be connected to Employee master / attendance /
    shift roster for true working-day compliance.
    """

    today = timezone.localdate()

    # =========================================================================
    # MONTH / YEAR FILTER
    # =========================================================================

    try:
        selected_year = int(
            request.GET.get(
                "year",
                today.year,
            )
        )
    except (TypeError, ValueError):
        selected_year = today.year

    try:
        selected_month = int(
            request.GET.get(
                "month",
                today.month,
            )
        )
    except (TypeError, ValueError):
        selected_month = today.month

    if selected_month < 1 or selected_month > 12:
        selected_month = today.month

    # Keep the dashboard within a reasonable year range.
    if (
        selected_year < 2000
        or selected_year > today.year
    ):
        selected_year = today.year

    # =========================================================================
    # MONTH INFORMATION
    # =========================================================================

    days_in_month = calendar.monthrange(
        selected_year,
        selected_month,
    )[1]

    days = list(
        range(
            1,
            days_in_month + 1,
        )
    )

    month_name = calendar.month_name[
        selected_month
    ]

    selected_month_start = date(
        selected_year,
        selected_month,
        1,
    )

    # =========================================================================
    # DETERMINE APPLICABLE DAYS
    # =========================================================================

    current_month_start = date(
        today.year,
        today.month,
        1,
    )

    if selected_month_start > current_month_start:

        applicable_days = 0

    elif (
        selected_year == today.year
        and selected_month == today.month
    ):

        applicable_days = today.day

    else:

        applicable_days = days_in_month

    # =========================================================================
    # OBSERVATIONS
    # =========================================================================

    observations = (
        BBSObservation.objects
        .filter(
            observation_date__year=selected_year,
            observation_date__month=selected_month,
        )
        .order_by(
            "card_no",
            "observation_date",
        )
    )

    # =========================================================================
    # BUILD EMPLOYEE / DATE LOOKUP
    # =========================================================================

    employees = {}

    submissions = defaultdict(set)

    for observation in observations:

        card_no = observation.card_no

        # Keep latest available employee name for the Card No.
        employees[card_no] = (
            observation.employee_name
        )

        submissions[card_no].add(
            observation.observation_date.day
        )

    # =========================================================================
    # DASHBOARD ROWS
    # =========================================================================

    rows = []

    total_expected = 0
    total_submitted = 0

    for card_no in sorted(employees):

        employee_name = employees[
            card_no
        ]

        submitted_days = submissions[
            card_no
        ]

        day_statuses = []

        submitted_count = 0

        for day_number in days:

            day_date = date(
                selected_year,
                selected_month,
                day_number,
            )

            if day_date > today:

                status = "future"

            elif day_number in submitted_days:

                status = "submitted"
                submitted_count += 1

            else:

                status = "missing"

            day_statuses.append(
                {
                    "day": day_number,
                    "status": status,
                }
            )

        if applicable_days:

            compliance_percentage = round(
                (
                    submitted_count
                    / applicable_days
                )
                * 100,
                1,
            )

        else:

            compliance_percentage = 0

        total_expected += applicable_days
        total_submitted += submitted_count

        rows.append(
            {
                "employee_name":
                    employee_name,

                "card_no":
                    card_no,

                "day_statuses":
                    day_statuses,

                "submitted_count":
                    submitted_count,

                "applicable_days":
                    applicable_days,

                "compliance_percentage":
                    compliance_percentage,
            }
        )

    # =========================================================================
    # SUMMARY KPI
    # =========================================================================

    total_employees = len(rows)

    if total_expected:

        overall_compliance = round(
            (
                total_submitted
                / total_expected
            )
            * 100,
            1,
        )

    else:

        overall_compliance = 0

    submitted_today = 0

    if (
        selected_year == today.year
        and selected_month == today.month
    ):

        submitted_today = (
            BBSObservation.objects
            .filter(
                observation_date=today
            )
            .values(
                "card_no"
            )
            .distinct()
            .count()
        )

    pending_today = max(
        total_employees - submitted_today,
        0,
    )

    # =========================================================================
    # MONTH OPTIONS
    # =========================================================================

    months = [
        {
            "number": month_number,
            "name": calendar.month_name[
                month_number
            ],
        }
        for month_number in range(
            1,
            13,
        )
    ]

    years = list(
        range(
            today.year,
            2024,
            -1,
        )
    )

    # =========================================================================
    # CONTEXT
    # =========================================================================

    context = {
        "rows": rows,
        "days": days,

        "selected_month":
            selected_month,

        "selected_year":
            selected_year,

        "month_name":
            month_name,

        "months":
            months,

        "years":
            years,

        "today":
            today,

        "total_employees":
            total_employees,

        "submitted_today":
            submitted_today,

        "pending_today":
            pending_today,

        "overall_compliance":
            overall_compliance,

        "applicable_days":
            applicable_days,
    }

    return render(
        request,
        "safety_bbs/bbs_dashboard.html",
        context,
    )
    
# # =============================================================================
# # BBS MONTHLY COMPLIANCE EXCEL EXPORT
# # =============================================================================


# @staff_required
# def bbs_monthly_export(request):
#     """
#     Export monthly BBS compliance as an Excel .xlsx file.

#     Output:
#         Employee Name
#         Card No.
#         Day-wise status
#         Filled Days
#         Required Days
#         Compliance %

#     Status:
#         YES = BBS submitted
#         NO  = BBS not submitted
#         -   = Future date

#     Compliance population:
#         Active Employees from LTPOMS Employee master.

#     Current compliance basis:
#         Calendar days up to today for the current month.
#         Full calendar month for previous months.
#     """

#     today = timezone.localdate()

#     # =========================================================================
#     # YEAR
#     # =========================================================================

#     try:
#         selected_year = int(
#             request.GET.get(
#                 "year",
#                 today.year,
#             )
#         )
#     except (TypeError, ValueError):
#         selected_year = today.year

#     # =========================================================================
#     # MONTH
#     # =========================================================================

#     try:
#         selected_month = int(
#             request.GET.get(
#                 "month",
#                 today.month,
#             )
#         )
#     except (TypeError, ValueError):
#         selected_month = today.month

#     # =========================================================================
#     # VALIDATE PERIOD
#     # =========================================================================

#     if not 1 <= selected_month <= 12:
#         selected_month = today.month

#     if (
#         selected_year < 2000
#         or selected_year > today.year
#     ):
#         selected_year = today.year

#     # =========================================================================
#     # MONTH INFORMATION
#     # =========================================================================

#     days_in_month = calendar.monthrange(
#         selected_year,
#         selected_month,
#     )[1]

#     days = list(
#         range(
#             1,
#             days_in_month + 1,
#         )
#     )

#     month_name = calendar.month_name[
#         selected_month
#     ]

#     selected_month_start = date(
#         selected_year,
#         selected_month,
#         1,
#     )

#     current_month_start = date(
#         today.year,
#         today.month,
#         1,
#     )

#     # =========================================================================
#     # APPLICABLE DAYS
#     # =========================================================================

#     if selected_month_start > current_month_start:
#         applicable_days = 0

#     elif (
#         selected_year == today.year
#         and selected_month == today.month
#     ):
#         applicable_days = today.day

#     else:
#         applicable_days = days_in_month

#     # =========================================================================
#     # ACTIVE EMPLOYEES
#     # =========================================================================

#     employees = (
#         Employee.objects
#         .filter(
#             is_active=True,
#             employment_status=(
#                 Employee
#                 .EmploymentStatus
#                 .ACTIVE
#             ),
#         )
#         .order_by(
#             "employee_code"
#         )
#     )

#     # =========================================================================
#     # BBS SUBMISSIONS
#     # =========================================================================

#     observations = (
#         BBSObservation.objects
#         .filter(
#             observation_date__year=
#                 selected_year,
#             observation_date__month=
#                 selected_month,
#         )
#         .only(
#             "card_no",
#             "observation_date",
#         )
#     )

#     # =========================================================================
#     # BUILD SUBMISSION LOOKUP
#     # =========================================================================

#     submission_days = defaultdict(set)

#     for observation in observations:

#         card_no = (
#             observation.card_no
#             .strip()
#             .upper()
#         )

#         submission_days[
#             card_no
#         ].add(
#             observation
#             .observation_date
#             .day
#         )

#     # =========================================================================
#     # CREATE WORKBOOK
#     # =========================================================================

#     workbook = Workbook()

#     worksheet = workbook.active

#     worksheet.title = (
#         "BBS Compliance"
#     )

#     # =========================================================================
#     # COLORS
#     # =========================================================================

#     LTPOMS_GREEN = "334D42"
#     LTPOMS_YELLOW = "FFEB00"

#     WHITE = "FFFFFF"

#     LIGHT_GREEN = "E8F5E9"
#     GREEN_TEXT = "198754"

#     LIGHT_RED = "FDECEC"
#     RED_TEXT = "DC2626"

#     LIGHT_GREY = "F3F4F6"
#     GREY_TEXT = "808080"

#     BORDER_COLOR = "D9D9D9"

#     # =========================================================================
#     # COMMON STYLES
#     # =========================================================================

#     thin_border = Border(
#         left=Side(
#             style="thin",
#             color=BORDER_COLOR,
#         ),
#         right=Side(
#             style="thin",
#             color=BORDER_COLOR,
#         ),
#         top=Side(
#             style="thin",
#             color=BORDER_COLOR,
#         ),
#         bottom=Side(
#             style="thin",
#             color=BORDER_COLOR,
#         ),
#     )

#     # =========================================================================
#     # TITLE
#     # =========================================================================

#     last_column = (
#         2
#         + days_in_month
#         + 3
#     )

#     worksheet.merge_cells(
#         start_row=1,
#         start_column=1,
#         end_row=1,
#         end_column=last_column,
#     )

#     title_cell = worksheet.cell(
#         row=1,
#         column=1,
#     )

#     title_cell.value = (
#         "LTPOMS - BBS Monthly Compliance"
#     )

#     title_cell.font = Font(
#         bold=True,
#         size=16,
#         color=LTPOMS_YELLOW,
#     )

#     title_cell.fill = PatternFill(
#         fill_type="solid",
#         fgColor=LTPOMS_GREEN,
#     )

#     title_cell.alignment = Alignment(
#         horizontal="center",
#         vertical="center",
#     )

#     worksheet.row_dimensions[1].height = 28

#     # =========================================================================
#     # PERIOD INFO
#     # =========================================================================

#     worksheet.merge_cells(
#         start_row=2,
#         start_column=1,
#         end_row=2,
#         end_column=last_column,
#     )

#     period_cell = worksheet.cell(
#         row=2,
#         column=1,
#     )

#     period_cell.value = (
#         f"Behaviour Based Safety Programme | "
#         f"{month_name} {selected_year}"
#     )

#     period_cell.font = Font(
#         bold=True,
#         color=LTPOMS_GREEN,
#     )

#     period_cell.alignment = Alignment(
#         horizontal="center",
#         vertical="center",
#     )

#     # =========================================================================
#     # HEADER
#     # =========================================================================

#     header_row = 4

#     headers = [
#         "Employee Name",
#         "Card No.",
#     ]

#     for day_number in days:
#         headers.append(
#             f"{day_number:02d}"
#         )

#     headers.extend(
#         [
#             "Filled",
#             "Required",
#             "Compliance %",
#         ]
#     )

#     for column_number, header in enumerate(
#         headers,
#         start=1,
#     ):

#         cell = worksheet.cell(
#             row=header_row,
#             column=column_number,
#             value=header,
#         )

#         cell.font = Font(
#             bold=True,
#             color=WHITE,
#         )

#         cell.fill = PatternFill(
#             fill_type="solid",
#             fgColor=LTPOMS_GREEN,
#         )

#         cell.alignment = Alignment(
#             horizontal="center",
#             vertical="center",
#         )

#         cell.border = thin_border

#     worksheet.row_dimensions[
#         header_row
#     ].height = 24

#     # =========================================================================
#     # DATA
#     # =========================================================================

#     current_row = header_row + 1

#     total_submitted = 0
#     total_required = 0

#     for employee in employees:

#         card_no = (
#             employee.employee_code
#             .strip()
#             .upper()
#         )

#         employee_name = (
#             employee.full_name
#         )

#         employee_submission_days = (
#             submission_days.get(
#                 card_no,
#                 set(),
#             )
#         )

#         # ---------------------------------------------------------------------
#         # EMPLOYEE NAME
#         # ---------------------------------------------------------------------

#         worksheet.cell(
#             row=current_row,
#             column=1,
#             value=employee_name,
#         )

#         # ---------------------------------------------------------------------
#         # CARD NO.
#         # ---------------------------------------------------------------------

#         worksheet.cell(
#             row=current_row,
#             column=2,
#             value=card_no,
#         )

#         submitted_count = 0

#         # ---------------------------------------------------------------------
#         # DAILY STATUS
#         # ---------------------------------------------------------------------

#         for day_number in days:

#             day_date = date(
#                 selected_year,
#                 selected_month,
#                 day_number,
#             )

#             column_number = (
#                 day_number + 2
#             )

#             cell = worksheet.cell(
#                 row=current_row,
#                 column=column_number,
#             )

#             # -----------------------------------------------------------------
#             # FUTURE
#             # -----------------------------------------------------------------

#             if day_date > today:

#                 cell.value = "-"

#                 cell.fill = PatternFill(
#                     fill_type="solid",
#                     fgColor=LIGHT_GREY,
#                 )

#                 cell.font = Font(
#                     color=GREY_TEXT,
#                 )

#             # -----------------------------------------------------------------
#             # SUBMITTED
#             # -----------------------------------------------------------------

#             elif (
#                 day_number
#                 in employee_submission_days
#             ):

#                 cell.value = "YES"

#                 submitted_count += 1

#                 cell.fill = PatternFill(
#                     fill_type="solid",
#                     fgColor=LIGHT_GREEN,
#                 )

#                 cell.font = Font(
#                     bold=True,
#                     color=GREEN_TEXT,
#                 )

#             # -----------------------------------------------------------------
#             # NOT SUBMITTED
#             # -----------------------------------------------------------------

#             else:

#                 cell.value = "NO"

#                 cell.fill = PatternFill(
#                     fill_type="solid",
#                     fgColor=LIGHT_RED,
#                 )

#                 cell.font = Font(
#                     bold=True,
#                     color=RED_TEXT,
#                 )

#             cell.alignment = Alignment(
#                 horizontal="center",
#                 vertical="center",
#             )

#             cell.border = thin_border

#         # ---------------------------------------------------------------------
#         # COMPLIANCE
#         # ---------------------------------------------------------------------

#         if applicable_days > 0:

#             compliance_percentage = round(
#                 (
#                     submitted_count
#                     / applicable_days
#                 )
#                 * 100,
#                 1,
#             )

#         else:

#             compliance_percentage = 0.0

#         # ---------------------------------------------------------------------
#         # SUMMARY COLUMNS
#         # ---------------------------------------------------------------------

#         filled_column = (
#             2
#             + days_in_month
#             + 1
#         )

#         required_column = (
#             filled_column + 1
#         )

#         compliance_column = (
#             required_column + 1
#         )

#         worksheet.cell(
#             row=current_row,
#             column=filled_column,
#             value=submitted_count,
#         )

#         worksheet.cell(
#             row=current_row,
#             column=required_column,
#             value=applicable_days,
#         )

#         compliance_cell = worksheet.cell(
#             row=current_row,
#             column=compliance_column,
#             value=compliance_percentage / 100,
#         )

#         compliance_cell.number_format = (
#             "0.0%"
#         )

#         # ---------------------------------------------------------------------
#         # COMPLIANCE COLOR
#         # ---------------------------------------------------------------------

#         if compliance_percentage >= 90:

#             compliance_cell.font = Font(
#                 bold=True,
#                 color=GREEN_TEXT,
#             )

#         elif compliance_percentage >= 75:

#             compliance_cell.font = Font(
#                 bold=True,
#                 color="D97706",
#             )

#         else:

#             compliance_cell.font = Font(
#                 bold=True,
#                 color=RED_TEXT,
#             )

#         # ---------------------------------------------------------------------
#         # NORMAL CELL FORMATTING
#         # ---------------------------------------------------------------------

#         for column_number in range(
#             1,
#             last_column + 1,
#         ):

#             cell = worksheet.cell(
#                 row=current_row,
#                 column=column_number,
#             )

#             cell.border = thin_border

#             if column_number > 2:

#                 cell.alignment = Alignment(
#                     horizontal="center",
#                     vertical="center",
#                 )

#             else:

#                 cell.alignment = Alignment(
#                     vertical="center",
#                 )

#         total_submitted += (
#             submitted_count
#         )

#         total_required += (
#             applicable_days
#         )

#         current_row += 1

#     # =========================================================================
#     # SUMMARY ROW
#     # =========================================================================

#     summary_row = current_row + 1

#     worksheet.merge_cells(
#         start_row=summary_row,
#         start_column=1,
#         end_row=summary_row,
#         end_column=2,
#     )

#     summary_label = worksheet.cell(
#         row=summary_row,
#         column=1,
#         value="Overall Compliance",
#     )

#     summary_label.font = Font(
#         bold=True,
#         color=LTPOMS_YELLOW,
#     )

#     summary_label.fill = PatternFill(
#         fill_type="solid",
#         fgColor=LTPOMS_GREEN,
#     )

#     summary_label.alignment = Alignment(
#         horizontal="center",
#     )

#     if total_required > 0:

#         overall_compliance = (
#             total_submitted
#             / total_required
#         )

#     else:

#         overall_compliance = 0

#     summary_compliance = worksheet.cell(
#         row=summary_row,
#         column=last_column,
#         value=overall_compliance,
#     )

#     summary_compliance.number_format = (
#         "0.0%"
#     )

#     summary_compliance.font = Font(
#         bold=True,
#         color=LTPOMS_GREEN,
#     )

#     summary_compliance.alignment = Alignment(
#         horizontal="center",
#     )

#     # =========================================================================
#     # COLUMN WIDTHS
#     # =========================================================================

#     worksheet.column_dimensions[
#         "A"
#     ].width = 28

#     worksheet.column_dimensions[
#         "B"
#     ].width = 14

#     for day_number in days:

#         column_letter = (
#             get_column_letter(
#                 day_number + 2
#             )
#         )

#         worksheet.column_dimensions[
#             column_letter
#         ].width = 7

#     worksheet.column_dimensions[
#         get_column_letter(
#             filled_column
#         )
#     ].width = 10

#     worksheet.column_dimensions[
#         get_column_letter(
#             required_column
#         )
#     ].width = 11

#     worksheet.column_dimensions[
#         get_column_letter(
#             compliance_column
#         )
#     ].width = 14

#     # =========================================================================
#     # EXCEL VIEW SETTINGS
#     # =========================================================================

#     worksheet.freeze_panes = "C5"

#     worksheet.auto_filter.ref = (
#         f"A4:"
#         f"{get_column_letter(last_column)}"
#         f"{current_row - 1}"
#     )

#     worksheet.sheet_view.showGridLines = (
#         False
#     )

#     # =========================================================================
#     # PRINT SETTINGS
#     # =========================================================================

#     worksheet.page_setup.orientation = (
#         "landscape"
#     )

#     worksheet.page_setup.paperSize = (
#         worksheet.PAPERSIZE_A4
#     )

#     worksheet.page_setup.fitToWidth = 1

#     worksheet.page_setup.fitToHeight = 0

#     worksheet.sheet_properties.pageSetUpPr.fitToPage = (
#         True
#     )

#     worksheet.print_title_rows = (
#         "1:4"
#     )

#     worksheet.print_options.horizontalCentered = (
#         True
#     )

#     # =========================================================================
#     # SAVE WORKBOOK
#     # =========================================================================

#     output = BytesIO()

#     workbook.save(output)

#     output.seek(0)

#     # =========================================================================
#     # RESPONSE
#     # =========================================================================

#     filename = (
#         f"LTPOMS_BBS_Compliance_"
#         f"{selected_year}_"
#         f"{selected_month:02d}.xlsx"
#     )

#     response = HttpResponse(
#         output.getvalue(),
#         content_type=(
#             "application/"
#             "vnd.openxmlformats-officedocument."
#             "spreadsheetml.sheet"
#         ),
#     )

#     response[
#         "Content-Disposition"
#     ] = (
#         f'attachment; filename="{filename}"'
#     )

#     return response

# =============================================================================
# BBS MONTHLY COMPLIANCE EXCEL EXPORT
# =============================================================================


@staff_required
def bbs_monthly_export(request):
    """
    Export monthly BBS submission status as an Excel .xlsx file.

    Population:
        Only employees/card numbers that have submitted at least
        one BBS response through the BBS form.

    Output:
        Employee Name
        Card No.
        Date-wise status
        Filled Days
        Required Days
        Compliance %

    Status:
        YES = BBS submitted
        NO  = No BBS submission
        -   = Future date

    Note:
        Because there is currently no Employee-master dependency,
        an employee/card number with no BBS submission in the
        selected month cannot appear in this report.
    """

    today = timezone.localdate()

    # =========================================================================
    # PERIOD
    # =========================================================================

    try:
        selected_year = int(
            request.GET.get(
                "year",
                today.year,
            )
        )
    except (TypeError, ValueError):
        selected_year = today.year

    try:
        selected_month = int(
            request.GET.get(
                "month",
                today.month,
            )
        )
    except (TypeError, ValueError):
        selected_month = today.month

    if not 1 <= selected_month <= 12:
        selected_month = today.month

    if (
        selected_year < 2000
        or selected_year > today.year
    ):
        selected_year = today.year

    # =========================================================================
    # MONTH INFORMATION
    # =========================================================================

    days_in_month = calendar.monthrange(
        selected_year,
        selected_month,
    )[1]

    days = list(
        range(
            1,
            days_in_month + 1,
        )
    )

    month_name = calendar.month_name[
        selected_month
    ]

    selected_month_start = date(
        selected_year,
        selected_month,
        1,
    )

    current_month_start = date(
        today.year,
        today.month,
        1,
    )

    # =========================================================================
    # APPLICABLE DAYS
    # =========================================================================

    if selected_month_start > current_month_start:
        applicable_days = 0

    elif (
        selected_year == today.year
        and selected_month == today.month
    ):
        applicable_days = today.day

    else:
        applicable_days = days_in_month

    # =========================================================================
    # BBS RESPONSES
    # =========================================================================

    observations = (
        BBSObservation.objects
        .filter(
            observation_date__year=
                selected_year,
            observation_date__month=
                selected_month,
        )
        .only(
            "card_no",
            "employee_name",
            "observation_date",
        )
        .order_by(
            "card_no",
            "observation_date",
            "submitted_at",
        )
    )

    # =========================================================================
    # BUILD RESPONDENT LOOKUP
    #
    # respondents:
    # {
    #     "12345": {
    #         "employee_name": "Employee A",
    #         "days": {1, 2, 3},
    #     }
    # }
    # =========================================================================

    respondents = {}

    for observation in observations:

        card_no = (
            observation.card_no
            .strip()
            .upper()
        )

        employee_name = (
            observation.employee_name
            .strip()
        )

        if card_no not in respondents:
            respondents[card_no] = {
                "employee_name":
                    employee_name,

                "days":
                    set(),
            }

        # Keep the latest submitted name for the same Card No.
        respondents[
            card_no
        ][
            "employee_name"
        ] = employee_name

        respondents[
            card_no
        ][
            "days"
        ].add(
            observation
            .observation_date
            .day
        )

    # =========================================================================
    # WORKBOOK
    # =========================================================================

    workbook = Workbook()

    worksheet = workbook.active

    worksheet.title = (
        "BBS Compliance"
    )

    # =========================================================================
    # COLORS
    # =========================================================================

    LTPOMS_GREEN = "334D42"
    LTPOMS_YELLOW = "FFEB00"

    WHITE = "FFFFFF"

    LIGHT_GREEN = "E8F5E9"
    GREEN_TEXT = "198754"

    LIGHT_RED = "FDECEC"
    RED_TEXT = "DC2626"

    LIGHT_GREY = "F3F4F6"
    GREY_TEXT = "808080"

    ORANGE_TEXT = "D97706"

    BORDER_COLOR = "D9D9D9"

    # =========================================================================
    # BORDER
    # =========================================================================

    thin_border = Border(
        left=Side(
            style="thin",
            color=BORDER_COLOR,
        ),
        right=Side(
            style="thin",
            color=BORDER_COLOR,
        ),
        top=Side(
            style="thin",
            color=BORDER_COLOR,
        ),
        bottom=Side(
            style="thin",
            color=BORDER_COLOR,
        ),
    )

    # =========================================================================
    # COLUMN POSITIONS
    # =========================================================================

    filled_column = (
        days_in_month + 3
    )

    required_column = (
        filled_column + 1
    )

    compliance_column = (
        required_column + 1
    )

    last_column = (
        compliance_column
    )

    # =========================================================================
    # TITLE
    # =========================================================================

    worksheet.merge_cells(
        start_row=1,
        start_column=1,
        end_row=1,
        end_column=last_column,
    )

    title_cell = worksheet.cell(
        row=1,
        column=1,
    )

    title_cell.value = (
        "LTPOMS - BBS Monthly Compliance"
    )

    title_cell.font = Font(
        bold=True,
        size=16,
        color=LTPOMS_YELLOW,
    )

    title_cell.fill = PatternFill(
        fill_type="solid",
        fgColor=LTPOMS_GREEN,
    )

    title_cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    worksheet.row_dimensions[1].height = 28

    # =========================================================================
    # PERIOD
    # =========================================================================

    worksheet.merge_cells(
        start_row=2,
        start_column=1,
        end_row=2,
        end_column=last_column,
    )

    period_cell = worksheet.cell(
        row=2,
        column=1,
    )

    period_cell.value = (
        f"Behaviour Based Safety Programme | "
        f"{month_name} {selected_year}"
    )

    period_cell.font = Font(
        bold=True,
        color=LTPOMS_GREEN,
    )

    period_cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    # =========================================================================
    # HEADERS
    # =========================================================================

    header_row = 4

    headers = [
        "Employee Name",
        "Card No.",
    ]

    for day_number in days:
        headers.append(
            f"{day_number:02d}"
        )

    headers.extend(
        [
            "Filled",
            "Required",
            "Compliance %",
        ]
    )

    for column_number, header in enumerate(
        headers,
        start=1,
    ):

        cell = worksheet.cell(
            row=header_row,
            column=column_number,
            value=header,
        )

        cell.font = Font(
            bold=True,
            color=WHITE,
        )

        cell.fill = PatternFill(
            fill_type="solid",
            fgColor=LTPOMS_GREEN,
        )

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

        cell.border = thin_border

    worksheet.row_dimensions[
        header_row
    ].height = 24

    # =========================================================================
    # DATA
    # =========================================================================

    current_row = (
        header_row + 1
    )

    total_submitted = 0
    total_required = 0

    sorted_respondents = sorted(
        respondents.items(),
        key=lambda item: (
            item[1]["employee_name"].lower(),
            item[0],
        ),
    )

    for (
        card_no,
        respondent,
    ) in sorted_respondents:

        employee_name = respondent[
            "employee_name"
        ]

        employee_submission_days = respondent[
            "days"
        ]

        # ---------------------------------------------------------------------
        # EMPLOYEE NAME
        # ---------------------------------------------------------------------

        employee_cell = worksheet.cell(
            row=current_row,
            column=1,
            value=employee_name,
        )

        # ---------------------------------------------------------------------
        # CARD NO.
        # ---------------------------------------------------------------------

        card_cell = worksheet.cell(
            row=current_row,
            column=2,
            value=card_no,
        )

        employee_cell.alignment = Alignment(
            vertical="center",
        )

        card_cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

        submitted_count = 0

        # ---------------------------------------------------------------------
        # DAY-WISE STATUS
        # ---------------------------------------------------------------------

        for day_number in days:

            day_date = date(
                selected_year,
                selected_month,
                day_number,
            )

            column_number = (
                day_number + 2
            )

            cell = worksheet.cell(
                row=current_row,
                column=column_number,
            )

            # FUTURE
            if day_date > today:

                cell.value = "-"

                cell.fill = PatternFill(
                    fill_type="solid",
                    fgColor=LIGHT_GREY,
                )

                cell.font = Font(
                    color=GREY_TEXT,
                )

            # SUBMITTED
            elif (
                day_number
                in employee_submission_days
            ):

                cell.value = "YES"

                submitted_count += 1

                cell.fill = PatternFill(
                    fill_type="solid",
                    fgColor=LIGHT_GREEN,
                )

                cell.font = Font(
                    bold=True,
                    color=GREEN_TEXT,
                )

            # NOT SUBMITTED
            else:

                cell.value = "NO"

                cell.fill = PatternFill(
                    fill_type="solid",
                    fgColor=LIGHT_RED,
                )

                cell.font = Font(
                    bold=True,
                    color=RED_TEXT,
                )

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

            cell.border = thin_border

        # ---------------------------------------------------------------------
        # COMPLIANCE
        # ---------------------------------------------------------------------

        if applicable_days > 0:

            compliance_percentage = round(
                (
                    submitted_count
                    / applicable_days
                )
                * 100,
                1,
            )

        else:

            compliance_percentage = 0.0

        # ---------------------------------------------------------------------
        # FILLED
        # ---------------------------------------------------------------------

        worksheet.cell(
            row=current_row,
            column=filled_column,
            value=submitted_count,
        )

        # ---------------------------------------------------------------------
        # REQUIRED
        # ---------------------------------------------------------------------

        worksheet.cell(
            row=current_row,
            column=required_column,
            value=applicable_days,
        )

        # ---------------------------------------------------------------------
        # COMPLIANCE %
        # ---------------------------------------------------------------------

        compliance_cell = worksheet.cell(
            row=current_row,
            column=compliance_column,
            value=(
                compliance_percentage
                / 100
            ),
        )

        compliance_cell.number_format = (
            "0.0%"
        )

        if compliance_percentage >= 90:

            compliance_cell.font = Font(
                bold=True,
                color=GREEN_TEXT,
            )

        elif compliance_percentage >= 75:

            compliance_cell.font = Font(
                bold=True,
                color=ORANGE_TEXT,
            )

        else:

            compliance_cell.font = Font(
                bold=True,
                color=RED_TEXT,
            )

        # ---------------------------------------------------------------------
        # ROW FORMATTING
        # ---------------------------------------------------------------------

        for column_number in range(
            1,
            last_column + 1,
        ):

            cell = worksheet.cell(
                row=current_row,
                column=column_number,
            )

            cell.border = thin_border

            if column_number > 2:

                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                )

        total_submitted += (
            submitted_count
        )

        total_required += (
            applicable_days
        )

        current_row += 1

    # =========================================================================
    # OVERALL COMPLIANCE
    # =========================================================================

    summary_row = (
        current_row + 1
    )

    worksheet.merge_cells(
        start_row=summary_row,
        start_column=1,
        end_row=summary_row,
        end_column=2,
    )

    summary_label = worksheet.cell(
        row=summary_row,
        column=1,
        value="Overall Compliance",
    )

    summary_label.font = Font(
        bold=True,
        color=LTPOMS_YELLOW,
    )

    summary_label.fill = PatternFill(
        fill_type="solid",
        fgColor=LTPOMS_GREEN,
    )

    summary_label.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    if total_required > 0:

        overall_compliance = (
            total_submitted
            / total_required
        )

    else:

        overall_compliance = 0

    summary_compliance = worksheet.cell(
        row=summary_row,
        column=last_column,
        value=overall_compliance,
    )

    summary_compliance.number_format = (
        "0.0%"
    )

    summary_compliance.font = Font(
        bold=True,
        color=LTPOMS_GREEN,
    )

    summary_compliance.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    # =========================================================================
    # COLUMN WIDTHS
    # =========================================================================

    worksheet.column_dimensions[
        "A"
    ].width = 28

    worksheet.column_dimensions[
        "B"
    ].width = 14

    for day_number in days:

        column_letter = (
            get_column_letter(
                day_number + 2
            )
        )

        worksheet.column_dimensions[
            column_letter
        ].width = 7

    worksheet.column_dimensions[
        get_column_letter(
            filled_column
        )
    ].width = 10

    worksheet.column_dimensions[
        get_column_letter(
            required_column
        )
    ].width = 11

    worksheet.column_dimensions[
        get_column_letter(
            compliance_column
        )
    ].width = 14

    # =========================================================================
    # VIEW SETTINGS
    # =========================================================================

    worksheet.freeze_panes = "C5"

    if respondents:

        worksheet.auto_filter.ref = (
            f"A4:"
            f"{get_column_letter(last_column)}"
            f"{current_row - 1}"
        )

    worksheet.sheet_view.showGridLines = (
        False
    )

    # =========================================================================
    # PRINT SETTINGS
    # =========================================================================

    worksheet.page_setup.orientation = (
        "landscape"
    )

    worksheet.page_setup.paperSize = (
        worksheet.PAPERSIZE_A4
    )

    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0

    worksheet.sheet_properties.pageSetUpPr.fitToPage = (
        True
    )

    worksheet.print_title_rows = (
        "1:4"
    )

    worksheet.print_options.horizontalCentered = (
        True
    )

    # =========================================================================
    # SAVE
    # =========================================================================

    output = BytesIO()

    workbook.save(
        output
    )

    output.seek(0)

    # =========================================================================
    # RESPONSE
    # =========================================================================

    filename = (
        f"LTPOMS_BBS_Compliance_"
        f"{selected_year}_"
        f"{selected_month:02d}.xlsx"
    )

    response = HttpResponse(
        output.getvalue(),
        content_type=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    response[
        "Content-Disposition"
    ] = (
        f'attachment; filename="{filename}"'
    )

    return response

from django.db.models import Q


# =============================================================================
# BBS FORM RESPONSES
# =============================================================================


@staff_required
def bbs_response_list(request):
    """
    Protected list of BBS responses submitted through
    the public BBS Observation form.

    Supports:
        - Search
        - Month filter
        - Year filter
        - Shift filter
        - Behaviour filter
        - At-Risk filtering
    """

    today = timezone.localdate()

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    shift_filter = (
        request.GET.get(
            "shift",
            "",
        ).strip()
    )

    behaviour_filter = (
        request.GET.get(
            "behaviour",
            "",
        ).strip()
    )

    risk_filter = (
        request.GET.get(
            "risk",
            "",
        ).strip()
    )

    # =========================================================================
    # MONTH / YEAR
    # =========================================================================

    try:
        selected_month = int(
            request.GET.get(
                "month",
                today.month,
            )
        )
    except (TypeError, ValueError):
        selected_month = today.month

    try:
        selected_year = int(
            request.GET.get(
                "year",
                today.year,
            )
        )
    except (TypeError, ValueError):
        selected_year = today.year

    if not 1 <= selected_month <= 12:
        selected_month = today.month

    if (
        selected_year < 2000
        or selected_year > today.year
    ):
        selected_year = today.year

    # =========================================================================
    # QUERYSET
    # =========================================================================

    responses = (
        BBSObservation.objects
        .filter(
            observation_date__year=selected_year,
            observation_date__month=selected_month,
        )
        .order_by(
            "-observation_date",
            "-observation_time",
        )
    )

    # =========================================================================
    # SEARCH
    # =========================================================================

    if search_query:
        responses = responses.filter(
            Q(
                employee_name__icontains=search_query
            )
            | Q(
                card_no__icontains=search_query
            )
            | Q(
                area__icontains=search_query
            )
            | Q(
                observer_name__icontains=search_query
            )
            | Q(
                behaviour_description__icontains=search_query
            )
            | Q(
                corrective_action__icontains=search_query
            )
        )

    # =========================================================================
    # SHIFT
    # =========================================================================

    if shift_filter:
        responses = responses.filter(
            shift=shift_filter
        )

    # =========================================================================
    # BEHAVIOUR
    # =========================================================================

    if behaviour_filter:
        responses = responses.filter(
            behaviour_type=behaviour_filter
        )

    # =========================================================================
    # AT-RISK
    # =========================================================================

    if risk_filter == "yes":

        responses = responses.filter(
            Q(
                behaviour_type=(
                    BBSObservation
                    .BehaviourType
                    .AT_RISK
                )
            )
            | Q(
                ppe_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )
            | Q(
                guarding_loto_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )
            | Q(
                ergonomics_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )
            | Q(
                tools_equipment_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )
            | Q(
                housekeeping_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )
            | Q(
                permit_procedure_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )
        )

    # =========================================================================
    # FILTER OPTIONS
    # =========================================================================

    months = [
        {
            "number": month_number,
            "name": calendar.month_name[
                month_number
            ],
        }
        for month_number in range(1, 13)
    ]

    years = list(
        range(
            today.year,
            2024,
            -1,
        )
    )

    context = {
        "responses": responses,

        "search_query": search_query,
        "shift_filter": shift_filter,
        "behaviour_filter": behaviour_filter,
        "risk_filter": risk_filter,

        "selected_month": selected_month,
        "selected_year": selected_year,

        "months": months,
        "years": years,

        "shift_choices":
            BBSObservation.Shift.choices,

        "behaviour_choices":
            BBSObservation
            .BehaviourType
            .choices,

        "response_count":
            responses.count(),
    }

    return render(
        request,
        "safety_bbs/bbs_response_list.html",
        context,
    )
    
# =============================================================================
# BBS RESPONSE DETAIL
# =============================================================================

@staff_required
def bbs_response_detail(
    request,
    response_id,
):
    """
    Protected read-only view of an individual
    submitted BBS Observation.
    """

    observation = get_object_or_404(
        BBSObservation,
        pk=response_id,
    )

    context = {
        "observation": observation,
        "page_title": "BBS Response Detail",
    }

    return render(
        request,
        "safety_bbs/bbs_response_detail.html",
        context,
    )

# =============================================================================
# BBS RESPONSE DETAILS EXCEL EXPORT
# =============================================================================


@staff_required
def bbs_response_export(request):
    """
    Export detailed BBS form responses to Excel.

    The export uses the same filters as the BBS Response List:
        - Search
        - Month
        - Year
        - Shift
        - Behaviour
        - At-Risk

    Each BBSObservation is exported as one Excel row.
    """

    today = timezone.localdate()

    # =========================================================================
    # FILTER VALUES
    # =========================================================================

    search_query = (
        request.GET.get(
            "search",
            "",
        ).strip()
    )

    shift_filter = (
        request.GET.get(
            "shift",
            "",
        ).strip()
    )

    behaviour_filter = (
        request.GET.get(
            "behaviour",
            "",
        ).strip()
    )

    risk_filter = (
        request.GET.get(
            "risk",
            "",
        ).strip()
    )

    # =========================================================================
    # MONTH / YEAR
    # =========================================================================

    try:
        selected_month = int(
            request.GET.get(
                "month",
                today.month,
            )
        )
    except (TypeError, ValueError):
        selected_month = today.month

    try:
        selected_year = int(
            request.GET.get(
                "year",
                today.year,
            )
        )
    except (TypeError, ValueError):
        selected_year = today.year

    if not 1 <= selected_month <= 12:
        selected_month = today.month

    if (
        selected_year < 2000
        or selected_year > today.year
    ):
        selected_year = today.year

    month_name = calendar.month_name[
        selected_month
    ]

    # =========================================================================
    # BASE QUERYSET
    # =========================================================================

    responses = (
        BBSObservation.objects
        .filter(
            observation_date__year=selected_year,
            observation_date__month=selected_month,
        )
        .order_by(
            "observation_date",
            "observation_time",
            "card_no",
        )
    )

    # =========================================================================
    # SEARCH
    # =========================================================================

    if search_query:

        responses = responses.filter(
            Q(
                employee_name__icontains=search_query
            )
            | Q(
                card_no__icontains=search_query
            )
            | Q(
                area__icontains=search_query
            )
            | Q(
                observer_name__icontains=search_query
            )
            | Q(
                activator__icontains=search_query
            )
            | Q(
                behaviour_description__icontains=search_query
            )
            | Q(
                feedback__icontains=search_query
            )
            | Q(
                corrective_action__icontains=search_query
            )
        )

    # =========================================================================
    # SHIFT
    # =========================================================================

    if shift_filter:

        responses = responses.filter(
            shift=shift_filter
        )

    # =========================================================================
    # BEHAVIOUR
    # =========================================================================

    if behaviour_filter:

        responses = responses.filter(
            behaviour_type=behaviour_filter
        )

    # =========================================================================
    # AT-RISK
    # =========================================================================

    if risk_filter == "yes":

        responses = responses.filter(

            Q(
                behaviour_type=(
                    BBSObservation
                    .BehaviourType
                    .AT_RISK
                )
            )

            | Q(
                ppe_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )

            | Q(
                guarding_loto_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )

            | Q(
                ergonomics_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )

            | Q(
                tools_equipment_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )

            | Q(
                housekeeping_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )

            | Q(
                permit_procedure_status=(
                    BBSObservation
                    .ChecklistStatus
                    .AT_RISK
                )
            )
        )

    # =========================================================================
    # WORKBOOK
    # =========================================================================

    workbook = Workbook()

    worksheet = workbook.active

    worksheet.title = (
        "BBS Responses"
    )

    # =========================================================================
    # LTPOMS COLORS
    # =========================================================================

    LTPOMS_GREEN = "334D42"
    LTPOMS_YELLOW = "FFEB00"

    WHITE = "FFFFFF"

    LIGHT_GREEN = "E8F5E9"
    GREEN_TEXT = "198754"

    LIGHT_RED = "FDECEC"
    RED_TEXT = "DC2626"

    BORDER_COLOR = "D9D9D9"

    thin_border = Border(
        left=Side(
            style="thin",
            color=BORDER_COLOR,
        ),
        right=Side(
            style="thin",
            color=BORDER_COLOR,
        ),
        top=Side(
            style="thin",
            color=BORDER_COLOR,
        ),
        bottom=Side(
            style="thin",
            color=BORDER_COLOR,
        ),
    )

    # =========================================================================
    # HEADERS
    # =========================================================================

    headers = [
        "Response ID",
        "Observation Date",
        "Observation Time",
        "Employee Name",
        "Card No.",
        "Shift",
        "Area",
        "Observer Name",

        "Activator",

        "Behaviour Type",
        "Behaviour Categories",
        "Behaviour Description",

        "Consequences",
        "Feedback",

        "PPE Status",
        "Guarding / LOTO Status",
        "Ergonomics Status",
        "Tools / Equipment Status",
        "Housekeeping Status",
        "Permit / Procedure Status",

        "Overall At-Risk",

        "Root Causes",
        "Other Root Cause",
        "Corrective / Preventive Action",

        "Observer Sign",
        "Supervisor Sign",

        "Submitted At",
        "Last Updated",
    ]

    last_column = len(headers)

    # =========================================================================
    # TITLE
    # =========================================================================

    worksheet.merge_cells(
        start_row=1,
        start_column=1,
        end_row=1,
        end_column=last_column,
    )

    title_cell = worksheet.cell(
        row=1,
        column=1,
    )

    title_cell.value = (
        "LTPOMS - BBS Form Responses"
    )

    title_cell.font = Font(
        bold=True,
        size=16,
        color=LTPOMS_YELLOW,
    )

    title_cell.fill = PatternFill(
        fill_type="solid",
        fgColor=LTPOMS_GREEN,
    )

    title_cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    worksheet.row_dimensions[1].height = 28

    # =========================================================================
    # PERIOD
    # =========================================================================

    worksheet.merge_cells(
        start_row=2,
        start_column=1,
        end_row=2,
        end_column=last_column,
    )

    period_cell = worksheet.cell(
        row=2,
        column=1,
    )

    period_cell.value = (
        f"Behaviour Based Safety Programme | "
        f"{month_name} {selected_year}"
    )

    period_cell.font = Font(
        bold=True,
        color=LTPOMS_GREEN,
    )

    period_cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    # =========================================================================
    # TABLE HEADER
    # =========================================================================

    header_row = 4

    for column_number, header in enumerate(
        headers,
        start=1,
    ):

        cell = worksheet.cell(
            row=header_row,
            column=column_number,
            value=header,
        )

        cell.font = Font(
            bold=True,
            color=WHITE,
        )

        cell.fill = PatternFill(
            fill_type="solid",
            fgColor=LTPOMS_GREEN,
        )

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

        cell.border = thin_border

    worksheet.row_dimensions[
        header_row
    ].height = 40

    # =========================================================================
    # DATA
    # =========================================================================

    current_row = (
        header_row + 1
    )

    for observation in responses:

        behaviour_categories = ", ".join(
            observation.behaviour_categories
            or []
        )

        consequences = ", ".join(
            observation.consequences
            or []
        )

        root_causes = ", ".join(
            observation.root_causes
            or []
        )

        overall_at_risk = (
            "YES"
            if observation.is_at_risk
            else "NO"
        )

        values = [
            observation.pk,

            observation.observation_date,

            observation.observation_time,

            observation.employee_name,

            observation.card_no,

            observation.get_shift_display(),

            observation.area,

            observation.observer_name,

            observation.activator,

            observation.get_behaviour_type_display(),

            behaviour_categories,

            observation.behaviour_description,

            consequences,

            observation.feedback,

            observation.get_ppe_status_display(),

            observation.get_guarding_loto_status_display(),

            observation.get_ergonomics_status_display(),

            observation.get_tools_equipment_status_display(),

            observation.get_housekeeping_status_display(),

            observation.get_permit_procedure_status_display(),

            overall_at_risk,

            root_causes,

            observation.root_cause_other,

            observation.corrective_action,

            observation.observer_sign,

            observation.supervisor_sign,

            timezone.localtime(
                observation.submitted_at
            ).replace(
                tzinfo=None
            ),

            timezone.localtime(
                observation.updated_at
            ).replace(
                tzinfo=None
            ),
        ]

        for column_number, value in enumerate(
            values,
            start=1,
        ):

            cell = worksheet.cell(
                row=current_row,
                column=column_number,
                value=value,
            )

            cell.border = thin_border

            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True,
            )

        # ---------------------------------------------------------------------
        # DATE / TIME FORMATTING
        # ---------------------------------------------------------------------

        worksheet.cell(
            row=current_row,
            column=2,
        ).number_format = (
            "dd-mmm-yyyy"
        )

        worksheet.cell(
            row=current_row,
            column=3,
        ).number_format = (
            "hh:mm"
        )

        worksheet.cell(
            row=current_row,
            column=27,
        ).number_format = (
            "dd-mmm-yyyy hh:mm"
        )

        worksheet.cell(
            row=current_row,
            column=28,
        ).number_format = (
            "dd-mmm-yyyy hh:mm"
        )

        # ---------------------------------------------------------------------
        # AT-RISK COLOR
        # ---------------------------------------------------------------------

        risk_cell = worksheet.cell(
            row=current_row,
            column=21,
        )

        if observation.is_at_risk:

            risk_cell.fill = PatternFill(
                fill_type="solid",
                fgColor=LIGHT_RED,
            )

            risk_cell.font = Font(
                bold=True,
                color=RED_TEXT,
            )

        else:

            risk_cell.fill = PatternFill(
                fill_type="solid",
                fgColor=LIGHT_GREEN,
            )

            risk_cell.font = Font(
                bold=True,
                color=GREEN_TEXT,
            )

        risk_cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

        current_row += 1

    # =========================================================================
    # COLUMN WIDTHS
    # =========================================================================

    widths = {
        1: 12,   # Response ID
        2: 15,   # Date
        3: 12,   # Time
        4: 24,   # Employee
        5: 14,   # Card
        6: 10,   # Shift
        7: 20,   # Area
        8: 22,   # Observer
        9: 32,   # Activator
        10: 18,  # Behaviour
        11: 30,  # Categories
        12: 40,  # Behaviour description
        13: 34,  # Consequences
        14: 40,  # Feedback

        15: 18,
        16: 22,
        17: 20,
        18: 22,
        19: 20,
        20: 22,

        21: 15,  # Overall Risk

        22: 30,  # Root causes
        23: 28,
        24: 40,

        25: 20,
        26: 20,

        27: 20,
        28: 20,
    }

    for column_number, width in widths.items():

        worksheet.column_dimensions[
            get_column_letter(
                column_number
            )
        ].width = width

    # =========================================================================
    # EXCEL VIEW SETTINGS
    # =========================================================================

    worksheet.freeze_panes = (
        "A5"
    )

    if current_row > 5:

        worksheet.auto_filter.ref = (
            f"A4:"
            f"{get_column_letter(last_column)}"
            f"{current_row - 1}"
        )

    worksheet.sheet_view.showGridLines = (
        False
    )

    # =========================================================================
    # PRINT SETTINGS
    # =========================================================================

    worksheet.page_setup.orientation = (
        "landscape"
    )

    worksheet.page_setup.paperSize = (
        worksheet.PAPERSIZE_A4
    )

    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0

    worksheet.sheet_properties.pageSetUpPr.fitToPage = (
        True
    )

    worksheet.print_title_rows = (
        "1:4"
    )

    # =========================================================================
    # SAVE
    # =========================================================================

    output = BytesIO()

    workbook.save(
        output
    )

    output.seek(0)

    filename = (
        f"LTPOMS_BBS_Responses_"
        f"{selected_year}_"
        f"{selected_month:02d}.xlsx"
    )

    response = HttpResponse(
        output.getvalue(),
        content_type=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    response[
        "Content-Disposition"
    ] = (
        f'attachment; filename="{filename}"'
    )

    return response