import msal

from app.config import settings


authority = f"https://login.microsoftonline.com/{settings.TENANT_ID}"

scope = [
    "https://graph.microsoft.com/.default"
]


_app = None


def get_access_token():
    global _app
    if _app is None:
        _app = msal.ConfidentialClientApplication(
            client_id=settings.CLIENT_ID,
            authority=authority,
            client_credential=settings.CLIENT_SECRET,
        )

    result = _app.acquire_token_for_client(scopes=scope)

    if "access_token" not in result:

        raise Exception(result)

    return result["access_token"]
