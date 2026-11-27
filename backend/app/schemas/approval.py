from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


class ApprovalSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]

    comments: str = Field(
        default="",
        max_length=500
    )


class ApprovalResponse(BaseModel):
    request_id: str
    reviewer_id: str
    reviewer_role: str
    decision: str
    comments: str
    status: str
    reviewed_at: str