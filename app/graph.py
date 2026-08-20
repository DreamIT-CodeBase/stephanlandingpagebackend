import logging
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from app.config import settings
from app.auth import get_access_token
from app.models import BookDemo, DeletionRequest

logger = logging.getLogger(__name__)

# Cache Microsoft resource identifiers to avoid repeated discovery calls.
DRIVE_ID_CACHE = None
FILE_ID_CACHE = None
TABLE_ID_CACHE = None


def get_drive_id(token: str) -> str:
    global DRIVE_ID_CACHE
    if DRIVE_ID_CACHE:
        return DRIVE_ID_CACHE

    url = f"{settings.GRAPH_BASE}/sites/{settings.SITE_ID}/drives"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    drives = response.json().get("value", [])

    for d in drives:
        if d.get("name", "").casefold() == settings.DOCUMENT_LIBRARY.casefold():
            DRIVE_ID_CACHE = d.get("id")
            return DRIVE_ID_CACHE

    raise RuntimeError(f"SharePoint library '{settings.DOCUMENT_LIBRARY}' was not found")


def get_file_id(token: str, drive_id: str) -> str:
    global FILE_ID_CACHE
    if FILE_ID_CACHE:
        return FILE_ID_CACHE

    encoded_path = quote(settings.EXCEL_FILE_NAME.strip("/"), safe="/")
    url = f"{settings.GRAPH_BASE}/drives/{drive_id}/root:/{encoded_path}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=20)
    if response.ok:
        FILE_ID_CACHE = response.json()["id"]
        return FILE_ID_CACHE
    if response.status_code != 404:
        response.raise_for_status()

    # Keep compatibility with an existing file that has an accidental extra extension.
    list_url = f"{settings.GRAPH_BASE}/drives/{drive_id}/root/children?$select=id,name,file"
    listing = requests.get(list_url, headers=headers, timeout=20)
    listing.raise_for_status()
    target = settings.EXCEL_FILE_NAME.casefold()
    matches = [
        item for item in listing.json().get("value", [])
        if item.get("file") and item.get("name", "").casefold().startswith(target)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Excel workbook '{settings.EXCEL_FILE_NAME}' was not found unambiguously in the library"
        )
    FILE_ID_CACHE = matches[0]["id"]
    logger.warning(
        "Using SharePoint workbook '%s' for configured name '%s'",
        matches[0]["name"],
        settings.EXCEL_FILE_NAME,
    )
    return FILE_ID_CACHE


def get_table_id(token: str, drive_id: str, file_id: str) -> str:
    global TABLE_ID_CACHE
    if TABLE_ID_CACHE:
        return TABLE_ID_CACHE

    url = f"{settings.GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/tables?$select=id,name"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    tables = response.json().get("value", [])
    configured = settings.TABLE_NAME.casefold()
    matches = [table for table in tables if table.get("name", "").casefold() == configured]
    if len(matches) == 1:
        TABLE_ID_CACHE = matches[0]["id"]
        return TABLE_ID_CACHE
    if len(tables) == 1:
        TABLE_ID_CACHE = tables[0]["id"]
        logger.warning(
            "Using only Excel table '%s' for configured name '%s'",
            tables[0].get("name"),
            settings.TABLE_NAME,
        )
        return TABLE_ID_CACHE
    raise RuntimeError(f"Excel table '{settings.TABLE_NAME}' was not found unambiguously")


def add_booking_to_excel(booking: BookDemo):
    """Append a booking directly to the configured SharePoint Excel table."""
    try:
        token = get_access_token()
        drive_id = get_drive_id(token)
        file_id = get_file_id(token, drive_id)
        table_id = get_table_id(token, drive_id, file_id)
        values = [[
            f"{booking.firstName} {booking.lastName}",
            str(booking.email),
            booking.firstName,
            booking.lastName,
            booking.suitableDate.isoformat(),
            booking.suitableTime.strftime("%H:%M"),
            "Pending",
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ]]
        encoded_table_id = quote(table_id, safe="")
        url = f"{settings.GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/tables/{encoded_table_id}/rows/add"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"values": values},
            timeout=30,
        )
        response.raise_for_status()
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Failed to add row to Excel: {e}")
        raise


def add_deletion_request_to_excel(request: DeletionRequest):
    """Append an account deletion request row to the configured SharePoint Excel table."""
    try:
        token = get_access_token()
        drive_id = get_drive_id(token)
        file_id = get_file_id(token, drive_id)
        table_id = get_table_id(token, drive_id, file_id)

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        created_on = now.isoformat(timespec="seconds")
        full_name = f"[ACCOUNT DELETION] {request.username or request.email}"
        reason_text = f"DELETION: {request.reason}" if request.reason else "DELETION REQUEST"

        values = [[
            full_name,
            str(request.email),
            "Account Deletion",
            request.username or "N/A",
            date_str,
            time_str,
            reason_text,
            created_on,
        ]]
        encoded_table_id = quote(table_id, safe="")
        url = f"{settings.GRAPH_BASE}/drives/{drive_id}/items/{file_id}/workbook/tables/{encoded_table_id}/rows/add"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"values": values},
            timeout=30,
        )
        response.raise_for_status()
        logger.info("Successfully added deletion request for %s to SharePoint Excel", request.email)
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Failed to add deletion row to Excel: {e}")
        raise

