from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import date, time
from typing import Optional


class BookDemo(BaseModel):
    firstName: str = Field(min_length=1, max_length=80)
    lastName: str = Field(min_length=1, max_length=80)
    email: EmailStr
    suitableDate: date
    suitableTime: time

    @field_validator("firstName", "lastName")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned


class DeletionRequest(BaseModel):
    email: EmailStr
    reason: Optional[str] = None
    username: Optional[str] = None
    requestedAt: Optional[str] = None


class APIResponse(BaseModel):
    success: bool
    message: str
    referenceId: Optional[str] = None
