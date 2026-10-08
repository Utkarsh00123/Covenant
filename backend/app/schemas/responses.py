from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID

# -----------------------------------------
# Risk Flag & Redline Responses
# -----------------------------------------
class DiffOperation(BaseModel):
    """Represents a single word/token level operation for the Track Changes UI."""
    operation: Literal["insert", "delete", "equal"]
    text: str

class RiskFlagResponse(BaseModel):
    """
    Exposes clause-level risks to the Next.js frontend.
    Hides internal plumbing (e.g., ai_model_version, raw foreign keys).
    """
    id: UUID
    flag_type: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    flag_reason: str
    evidence_text: str
    baseline_text: Optional[str] = None
    suggested_redline: Optional[str] = None
    plain_english_explanation: Optional[str] = None
    redline_diff: Optional[List[DiffOperation]] = None
    
    # Audit confidence exposed for UI badges (e.g. "82% match")
    similarity_score: Optional[float] = None
    
    status: str = "OPEN"
    user_override_reason: Optional[str] = None

    # Allows Pydantic to read directly from SQLAlchemy ORM objects
    model_config = ConfigDict(from_attributes=True)

# -----------------------------------------
# Document Responses
# -----------------------------------------
class DocumentListResponse(BaseModel):
    """Lightweight document representation for the main dashboard table."""
    id: UUID
    filename: str
    document_type: Optional[str] = "contract"
    status: Optional[str] = "PENDING"
    created_at: Optional[datetime] = None
    
    # Composite risk metrics from calculate_document_risk_score
    risk_level: Optional[str] = "PENDING"
    numeric_score: Optional[int] = Field(default=None, ge=0, le=100)

    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(BaseModel):
    """Comprehensive document payload for the side-by-side analysis view."""
    document: DocumentListResponse
    numeric_score: Optional[int] = Field(default=None, ge=0, le=100)
    risk_summary: Optional[Dict[str, int]] = None  # e.g., {"CRITICAL": 1, "HIGH": 2}
    extracted_intelligence: Optional[Any] = None  # The structured JSON data from extraction
    flags: List[RiskFlagResponse] = []

    model_config = ConfigDict(from_attributes=True)