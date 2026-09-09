"""
Demo Support Triage Use Case Models (Strands Implementation).

Pydantic models for support ticket triage requests and responses.
"""

from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class TriageMode(str, Enum):
    """Type of triage operation."""
    FULL = "full"
    CLASSIFY_ONLY = "classify_only"
    DRAFT_ONLY = "draft_only"


class TicketCategory(str, Enum):
    """Category classification for support tickets."""
    TECHNICAL_ISSUE = "technical_issue"
    BILLING_INQUIRY = "billing_inquiry"
    FEATURE_REQUEST = "feature_request"
    COMPLAINT = "complaint"
    GENERAL_QUESTION = "general_question"
    ACCOUNT_ACCESS = "account_access"
    PRODUCT_INFO = "product_info"
    OTHER = "other"


class UrgencyLevel(str, Enum):
    """Urgency level for support tickets."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TriageRequest(BaseModel):
    """Request model for support ticket triage."""
    ticket_id: str = Field(..., description="Unique ticket identifier")
    triage_mode: TriageMode = Field(
        default=TriageMode.FULL,
        description="Type of triage operation"
    )
    additional_context: str | None = Field(
        default=None,
        description="Additional context for the triage"
    )


class TriageResponse(BaseModel):
    """Response model for support ticket triage."""
    ticket_id: str = Field(..., description="Ticket identifier")
    category: TicketCategory = Field(..., description="Classified ticket category")
    urgency: UrgencyLevel = Field(..., description="Urgency level")
    suggested_response: str = Field(..., description="Drafted response for the ticket")
    reasoning: str = Field(..., description="Explanation of classification and urgency")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Triage timestamp")
    raw_analysis: dict = Field(default_factory=dict, description="Raw analysis from agent")


__all__ = [
    "TriageMode",
    "TicketCategory",
    "UrgencyLevel",
    "TriageRequest",
    "TriageResponse",
]
