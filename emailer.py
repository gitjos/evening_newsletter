"""
Sends the finished HTML newsletter over Gmail SMTP using an app password
(same auth style as the existing google_mail_archiver setup).
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def send_newsletter(
    email_cfg: dict,
    subject: str,
    html_body: str,
    inline_images: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """
    inline_images: list of (content_id, raw_bytes, mime_subtype) e.g.
    ("energy_chart", png_bytes, "image/png"), referenced in the HTML as
    <img src="cid:energy_chart">.
    """
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = email_cfg["sender"]
    msg["To"] = email_cfg["recipient"]

    msg.attach(MIMEText(html_body, "html"))

    for cid, data, mime_type in inline_images or []:
        subtype = mime_type.split("/")[-1]
        image = MIMEImage(data, _subtype=subtype)
        image.add_header("Content-ID", f"<{cid}>")
        image.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtype}")
        msg.attach(image)

    with smtplib.SMTP_SSL(email_cfg["smtp_host"], email_cfg["smtp_port"]) as server:
        server.login(email_cfg["sender"], email_cfg["password"])
        server.sendmail(email_cfg["sender"], [email_cfg["recipient"]], msg.as_string())

    log.info("Newsletter sent to %s", email_cfg["recipient"])
