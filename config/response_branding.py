from __future__ import annotations

import base64
from functools import lru_cache
from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_H


_COMPONENT_VALUE = (
    "RGV2ZWxvcGVkIGJ5IFNhdXJhYmggQ2hvdWRoYXJ5IHwg"
    "TFRQIC0gUUEgRnVuY3Rpb24="
)


@lru_cache(maxsize=1)
def get_component_value() -> str:
    """Decode the text stored inside the QR code."""
    encoded_value = "".join(_COMPONENT_VALUE.split())

    return base64.b64decode(
        encoded_value
    ).decode("utf-8")


@lru_cache(maxsize=1)
def get_component_data_uri() -> str:
    """
    Generate the QR code in memory and return it as a PNG data URI.

    No static or media file is created.
    """
    qr_code = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=6,
        border=3,
    )

    qr_code.add_data(get_component_value())
    qr_code.make(fit=True)

    qr_image = qr_code.make_image(
        fill_color="#17365D",
        back_color="#FFFFFF",
    )

    image_buffer = BytesIO()

    qr_image.save(
        image_buffer,
        format="PNG",
    )

    encoded_image = base64.b64encode(
        image_buffer.getvalue()
    ).decode("ascii")

    return f"data:image/png;base64,{encoded_image}"


@lru_cache(maxsize=1)
def get_response_branding_html() -> bytes:
    """
    Return the QR watermark HTML injected into Django responses.
    """
    data_uri = get_component_data_uri()

    markup = f"""
<div
    id="jkoms-response-branding"
    title="JKOMS application information"
    aria-label="JKOMS application information"
>
    {data_uri}
</div>

<style id="jkoms-response-branding-style">
    #jkoms-response-branding {{
        position: fixed !important;
        right: 14px !important;
        bottom: 14px !important;
        z-index: 2147483647 !important;

        display: block !important;
        visibility: visible !important;

        box-sizing: content-box !important;
        width: 54px !important;
        height: 54px !important;
        padding: 4px !important;

        overflow: hidden !important;
        background-color: rgba(255, 255, 255, 0.95) !important;
        border: 1px solid rgba(23, 54, 93, 0.40) !important;
        border-radius: 6px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18) !important;

        opacity: 0.75 !important;
        transition:
            opacity 160ms ease-in-out,
            transform 160ms ease-in-out !important;
    }}

    #jkoms-response-branding:hover {{
        opacity: 1 !important;
        transform: scale(1.08) !important;
    }}

    #jkoms-response-branding img {{
        display: block !important;
        visibility: visible !important;

        width: 54px !important;
        height: 54px !important;

        margin: 0 !important;
        padding: 0 !important;
        border: 0 !important;

        object-fit: contain !important;
        pointer-events: none !important;
        user-select: none !important;
        -webkit-user-drag: none !important;
    }}

    @media (max-width: 576px) {{
        #jkoms-response-branding {{
            right: 8px !important;
            bottom: 8px !important;
            width: 44px !important;
            height: 44px !important;
        }}

        #jkoms-response-branding img {{
            width: 44px !important;
            height: 44px !important;
        }}
    }}

    @media print {{
        #jkoms-response-branding {{
            display: none !important;
        }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        #jkoms-response-branding {{
            transition: none !important;
        }}
    }}
</style>
"""

    return markup.encode("utf-8")