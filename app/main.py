import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.models import BookDemo, APIResponse
from app.graph import add_booking_to_excel
from app.email import send_booking_emails
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


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


# Serve the landing page and assets from the same origin as the API in production.
FRONTEND_DIR = Path(__file__).resolve().parents[2]
if (FRONTEND_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
