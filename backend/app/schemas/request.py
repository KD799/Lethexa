
from pydantic import BaseModel, Field, field_validator
from typing import Literal
import re


class RequestCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)

    request_type: Literal["access", "deletion"]

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Name cannot be empty")

        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        value = value.strip().lower()

        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if not re.match(pattern, value):
            raise ValueError("Invalid email address")

        return value


class RequestResponse(BaseModel):
    request_id: str
    full_name: str
    email: str
    request_type: str
    status: str
    created_at: str
