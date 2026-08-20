import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.models import BookDemo, DeletionRequest, APIResponse
from app.graph import add_booking_to_excel, add_deletion_request_to_excel
from app.email import send_booking_emails, send_deletion_emails
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Social Studying AI Booking API",
    version="1.0.0"
)

settings.validate()

# Configure CORS middleware to accept calls from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production security if needed
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/book", response_model=APIResponse)
async def book_demo(booking: BookDemo):
    logger.info(f"Received booking request for: {booking.firstName} {booking.lastName} ({booking.email})")
    
    # 1. Save record to SharePoint Excel Sheet
    try:
        add_booking_to_excel(booking)
        logger.info("Successfully added booking to SharePoint Excel table")
    except Exception as e:
        logger.error(f"SharePoint Excel transaction failed: {e}")
        # If database/Excel transaction fails, we report error back to the user
        raise HTTPException(
            status_code=500,
            detail="We could not save your booking. Please try again shortly."
        )

    # 2. Dispatch Graph API confirmation emails (customer & admin)
    try:
        send_booking_emails(booking)
        logger.info("Successfully processed and dispatched booking emails")
    except Exception as e:
        logger.error("Booking saved, but email dispatch failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail="Your booking was saved, but a confirmation email could not be sent. Our team has been notified; please do not submit again.",
        )

    return APIResponse(
        success=True,
        message="Demo request submitted and confirmation email sent successfully!"
    )


@app.post("/api/delete-account", response_model=APIResponse)
@app.post("/api/request-deletion", response_model=APIResponse)
async def request_account_deletion(request: DeletionRequest):
    import uuid
    reference_id = f"DEL-{uuid.uuid4().hex[:8].upper()}"

    logger.info("Received account deletion request for: %s (Username: %s, Ref: %s)", request.email, request.username, reference_id)

    # 1. Save deletion record to SharePoint Excel Sheet
    try:
        add_deletion_request_to_excel(request)
        logger.info("Successfully added deletion request to SharePoint Excel table")
    except Exception as e:
        logger.error("SharePoint Excel deletion logging failed: %s", e)
        # Continue to attempt sending email alert even if Excel write fails

    # 2. Dispatch Graph API / SMTP notification emails (user receipt & admin alert)
    try:
        send_deletion_emails(request, reference_id)
        logger.info("Successfully dispatched deletion alert emails")
    except Exception as e:
        logger.error("Deletion alert email dispatch failed: %s", e)

    return APIResponse(
        success=True,
        message=f"Account deletion request received for {request.email}. Reference ID: {reference_id}. Our privacy team will process it within 30 days.",
        referenceId=reference_id,
    )



@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


# Serve the landing page and assets from the same origin as the API in production.
FRONTEND_DIR = Path(__file__).resolve().parents[2]
if (FRONTEND_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
