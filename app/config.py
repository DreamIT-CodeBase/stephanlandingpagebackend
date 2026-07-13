from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Settings:

    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    SITE_ID = os.getenv("SITE_ID")
    TENANT_ID = os.getenv("TENANT_ID")
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")

    SHAREPOINT_HOST = os.getenv("SHAREPOINT_HOST")

    DOCUMENT_LIBRARY = os.getenv("DOCUMENT_LIBRARY")

    EXCEL_FILE_NAME = os.getenv("EXCEL_FILE_NAME")

    TABLE_NAME = os.getenv("TABLE_NAME")

    MAILBOX = os.getenv("MAILBOX")

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL") or os.getenv("REICEIVER_EMAIL")

    MAIL_SENDER_EMAIL = os.getenv("MAIL_SENDER_EMAIL")
    EMAIL_DELIVERY_MODE = os.getenv("EMAIL_DELIVERY_MODE", "graph")
    SMTP_EMAIL = os.getenv("SMTP_EMAIL")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    CC_EMAILS = os.getenv("CC_EMAILS") or os.getenv("cc_emails", "")

    @classmethod
    def validate(cls):
        required = [
            "SITE_ID", "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET",
            "DOCUMENT_LIBRARY", "EXCEL_FILE_NAME", "TABLE_NAME", "ADMIN_EMAIL",
        ]
        if cls.EMAIL_DELIVERY_MODE.lower() == "smtp":
            required.extend(["SMTP_EMAIL", "SMTP_PASSWORD"])
        else:
            required.append("MAIL_SENDER_EMAIL")
        missing = [name for name in required if not getattr(cls, name, None)]
        if missing:
            raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


settings = Settings()
