"""Account emails through the EmailJS REST API (free plan: 200 emails/month, 2 templates).

Sending never raises: an email problem must not break signup or leak whether an account
exists. When EmailJS isn't configured, the link is logged instead (local dev and tests only;
production logs never contain a link).
"""

import logging
from dataclasses import dataclass, field
from typing import Literal

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)
EMAILJS_URL = "https://api.emailjs.com/api/v1.0/email/send"

Template = Literal["verify", "reset"]


@dataclass
class Outbox:
    """Last emails "sent" while EmailJS is off; tests read links from here."""

    sent: list[dict[str, str]] = field(default_factory=list)


outbox = Outbox()


async def send_email(template: Template, to_email: str, to_name: str, link: str) -> bool:
    s = get_settings()
    template_id = s.emailjs_template_verify if template == "verify" else s.emailjs_template_reset
    params = {"to_email": to_email, "to_name": to_name, "link": link}
    if not (
        s.emailjs_service_id and s.emailjs_public_key and s.emailjs_private_key and template_id
    ):
        outbox.sent = [*outbox.sent[-19:], {"template": template, **params}]
        if s.environment == "production":
            # never write a working reset link into production logs
            log.warning("EmailJS not configured: %s email to %s not sent", template, to_email)
        else:
            log.warning("email not configured; %s link for %s: %s", template, to_email, link)
        return False
    payload = {
        "service_id": s.emailjs_service_id,
        "template_id": template_id,
        "user_id": s.emailjs_public_key,
        "accessToken": s.emailjs_private_key.get_secret_value(),
        "template_params": params,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(EMAILJS_URL, json=payload)
        if res.status_code != 200:
            log.warning("EmailJS %s: %s", res.status_code, res.text[:200])
            return False
    except httpx.HTTPError as exc:
        log.warning("EmailJS unreachable: %s", exc)
        return False
    return True
