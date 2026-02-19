"""Builds auto-response emails using case data from Filevine."""

import logging

from jinja2 import Template

from config import Config
from filevine_scraper import CaseInfo

logger = logging.getLogger(__name__)

# Response when a matching case is found in Filevine
CASE_FOUND_TEMPLATE = Template("""\
<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
<p>Dear {{ sender_name }},</p>

<p>Thank you for contacting <strong>{{ firm_name }}</strong>. We have received your email
and wanted to provide you with an update on your case.</p>

<table style="border-collapse: collapse; margin: 20px 0; width: 100%; max-width: 500px;">
  <tr style="background-color: #f8f9fa;">
    <td style="padding: 10px 15px; border: 1px solid #dee2e6; font-weight: bold;">Case</td>
    <td style="padding: 10px 15px; border: 1px solid #dee2e6;">{{ case_info.project_name }}</td>
  </tr>
  {% if case_info.case_number %}
  <tr>
    <td style="padding: 10px 15px; border: 1px solid #dee2e6; font-weight: bold;">Case Number</td>
    <td style="padding: 10px 15px; border: 1px solid #dee2e6;">{{ case_info.case_number }}</td>
  </tr>
  {% endif %}
  <tr style="background-color: #f8f9fa;">
    <td style="padding: 10px 15px; border: 1px solid #dee2e6; font-weight: bold;">Current Phase</td>
    <td style="padding: 10px 15px; border: 1px solid #dee2e6;">{{ case_info.phase or "In Progress" }}</td>
  </tr>
</table>

<p>A member of our team will review your message and respond as soon as possible.
If your matter is urgent, please call us directly at <strong>{{ firm_phone }}</strong>.</p>

<p>Best regards,<br>
<strong>{{ firm_name }}</strong><br>
{{ firm_phone }}<br>
{{ firm_email }}</p>

<hr style="border: none; border-top: 1px solid #eee; margin-top: 30px;">
<p style="font-size: 12px; color: #888;">
This is an automated response. Please do not reply to this message.
A team member will follow up with you directly.
</p>
</body>
</html>
""")

# Response when no matching case is found
NO_CASE_TEMPLATE = Template("""\
<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
<p>Dear {{ sender_name }},</p>

<p>Thank you for contacting <strong>{{ firm_name }}</strong>. We have received your email
and a member of our team will review it and respond to you as soon as possible.</p>

<p>If your matter is urgent, please call us directly at <strong>{{ firm_phone }}</strong>.</p>

<p>Best regards,<br>
<strong>{{ firm_name }}</strong><br>
{{ firm_phone }}<br>
{{ firm_email }}</p>

<hr style="border: none; border-top: 1px solid #eee; margin-top: 30px;">
<p style="font-size: 12px; color: #888;">
This is an automated response. Please do not reply to this message.
A team member will follow up with you directly.
</p>
</body>
</html>
""")


def build_response(sender_name: str, case_info: CaseInfo | None) -> str:
    """Build an HTML email response based on available case information.

    Args:
        sender_name: The name of the person who sent the email.
        case_info: Case data from Filevine, or None if lookup failed.

    Returns:
        HTML string for the reply email body.
    """
    context = {
        "sender_name": sender_name or "Valued Client",
        "firm_name": Config.FIRM_NAME,
        "firm_phone": Config.FIRM_PHONE,
        "firm_email": Config.FIRM_EMAIL,
    }

    if case_info and case_info.found:
        context["case_info"] = case_info
        html = CASE_FOUND_TEMPLATE.render(**context)
        logger.info("Built case-found response for %s (case: %s)", sender_name, case_info.project_name)
    else:
        html = NO_CASE_TEMPLATE.render(**context)
        logger.info("Built generic response for %s (no case found)", sender_name)

    return html
