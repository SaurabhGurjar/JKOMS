from django.shortcuts import render
from django.contrib.auth.decorators import login_required


ftq_report = [
    {
        "date": "01-Sep-2026",
        "total_checked_tyres": 6385,
        "defective_tyres": 82,
        "ftq": 98.72,
    },
    {
        "date": "02-Sep-2026",
        "total_checked_tyres": 6452,
        "defective_tyres": 96,
        "ftq": 98.51,
    },
    {
        "date": "03-Sep-2026",
        "total_checked_tyres": 6318,
        "defective_tyres": 148,
        "ftq": 97.66,
    },
    {
        "date": "04-Sep-2026",
        "total_checked_tyres": 6412,
        "defective_tyres": 235,
        "ftq": 96.33,
    },
    {
        "date": "05-Sep-2026",
        "total_checked_tyres": 6501,
        "defective_tyres": 74,
        "ftq": 98.86,
    },
    {
        "date": "06-Sep-2026",
        "total_checked_tyres": 6355,
        "defective_tyres": 88,
        "ftq": 98.62,
    },
    {
        "date": "07-Sep-2026",
        "total_checked_tyres": 6471,
        "defective_tyres": 157,
        "ftq": 97.57,
    },
    {
        "date": "08-Sep-2026",
        "total_checked_tyres": 6389,
        "defective_tyres": 79,
        "ftq": 98.76,
    },
    {
        "date": "09-Sep-2026",
        "total_checked_tyres": 6422,
        "defective_tyres": 72,
        "ftq": 98.88,
    },
    {
        "date": "10-Sep-2026",
        "total_checked_tyres": 6360,
        "defective_tyres": 191,
        "ftq": 97.00,
    },
    {
        "date": "11-Sep-2026",
        "total_checked_tyres": 6495,
        "defective_tyres": 85,
        "ftq": 98.69,
    },
    {
        "date": "12-Sep-2026",
        "total_checked_tyres": 6374,
        "defective_tyres": 68,
        "ftq": 98.93,
    },
    {
        "date": "13-Sep-2026",
        "total_checked_tyres": 6308,
        "defective_tyres": 228,
        "ftq": 96.39,
    },
    {
        "date": "14-Sep-2026",
        "total_checked_tyres": 6487,
        "defective_tyres": 105,
        "ftq": 98.38,
    },
    {
        "date": "15-Sep-2026",
        "total_checked_tyres": 6396,
        "defective_tyres": 77,
        "ftq": 98.80,
    },
]


total_checked_tyres = sum(
    row["total_checked_tyres"] for row in ftq_report
)

total_defective_tyres = sum(
    row["defective_tyres"] for row in ftq_report
)

overall_ftq = round(
    (
        (total_checked_tyres - total_defective_tyres)
        / total_checked_tyres
    ) * 100,
    2
)

plant_quality_rating = [
    {"department": "Mixing", "rating": 98.4},
    {"department": "Extrusion", "rating": 97.8},
    {"department": "Calendaring", "rating": 98.9},
    {"department": "Bead Preparation", "rating": 96.7},
    {"department": "Bias Cutting", "rating": 97.2},
    {"department": "Tyre Building", "rating": 95.8},
    {"department": "Curing", "rating": 98.1},
    {"department": "Final Inspection", "rating": 99.2},
]

plant_average = round(
sum(item["rating"] for item in plant_quality_rating)
/ len(plant_quality_rating),
2
)

@login_required
def dashboard(request):
    context = {
    "ftq_report": ftq_report,
    "total_checked_tyres": total_checked_tyres,
    "total_defective_tyres": total_defective_tyres,
    "overall_ftq": overall_ftq,
    "plant_quality_rating": plant_quality_rating,
    "plant_average": plant_average,
}

    return render(
        request,
        "quality/dashboard.html",
        context,
    )
    
@login_required
def qms_home(request):
    context = {
        "active_page": "qms",
    }

    return render(
        request,
        "quality/qms/qms_home.html",
        context
    )