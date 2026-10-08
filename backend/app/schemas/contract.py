from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union, Any
from enum import Enum

class ClauseCategory(str, Enum):
    """Enumeration of strict clause categories the AI is allowed to classify."""
    LIABILITY_CAP = "LIABILITY_CAP"
    AUTO_RENEWAL = "AUTO_RENEWAL"
    INDEMNIFICATION = "INDEMNIFICATION"
    TERMINATION_CONVENIENCE = "TERMINATION_CONVENIENCE"
    PAYMENT_TERMS = "PAYMENT_TERMS"
    CONFIDENTIALITY = "CONFIDENTIALITY"
    GOVERNING_LAW = "GOVERNING_LAW"
    UNKNOWN = "UNKNOWN"

class ExtractedClause(BaseModel):
    """Schema for a single extracted legal clause."""
    category: ClauseCategory = Field(
        default=ClauseCategory.UNKNOWN,
        description="The category of the clause. If it does not match exactly, use UNKNOWN."
    )
    raw_text: str = Field(
        default="",
        description="The VERBATIM text of the clause extracted from the document. Do not paraphrase."
    )
    confidence_score: str = Field(
        default="MEDIUM",
        description="Your confidence in this extraction: HIGH, MEDIUM, or LOW."
    )
    page_number_estimate: Optional[int] = Field(
        None, description="The estimated page number this clause appears on, if discernible from context."
    )
    renewal_period_months: Optional[int] = Field(
        None, description="If auto-renewal, the length of the renewal period in months (e.g. 12, 24, 36)."
    )
    notice_period_days: Optional[int] = Field(
        None, description="Notice period in days required to cancel or prevent renewal (e.g. 30, 60, 90)."
    )
    payment_terms_days: Optional[int] = Field(
        None, description="Payment terms in days (e.g. 30 for Net 30, 45, 60)."
    )
    is_liability_capped: Optional[bool] = Field(
        None, description="Whether liability under this clause is explicitly capped."
    )
    is_mutual: Optional[bool] = Field(
        None, description="Whether the obligations or rights in this clause are mutual."
    )

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: Any) -> ClauseCategory:
        if isinstance(v, ClauseCategory):
            return v
        if isinstance(v, str):
            clean = v.upper().strip().replace(" ", "_").replace("-", "_")
            for cat in ClauseCategory:
                if cat.value == clean:
                    return cat
            if "LIABIL" in clean or "LIMITATION" in clean:
                return ClauseCategory.LIABILITY_CAP
            if "RENEW" in clean:
                return ClauseCategory.AUTO_RENEWAL
            if "INDEMN" in clean:
                return ClauseCategory.INDEMNIFICATION
            if "TERMINAT" in clean:
                return ClauseCategory.TERMINATION_CONVENIENCE
            if "PAY" in clean or "FEE" in clean or "INVOIC" in clean:
                return ClauseCategory.PAYMENT_TERMS
            if "CONFIDEN" in clean or "NDA" in clean or "PROPRIETARY" in clean:
                return ClauseCategory.CONFIDENTIALITY
            if "LAW" in clean or "JURISDICTION" in clean or "GOVERN" in clean:
                return ClauseCategory.GOVERNING_LAW
        return ClauseCategory.UNKNOWN

    @field_validator("confidence_score", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> str:
        if isinstance(v, (int, float)):
            if v > 0.7:
                return "HIGH"
            elif v > 0.4:
                return "MEDIUM"
            return "LOW"
        return str(v) if v else "MEDIUM"

class ContractAnalysis(BaseModel):
    """The master schema for extracting data from a legal contract."""
    parties: List[str] = Field(
        default_factory=list,
        description="A list of the legal entities or people entering into the agreement."
    )
    effective_date: Optional[str] = Field(
        None, description="The date the contract goes into effect, formatted as YYYY-MM-DD."
    )
    expiration_date: Optional[str] = Field(
        None, description="The date the contract expires, formatted as YYYY-MM-DD. Leave null if perpetual."
    )
    governing_law_jurisdiction: Optional[str] = Field(
        None, description="The state or country whose laws govern the agreement (e.g., 'Delaware', 'California')."
    )
    renewal_period_months: Optional[int] = Field(
        None, description="Overall contract renewal term in months if specified."
    )
    payment_terms_days: Optional[int] = Field(
        None, description="Standard payment terms in days (e.g. 30 for Net 30)."
    )
    is_liability_capped: Optional[bool] = Field(
        None, description="Whether liability is capped across the contract."
    )
    key_clauses: List[ExtractedClause] = Field(
        default_factory=list,
        description="A list of highly critical legal clauses found in the document."
    )

    @field_validator("parties", mode="before")
    @classmethod
    def normalize_parties(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(item) for item in v if item]
        return []

    @field_validator("key_clauses", mode="before")
    @classmethod
    def normalize_key_clauses(cls, v: Any) -> List[Any]:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []