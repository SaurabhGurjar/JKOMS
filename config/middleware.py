from django.conf import settings
from django.http import StreamingHttpResponse
from .response_branding import get_response_branding_html


class ResponseBrandingMiddleware:
    """
    Insert the JKOMS branding component before the closing body tag of successful HTML responses.
    """

    component_identifier = b"id=\"jkoms-response-branding\""
    closing_body_tag = b"</body>"

    def __init__(self, get_response):
        self.get_response = get_response
        self.component_html = get_response_branding_html()

    def __call__(self, request):
        response = self.get_response(request)

        if not self.should_process(response):
            return response

        content = response.content

        # Prevent duplicate insertion.
        if self.component_identifier in content:
            return response

        insertion_position = content.lower().rfind(self.closing_body_tag)

        # Ignore HTML fragments without a closing body tag.
        if insertion_position == -1:
            return response

        response.content = (
            content[:insertion_position]
            + self.component_html
            + content[insertion_position:]
        )

        # Diagnostic header for browser developer tools.
        response["X-JKOMS-Component"] = "present"
        return response

    @staticmethod
    def should_process(response):
        """
        Process only successful, uncompressed HTML responses.
        """
        enabled = getattr(settings, "JKOMS_RESPONSE_BRANDING_ENABLED", True)
        if not enabled:
            return False

        if isinstance(response, StreamingHttpResponse):
            return False

        if getattr(response, "streaming", False):
            return False

        if response.status_code != 200:
            return False

        if response.get("Content-Encoding"):
            return False

        content_type = response.get("Content-Type", "").lower()
        return "text/html" in content_type
