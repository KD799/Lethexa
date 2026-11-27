
from pydantic import BaseModel, Field


class VerificationSubmit(BaseModel):

    code: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="Enter the six-digit verification code"
    )
