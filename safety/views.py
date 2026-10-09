from django.shortcuts import redirect


def dashboard(request):
    """
    Safety module landing page.

    Redirects to the protected BBS compliance dashboard.
    """

    return redirect(
        "safety_bbs:bbs_dashboard"
    )