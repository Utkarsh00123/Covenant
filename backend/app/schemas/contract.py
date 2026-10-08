from pydantic import BaseModel, Field
from typing import List, Optional
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
        description="The category of the clause. If it does not match exactly, use UNKNOWN."
    )
    raw_text: str = Field(
        description="The VERBATIM text of the clause extracted from the document. Do not paraphrase."
    )
    confidence_score: str = Field(
        description="Your confidence in this extraction: HIGH, MEDIUM, or LOW."
    )
    page_number_estimate: Optional[int] = Field(
        None, description="The estimated page number this clause appears on, if discernible from context."
    )

class ContractAnalysis(BaseModel):
    """The master schema for extracting data from a legal contract."""
    parties: List[str] = Field(
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
    key_clauses: List[ExtractedClause] = Field(
        description="A list of highly critical legal clauses found in the document."
    )