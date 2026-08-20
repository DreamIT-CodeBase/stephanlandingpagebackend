import os
import requests
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from app.config import settings
from app.auth import get_access_token
from app.models import BookDemo, DeletionRequest

logger = logging.getLogger(__name__)

# Setup Jinja2 templates directory path
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def render_template(template_name: str, **kwargs) -> str:
    template = jinja_env.get_template(template_name)
    return template.render(**kwargs)


def send_graph_email(to_email: str, subject: str, html_content: str, cc_emails: list = None):
    token = get_access_token()
    sender = settings.MAIL_SENDER_EMAIL or settings.MAILBOX
    if not sender:
        raise RuntimeError("MAIL_SENDER_EMAIL is not configured")
    url = f"{settings.GRAPH_BASE}/users/{sender}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    message_payload = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": html_content
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "address": to_email
                }
            }
        ]
    }

    if cc_emails:
        message_payload["ccRecipients"] = [
            {
                "emailAddress": {
                    "address": cc
                }
            }
            for cc in cc_emails
        ]

    payload = {
        "message": message_payload,
        "saveToSentItems": "true"
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code >= 400:
        raise Exception(f"Graph API Mail Send Error {response.status_code}: {response.text}")
    response.raise_for_status()


def send_smtp_email(to_email: str, subject: str, html_content: str, cc_emails: list = None):
    smtp_host = "smtp.office365.com"  # default for dreamitcs.com (Office 365)
    smtp_port = 587
    smtp_user = settings.SMTP_EMAIL
    smtp_pass = settings.SMTP_PASSWORD
    sender = settings.MAIL_SENDER_EMAIL or smtp_user
    if not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP_EMAIL and SMTP_PASSWORD are required for SMTP delivery")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    recipients = [to_email]

    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)
        recipients.extend(cc_emails)

    part = MIMEText(html_content, "html")
    msg.attach(part)

    logger.info(f"Connecting to SMTP server {smtp_host}:{smtp_port}...")
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender, recipients, msg.as_string())
    logger.info(f"SMTP Email sent successfully to {to_email}")


def dispatch_email(to_email: str, subject: str, html_content: str, cc_emails: list = None):
    mode = str(settings.EMAIL_DELIVERY_MODE).lower()
    if mode == "smtp":
        send_smtp_email(to_email, subject, html_content, cc_emails)
    else:
        send_graph_email(to_email, subject, html_content, cc_emails)


def send_booking_emails(booking: BookDemo):
    # Render variables
    render_vars = {
        "first_name": booking.firstName,
        "last_name": booking.lastName,
        "email": booking.email,
        "suitable_date": booking.suitableDate.strftime("%B %d, %Y"),
        "suitable_time": booking.suitableTime.strftime("%I:%M %p")
    }

    customer_html = render_template("customer_email.html", **render_vars)
    dispatch_email(
        to_email=str(booking.email),
        subject="Demo Booking Confirmation - Social Studying AI",
        html_content=customer_html
    )
    logger.info("Sent confirmation email to customer: %s", booking.email)

    # 2. Send notification email to Admin & CC
    admin_recipient = settings.ADMIN_EMAIL
    if not admin_recipient:
        raise RuntimeError("ADMIN_EMAIL is not configured")
    
    # Parse CC emails list
    cc_list = None
    if settings.CC_EMAILS:
        cc_list = [cc.strip() for cc in settings.CC_EMAILS.split(",") if cc.strip()]

    admin_html = render_template("admin_email.html", **render_vars)
    dispatch_email(
        to_email=admin_recipient,
        subject=f"New Demo Requested: {booking.firstName} {booking.lastName}",
        html_content=admin_html,
        cc_emails=cc_list
    )
    logger.info("Sent admin notification email to %s with CC %s", admin_recipient, cc_list)


def send_deletion_emails(request: DeletionRequest, reference_id: str):
    from datetime import datetime
    request_date = request.requestedAt or datetime.now().strftime("%B %d, %Y at %I:%M %p")

    render_vars = {
        "email": str(request.email),
        "username": request.username or "N/A",
        "reason": request.reason or "Not specified",
        "request_date": request_date,
        "reference_id": reference_id,
    }

    # 1. User confirmation email
    try:
        user_html = render_template("user_deletion_email.html", **render_vars)
        dispatch_email(
            to_email=str(request.email),
            subject="Account Deletion Request Confirmation - Social Studying AI",
            html_content=user_html,
        )
        logger.info("Sent deletion confirmation email to user: %s", request.email)
    except Exception as exc:
        logger.error("User deletion receipt email failed: %s", exc)

    # 2. Admin alert email to socials@socialstudying.ai + CCs
    admin_recipient = settings.ADMIN_EMAIL or "socials@socialstudying.ai"
    cc_list = None
    if settings.CC_EMAILS:
        cc_list = [cc.strip() for cc in settings.CC_EMAILS.split(",") if cc.strip()]

    try:
        admin_html = render_template("admin_deletion_email.html", **render_vars)
        dispatch_email(
            to_email=admin_recipient,
            subject=f"[ACTION REQUIRED] Account Deletion Request: {request.email}",
            html_content=admin_html,
            cc_emails=cc_list,
        )
        logger.info("Sent admin deletion alert to %s with CC %s", admin_recipient, cc_list)
    except Exception as exc:
        logger.error("Admin deletion email failed: %s", exc)

