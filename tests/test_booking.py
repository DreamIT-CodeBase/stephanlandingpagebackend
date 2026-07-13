import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


class BookingApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = {
            "firstName": "Jane",
            "lastName": "Student",
            "email": "jane@example.com",
            "suitableDate": "2030-08-15",
            "suitableTime": "14:30",
        }

    @patch("app.main.send_booking_emails")
    @patch("app.main.add_booking_to_excel")
    def test_booking_saves_and_sends_both_emails(self, save_booking, send_emails):
        response = self.client.post("/api/book", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        save_booking.assert_called_once()
        send_emails.assert_called_once()

    @patch("app.main.send_booking_emails", side_effect=RuntimeError("mail unavailable"))
    @patch("app.main.add_booking_to_excel")
    def test_email_failure_is_reported_honestly(self, save_booking, _send_emails):
        response = self.client.post("/api/book", json=self.payload)
        self.assertEqual(response.status_code, 502)
        self.assertIn("booking was saved", response.json()["detail"].lower())
        save_booking.assert_called_once()

    def test_invalid_email_is_rejected(self):
        response = self.client.post("/api/book", json={**self.payload, "email": "invalid"})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
